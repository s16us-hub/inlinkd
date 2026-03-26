"""LinkedIn API client for the Community Management and Pages APIs."""

from __future__ import annotations

import httpx
from typing import Any


LINKEDIN_API_BASE = "https://api.linkedin.com/rest"
LINKEDIN_API_VERSION = "202503"


class LinkedInPagesClient:
    """HTTP client for LinkedIn's official Community Management and Pages APIs.

    Uses OAuth 2.0 bearer tokens. The authenticated user must be an admin
    of the target company page.
    """

    def __init__(self, access_token: str, organization_id: str) -> None:
        self.organization_id = organization_id
        self._client = httpx.AsyncClient(
            base_url=LINKEDIN_API_BASE,
            headers={
                "Authorization": f"Bearer {access_token}",
                "LinkedIn-Version": LINKEDIN_API_VERSION,
                "X-Restli-Protocol-Version": "2.0.0",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    @property
    def org_urn(self) -> str:
        return f"urn:li:organization:{self.organization_id}"

    async def close(self) -> None:
        await self._client.aclose()

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
            body["content"] = {
                "media": {
                    "id": media_id,
                    "title": media_title or "",
                },
            }

        resp = await self._client.post("/posts", json=body)
        resp.raise_for_status()
        post_id = resp.headers.get("x-restli-id", "")
        return {"post_id": post_id, "status": "published"}

    async def get_posts(
        self, count: int = 10, start: int = 0
    ) -> dict[str, Any]:
        params = {
            "author": self.org_urn,
            "q": "author",
            "count": min(count, 100),
            "start": start,
            "sortBy": "LAST_MODIFIED",
        }
        resp = await self._client.get("/posts", params=params)
        resp.raise_for_status()
        return resp.json()

    async def get_post(self, post_id: str) -> dict[str, Any]:
        resp = await self._client.get(f"/posts/{post_id}")
        resp.raise_for_status()
        return resp.json()

    async def delete_post(self, post_id: str) -> dict[str, Any]:
        resp = await self._client.delete(f"/posts/{post_id}")
        resp.raise_for_status()
        return {"post_id": post_id, "status": "deleted"}

    async def update_post(self, post_id: str, text: str) -> dict[str, Any]:
        body = {"patch": {"$set": {"commentary": text}}}
        resp = await self._client.post(f"/posts/{post_id}", json=body)
        resp.raise_for_status()
        return {"post_id": post_id, "status": "updated"}

    # ── Comments ──────────────────────────────────────────────────────

    async def get_comments(
        self, post_urn: str, count: int = 10, start: int = 0
    ) -> dict[str, Any]:
        params = {"q": "socialActions", "count": count, "start": start}
        resp = await self._client.get(
            f"/socialActions/{post_urn}/comments", params=params
        )
        resp.raise_for_status()
        return resp.json()

    async def create_comment(
        self, post_urn: str, text: str
    ) -> dict[str, Any]:
        body = {
            "actor": self.org_urn,
            "message": {"text": text},
        }
        resp = await self._client.post(
            f"/socialActions/{post_urn}/comments", json=body
        )
        resp.raise_for_status()
        return resp.json()

    async def delete_comment(
        self, post_urn: str, comment_id: str
    ) -> dict[str, Any]:
        resp = await self._client.delete(
            f"/socialActions/{post_urn}/comments/{comment_id}"
        )
        resp.raise_for_status()
        return {"comment_id": comment_id, "status": "deleted"}

    # ── Reactions ─────────────────────────────────────────────────────

    async def get_reactions(
        self, post_urn: str, count: int = 10
    ) -> dict[str, Any]:
        params = {"q": "entity", "count": count}
        resp = await self._client.get(
            f"/reactions/(entity:{post_urn})", params=params
        )
        resp.raise_for_status()
        return resp.json()

    async def add_reaction(
        self, post_urn: str, reaction_type: str = "LIKE"
    ) -> dict[str, Any]:
        body = {
            "root": post_urn,
            "reactionType": reaction_type,
            "actor": self.org_urn,
        }
        resp = await self._client.post("/reactions", json=body)
        resp.raise_for_status()
        return {"status": "reacted", "type": reaction_type}

    # ── Analytics ─────────────────────────────────────────────────────

    async def get_follower_statistics(
        self, time_granularity: str = "MONTH"
    ) -> dict[str, Any]:
        params = {
            "q": "organizationalEntity",
            "organizationalEntity": self.org_urn,
            "timeIntervals.timeGranularityType": time_granularity,
        }
        resp = await self._client.get(
            "/organizationalEntityFollowerStatistics", params=params
        )
        resp.raise_for_status()
        return resp.json()

    async def get_page_statistics(
        self, time_granularity: str = "MONTH"
    ) -> dict[str, Any]:
        params = {
            "q": "organizationalEntity",
            "organizationalEntity": self.org_urn,
            "timeIntervals.timeGranularityType": time_granularity,
        }
        resp = await self._client.get(
            "/organizationPageStatistics", params=params
        )
        resp.raise_for_status()
        return resp.json()

    async def get_share_statistics(
        self, shares: list[str] | None = None
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "q": "organizationalEntity",
            "organizationalEntity": self.org_urn,
        }
        if shares:
            params["shares"] = ",".join(shares)
        resp = await self._client.get(
            "/organizationalEntityShareStatistics", params=params
        )
        resp.raise_for_status()
        return resp.json()

    async def get_follower_demographics(self) -> dict[str, Any]:
        params = {
            "q": "organizationalEntity",
            "organizationalEntity": self.org_urn,
        }
        resp = await self._client.get(
            "/organizationalEntityFollowerStatistics", params=params
        )
        resp.raise_for_status()
        return resp.json()

    # ── Media Upload ──────────────────────────────────────────────────

    async def initialize_image_upload(self) -> dict[str, Any]:
        body = {
            "initializeUploadRequest": {
                "owner": self.org_urn,
            },
        }
        resp = await self._client.post("/images?action=initializeUpload", json=body)
        resp.raise_for_status()
        return resp.json()

    async def upload_image_binary(self, upload_url: str, image_data: bytes) -> None:
        async with httpx.AsyncClient(timeout=120.0) as upload_client:
            resp = await upload_client.put(
                upload_url,
                content=image_data,
                headers={"Content-Type": "application/octet-stream"},
            )
            resp.raise_for_status()

    # ── Organization Info ─────────────────────────────────────────────

    async def get_organization(self) -> dict[str, Any]:
        resp = await self._client.get(f"/organizations/{self.organization_id}")
        resp.raise_for_status()
        return resp.json()
