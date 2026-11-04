"""Offline tests for the LinkedIn client: no network, no real token."""

from __future__ import annotations

import json
from collections.abc import Callable

import httpx
import pytest

from linkedin_pages_mcp.client import (
    LinkedInAPIError,
    LinkedInPagesClient,
    normalize_post_urn,
    urn_path,
)

ORG = "111806031"
Handler = Callable[[httpx.Request], httpx.Response]


def make_client(handler: Handler) -> LinkedInPagesClient:
    return LinkedInPagesClient(
        access_token="test-token",
        organization_id=ORG,
        transport=httpx.MockTransport(handler),
    )


# ── helpers ───────────────────────────────────────────────────────────


def test_urn_path_encodes_colons() -> None:
    assert urn_path("urn:li:share:123") == "urn%3Ali%3Ashare%3A123"


def test_normalize_accepts_full_urn() -> None:
    assert normalize_post_urn("urn:li:share:123") == "urn:li:share:123"


def test_normalize_rejects_bare_id_and_garbage() -> None:
    with pytest.raises(LinkedInAPIError) as bare:
        normalize_post_urn("123")
    assert bare.value.status == 400
    with pytest.raises(LinkedInAPIError):
        normalize_post_urn("https://example.com")


def test_constructor_validates_inputs() -> None:
    with pytest.raises(LinkedInAPIError):
        LinkedInPagesClient(access_token="", organization_id=ORG)
    with pytest.raises(LinkedInAPIError):
        LinkedInPagesClient(access_token="t", organization_id="not-a-number")


# ── posts ─────────────────────────────────────────────────────────────


async def test_create_post_sends_org_author_and_returns_id() -> None:
    seen: dict[str, object] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(req.content)
        seen["auth"] = req.headers["Authorization"]
        return httpx.Response(201, headers={"x-restli-id": "urn:li:share:999"})

    client = make_client(handler)
    result = await client.create_post("Hello world")
    await client.close()

    body = seen["body"]
    assert isinstance(body, dict)
    assert body["author"] == f"urn:li:organization:{ORG}"
    assert body["commentary"] == "Hello world"
    assert body["lifecycleState"] == "PUBLISHED"
    assert seen["auth"] == "Bearer test-token"
    assert result == {"post_id": "urn:li:share:999", "status": "published"}


async def test_create_post_rejects_empty_and_too_long_text() -> None:
    client = make_client(lambda r: httpx.Response(201))
    with pytest.raises(LinkedInAPIError):
        await client.create_post("   ")
    with pytest.raises(LinkedInAPIError) as long_text:
        await client.create_post("x" * 3001)
    assert "3000" in long_text.value.message
    await client.close()


async def test_create_post_rejects_article_and_media_together() -> None:
    client = make_client(lambda r: httpx.Response(201))
    with pytest.raises(LinkedInAPIError):
        await client.create_post("hi", article_url="https://a.test", media_id="urn:li:image:1")
    await client.close()


async def test_update_post_uses_partial_update_header() -> None:
    seen: dict[str, str] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["method"] = req.headers.get("X-RestLi-Method", "")
        seen["path"] = req.url.raw_path.decode()
        return httpx.Response(204)

    client = make_client(handler)
    result = await client.update_post("urn:li:share:123", "new text")
    await client.close()

    assert seen["method"] == "PARTIAL_UPDATE"
    assert "urn%3Ali%3Ashare%3A123" in seen["path"]
    assert result["status"] == "updated"


async def test_get_posts_clamps_count() -> None:
    seen: dict[str, str] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["count"] = req.url.params["count"]
        return httpx.Response(200, json={"elements": []})

    client = make_client(handler)
    await client.get_posts(count=500)
    await client.close()
    assert seen["count"] == "100"


# ── errors ────────────────────────────────────────────────────────────


async def test_api_error_is_structured() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"message": "Not enough permissions"})

    client = make_client(handler)
    with pytest.raises(LinkedInAPIError) as exc:
        await client.get_organization()
    await client.close()

    assert exc.value.status == 403
    assert exc.value.to_dict()["error"] == "Not enough permissions"


async def test_network_error_becomes_503() -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=req)

    client = make_client(handler)
    with pytest.raises(LinkedInAPIError) as exc:
        await client.get_organization()
    await client.close()
    assert exc.value.status == 503


async def test_bad_granularity_rejected_before_sending() -> None:
    calls: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(req)
        return httpx.Response(200, json={})

    client = make_client(handler)
    with pytest.raises(LinkedInAPIError):
        await client.get_follower_statistics("YEAR")
    await client.close()
    assert calls == []


async def test_reaction_type_validated() -> None:
    client = make_client(lambda r: httpx.Response(201))
    with pytest.raises(LinkedInAPIError):
        await client.add_reaction("urn:li:share:1", "HATE")
    await client.close()


# ── image upload ──────────────────────────────────────────────────────


async def test_upload_image_rejects_missing_file(tmp_path) -> None:  # type: ignore[no-untyped-def]
    client = make_client(lambda r: httpx.Response(200))
    with pytest.raises(LinkedInAPIError) as exc:
        await client.upload_image(str(tmp_path / "nope.png"))
    await client.close()
    assert exc.value.status == 400


async def test_upload_image_rejects_wrong_extension(tmp_path) -> None:  # type: ignore[no-untyped-def]
    f = tmp_path / "doc.pdf"
    f.write_bytes(b"%PDF")
    client = make_client(lambda r: httpx.Response(200))
    with pytest.raises(LinkedInAPIError):
        await client.upload_image(str(f))
    await client.close()
