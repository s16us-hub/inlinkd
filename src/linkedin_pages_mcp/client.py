"""LinkedIn API client for the Community Management and Pages APIs.

Uses only LinkedIn's official REST API with OAuth 2.0 bearer tokens. The
authenticated member must be an admin of the target company page.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx
from typing_extensions import Self

LINKEDIN_API_BASE = "https://api.linkedin.com/rest"
DEFAULT_API_VERSION = "202503"

MAX_POST_CHARS = 3000
MAX_COMMENT_CHARS = 1250
MAX_PAGE_SIZE = 100
MAX_IMAGE_BYTES = 10 * 1024 * 1024  # LinkedIn's image limit is 10 MB
ALLOWED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".gif"}
VALID_REACTIONS = {"LIKE", "PRAISE", "EMPATHY", "INTEREST", "APPRECIATION"}


class LinkedInAPIError(Exception):
    """A non-2xx response from LinkedIn, or invalid input caught before sending."""

    def __init__(self, status: int, message: str, body: Any = None) -> None:
        super().__init__(message)
        self.status = status
        self.message = message
        self.body = body

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"error": self.message, "status": self.status}
        if self.body:
            out["details"] = self.body
        return out


def _raise_for_status(resp: httpx.Response) -> None:
    if resp.is_success:
        return
    try:
        body: Any = resp.json()
    except ValueError:
        body = resp.text[:500] or None
    message = (
        body.get("message")
        if isinstance(body, dict) and body.get("message")
        else resp.reason_phrase
    )
    raise LinkedInAPIError(resp.status_code, str(message), body)


def _json(resp: httpx.Response) -> dict[str, Any]:
    data: Any = resp.json()
    return data if isinstance(data, dict) else {"data": data}


def _check_text(text: str, limit: int, field: str) -> None:
    if not text or not text.strip():
        raise LinkedInAPIError(400, f"{field} must not be empty")
    if len(text) > limit:
        raise LinkedInAPIError(400, f"{field} is {len(text)} characters; the limit is {limit}")


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(int(value), high))


def urn_path(value: str) -> str:
    """Percent-encode a URN (or bare ID) for use inside a URL path segment."""
    return quote(value, safe="")


def normalize_post_urn(post_id: str) -> str:
    """Accept a bare numeric ID or a full URN and return a full share/ugcPost URN."""
    value = post_id.strip()
    if value.startswith("urn:li:"):
        return value
    if value.isdigit():
        # Posts created via the /posts API are ugcPost-style URNs; the numeric
        # ID alone is ambiguous, so we require the caller to pass a full URN.
        raise LinkedInAPIError(
            400,
            "Pass the full post URN (for example urn:li:share:123 or urn:li:ugcPost:123); "
            "a bare numeric ID cannot be resolved to a post type.",
        )
    raise LinkedInAPIError(400, f"Not a LinkedIn post URN: {post_id!r}")


class LinkedInPagesClient:
    """Async client for a single LinkedIn company page."""

    def __init__(
        self,
        access_token: str,
        organization_id: str,
        api_version: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not access_token:
            raise LinkedInAPIError(401, "access token is empty")
        if not organization_id or not organization_id.isdigit():
            raise LinkedInAPIError(400, "organization_id must be the numeric company page ID")

        self.organization_id = organization_id
        self._client = httpx.AsyncClient(
            base_url=LINKEDIN_API_BASE,
            headers={
                "Authorization": f"Bearer {access_token}",
                "LinkedIn-Version": api_version
                or os.environ.get("LINKEDIN_API_VERSION", DEFAULT_API_VERSION),
                "X-Restli-Protocol-Version": "2.0.0",
                "Content-Type": "application/json",
            },
            timeout=30.0,
            transport=transport,
        )

    @property
    def org_urn(self) -> str:
        return f"urn:li:organization:{self.organization_id}"

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        try:
            resp = await self._client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise LinkedInAPIError(503, f"network error talking to LinkedIn: {exc}") from exc
        _raise_for_status(resp)
        return resp

    # ── Posts ──────────────────────────────────────────────────────────

    async def create_post(
        self,
        text: str,
        visibility: str = "PUBLIC",
        media_id: str | None = None,
        media_title: str | None = None,
        article_url: str | None = None,
        article_title: str | None = None,
        article_description: str | None = None,
    ) -> dict[str, Any]:
        _check_text(text, MAX_POST_CHARS, "text")
        if visibility != "PUBLIC":
            raise LinkedInAPIError(400, "only visibility 'PUBLIC' is supported")
        if article_url and media_id:
            raise LinkedInAPIError(400, "use either article_url or media_id, not both")

        body: dict[str, Any] = {
            "author": self.org_urn,
            "commentary": text,
            "visibility": visibility,
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": [],
            },
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        }
        if article_url:
            body["content"] = {
                "article": {
                    "source": article_url,
                    "title": article_title or "",
                    "description": article_description or "",
                },
            }
        elif media_id:
            body["content"] = {"media": {"id": media_id, "title": media_title or ""}}

        resp = await self._request("POST", "/posts", json=body)
        post_id = resp.headers.get("x-restli-id", "")
        return {"post_id": post_id, "status": "published"}

    async def get_posts(self, count: int = 10, start: int = 0) -> dict[str, Any]:
        params = {
            "author": self.org_urn,
            "q": "author",
            "count": _clamp(count, 1, MAX_PAGE_SIZE),
            "start": max(0, int(start)),
            "sortBy": "LAST_MODIFIED",
        }
        resp = await self._request("GET", "/posts", params=params)
        return _json(resp)

    async def get_post(self, post_id: str) -> dict[str, Any]:
        resp = await self._request("GET", f"/posts/{urn_path(post_id)}")
        return _json(resp)

    async def delete_post(self, post_id: str) -> dict[str, Any]:
        await self._request("DELETE", f"/posts/{urn_path(post_id)}")
        return {"post_id": post_id, "status": "deleted"}

    async def update_post(self, post_id: str, text: str) -> dict[str, Any]:
        _check_text(text, MAX_POST_CHARS, "text")
        body = {"patch": {"$set": {"commentary": text}}}
        # LinkedIn requires the partial-update method header for $set patches.
        await self._request(
            "POST",
            f"/posts/{urn_path(post_id)}",
            json=body,
            headers={"X-RestLi-Method": "PARTIAL_UPDATE"},
        )
        return {"post_id": post_id, "status": "updated"}

    # ── Comments ──────────────────────────────────────────────────────

    async def get_comments(self, post_urn: str, count: int = 10, start: int = 0) -> dict[str, Any]:
        params = {
            "q": "socialActions",
            "count": _clamp(count, 1, MAX_PAGE_SIZE),
            "start": max(0, int(start)),
        }
        resp = await self._request(
            "GET", f"/socialActions/{urn_path(post_urn)}/comments", params=params
        )
        return _json(resp)

    async def create_comment(self, post_urn: str, text: str) -> dict[str, Any]:
        _check_text(text, MAX_COMMENT_CHARS, "comment text")
        body = {"actor": self.org_urn, "message": {"text": text}}
        resp = await self._request(
            "POST", f"/socialActions/{urn_path(post_urn)}/comments", json=body
        )
        return _json(resp) if resp.content else {"status": "commented"}

    async def delete_comment(self, post_urn: str, comment_id: str) -> dict[str, Any]:
        await self._request(
            "DELETE",
            f"/socialActions/{urn_path(post_urn)}/comments/{urn_path(comment_id)}",
        )
        return {"comment_id": comment_id, "status": "deleted"}

    # ── Reactions ─────────────────────────────────────────────────────

    async def get_reactions(self, post_urn: str, count: int = 10) -> dict[str, Any]:
        params = {"q": "entity", "count": _clamp(count, 1, MAX_PAGE_SIZE)}
        resp = await self._request(
            "GET", f"/reactions/(entity:{urn_path(post_urn)})", params=params
        )
        return _json(resp)

    async def add_reaction(self, post_urn: str, reaction_type: str = "LIKE") -> dict[str, Any]:
        if reaction_type not in VALID_REACTIONS:
            raise LinkedInAPIError(400, f"reaction_type must be one of {sorted(VALID_REACTIONS)}")
        body = {"root": post_urn, "reactionType": reaction_type, "actor": self.org_urn}
        await self._request("POST", "/reactions", json=body)
        return {"status": "reacted", "type": reaction_type}

    # ── Analytics ─────────────────────────────────────────────────────

    def _granularity(self, value: str) -> str:
        if value not in {"DAY", "MONTH"}:
            raise LinkedInAPIError(400, "time_granularity must be DAY or MONTH")
        return value

    async def get_follower_statistics(self, time_granularity: str = "MONTH") -> dict[str, Any]:
        params = {
            "q": "organizationalEntity",
            "organizationalEntity": self.org_urn,
            "timeIntervals.timeGranularityType": self._granularity(time_granularity),
        }
        resp = await self._request("GET", "/organizationalEntityFollowerStatistics", params=params)
        return _json(resp)

    async def get_page_statistics(self, time_granularity: str = "MONTH") -> dict[str, Any]:
        params = {
            "q": "organizationalEntity",
            "organizationalEntity": self.org_urn,
            "timeIntervals.timeGranularityType": self._granularity(time_granularity),
        }
        resp = await self._request("GET", "/organizationPageStatistics", params=params)
        return _json(resp)

    async def get_share_statistics(self, shares: list[str] | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {"q": "organizationalEntity", "organizationalEntity": self.org_urn}
        if shares:
            params["shares"] = ",".join(shares)
        resp = await self._request("GET", "/organizationalEntityShareStatistics", params=params)
        return _json(resp)

    async def get_follower_demographics(self) -> dict[str, Any]:
        # Demographic facets come back on the same follower-statistics resource.
        params = {"q": "organizationalEntity", "organizationalEntity": self.org_urn}
        resp = await self._request("GET", "/organizationalEntityFollowerStatistics", params=params)
        return _json(resp)

    # ── Media Upload ──────────────────────────────────────────────────

    async def initialize_image_upload(self) -> dict[str, Any]:
        body = {"initializeUploadRequest": {"owner": self.org_urn}}
        resp = await self._request("POST", "/images?action=initializeUpload", json=body)
        return _json(resp)

    async def upload_image(self, image_path: str) -> dict[str, Any]:
        """Upload a local image file and return its media URN for linkedin_create_post."""
        path = Path(image_path).expanduser()
        if not path.is_file():
            raise LinkedInAPIError(400, f"image file not found: {image_path}")
        if path.suffix.lower() not in ALLOWED_IMAGE_SUFFIXES:
            raise LinkedInAPIError(400, "image must be a .jpg, .jpeg, .png or .gif file")
        size = path.stat().st_size
        if size == 0 or size > MAX_IMAGE_BYTES:
            raise LinkedInAPIError(400, "image must be between 1 byte and 10 MB")

        init = (
            await self._request(
                "POST",
                "/images?action=initializeUpload",
                json={"initializeUploadRequest": {"owner": self.org_urn}},
            )
        ).json()
        value = init.get("value", {})
        upload_url = value.get("uploadUrl")
        image_urn = value.get("image")
        if not upload_url or not image_urn:
            raise LinkedInAPIError(502, "LinkedIn did not return an upload URL", init)

        data = path.read_bytes()
        try:
            async with httpx.AsyncClient(timeout=120.0) as upload_client:
                resp = await upload_client.put(
                    upload_url, content=data, headers={"Content-Type": "application/octet-stream"}
                )
        except httpx.HTTPError as exc:
            raise LinkedInAPIError(503, f"image upload failed: {exc}") from exc
        _raise_for_status(resp)
        return {"media_id": image_urn, "status": "uploaded"}

    # ── Organization Info ─────────────────────────────────────────────

    async def get_organization(self) -> dict[str, Any]:
        resp = await self._request("GET", f"/organizations/{self.organization_id}")
        return _json(resp)
