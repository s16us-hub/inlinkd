"""Offline tests for member mode (posting as an individual, not a company page)."""

from __future__ import annotations

import json
import os

import httpx
import pytest

from linkedin_pages_mcp.client import LinkedInAPIError, LinkedInPagesClient
from linkedin_pages_mcp.server import COMPANY_PAGE_ONLY_TOOLS, TOOLS, visible_tools

PERSON = "AbC123xyz"
ORG = "111806031"


def member_client(handler) -> LinkedInPagesClient:  # type: ignore[no-untyped-def]
    return LinkedInPagesClient(
        access_token="test-token",
        person_id=PERSON,
        transport=httpx.MockTransport(handler),
    )


def test_exactly_one_identity_required() -> None:
    with pytest.raises(LinkedInAPIError):
        LinkedInPagesClient(access_token="t")
    with pytest.raises(LinkedInAPIError):
        LinkedInPagesClient(access_token="t", organization_id=ORG, person_id=PERSON)


async def test_member_post_uses_person_author() -> None:
    seen: dict[str, object] = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(req.content)
        return httpx.Response(201, headers={"x-restli-id": "urn:li:share:7"})

    client = member_client(handler)
    result = await client.create_post("Hello from me")
    await client.close()

    assert seen["body"]["author"] == f"urn:li:person:{PERSON}"  # type: ignore[index]
    assert result["post_id"] == "urn:li:share:7"


async def test_member_comment_and_reaction_use_person_actor() -> None:
    actors: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        actors.append(json.loads(req.content)["actor"])
        return httpx.Response(201, json={})

    client = member_client(handler)
    await client.create_comment("urn:li:share:1", "thanks")
    await client.add_reaction("urn:li:share:1", "LIKE")
    await client.close()

    assert actors == [f"urn:li:person:{PERSON}", f"urn:li:person:{PERSON}"]


async def test_member_image_upload_owner_is_person() -> None:
    owners: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        owners.append(json.loads(req.content)["initializeUploadRequest"]["owner"])
        return httpx.Response(
            200, json={"value": {"uploadUrl": "https://x.test/u", "image": "urn:li:image:1"}}
        )

    client = member_client(handler)
    await client.initialize_image_upload()
    await client.close()
    assert owners == [f"urn:li:person:{PERSON}"]


async def test_company_only_calls_are_blocked_in_member_mode() -> None:
    calls: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(req)
        return httpx.Response(200, json={})

    client = member_client(handler)
    with pytest.raises(LinkedInAPIError) as exc:
        await client.get_follower_statistics()
    with pytest.raises(LinkedInAPIError):
        await client.get_organization()
    await client.close()

    assert exc.value.status == 400
    assert calls == []  # nothing was sent to LinkedIn


def test_member_mode_hides_company_only_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LINKEDIN_AUTHOR_MODE", "member")
    names = {t.name for t in visible_tools()}
    assert names.isdisjoint(COMPANY_PAGE_ONLY_TOOLS)
    assert "linkedin_create_post" in names
    assert len(names) == len(TOOLS) - len(COMPANY_PAGE_ONLY_TOOLS)


def test_organization_mode_keeps_all_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LINKEDIN_AUTHOR_MODE", raising=False)
    assert len(visible_tools()) == len(TOOLS)


def test_bad_author_mode_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LINKEDIN_AUTHOR_MODE", "personal")
    with pytest.raises(LinkedInAPIError):
        visible_tools()
    os.environ.pop("LINKEDIN_AUTHOR_MODE", None)
