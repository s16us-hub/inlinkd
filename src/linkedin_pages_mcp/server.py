"""MCP server exposing LinkedIn Company Page management tools."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from linkedin_pages_mcp.client import (
    LinkedInAPIError,
    LinkedInPagesClient,
    normalize_post_urn,
)

log = logging.getLogger("linkedin_pages_mcp")

_GRANULARITY = {
    "type": "string",
    "enum": ["DAY", "MONTH"],
    "default": "MONTH",
    "description": "Time granularity for stats",
}
_POST_ID = {
    "type": "string",
    "description": "Full post URN, e.g. urn:li:share:123 or urn:li:ugcPost:123",
}


def _get_client() -> LinkedInPagesClient:
    token = os.environ.get("LINKEDIN_ACCESS_TOKEN", "")
    org_id = os.environ.get("LINKEDIN_ORGANIZATION_ID", "")
    if not token:
        raise LinkedInAPIError(401, "LINKEDIN_ACCESS_TOKEN environment variable is required")
    if not org_id:
        raise LinkedInAPIError(400, "LINKEDIN_ORGANIZATION_ID environment variable is required")
    return LinkedInPagesClient(access_token=token, organization_id=org_id)


TOOLS: list[Tool] = [
    # ── Posts ──────────────────────────────────────────────────────
    Tool(
        name="linkedin_create_post",
        description="Publish a post on the LinkedIn company page. Supports text, an article link, or an uploaded image (media_id from linkedin_upload_image).",
        inputSchema={
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Post text (max 3000 chars)"},
                "visibility": {"type": "string", "enum": ["PUBLIC"], "default": "PUBLIC"},
                "article_url": {
                    "type": "string",
                    "description": "Article link. Set article_title and article_description too; LinkedIn does not scrape them.",
                },
                "article_title": {"type": "string"},
                "article_description": {"type": "string"},
                "media_id": {
                    "type": "string",
                    "description": "Image URN returned by linkedin_upload_image",
                },
                "media_title": {"type": "string"},
            },
            "required": ["text"],
        },
    ),
    Tool(
        name="linkedin_get_posts",
        description="List recent posts from the company page, most recently modified first.",
        inputSchema={
            "type": "object",
            "properties": {
                "count": {"type": "integer", "default": 10, "minimum": 1, "maximum": 100},
                "start": {"type": "integer", "default": 0, "minimum": 0},
            },
        },
    ),
    Tool(
        name="linkedin_get_post",
        description="Get one post by its full URN.",
        inputSchema={
            "type": "object",
            "properties": {"post_id": _POST_ID},
            "required": ["post_id"],
        },
    ),
    Tool(
        name="linkedin_update_post",
        description="Replace the text of an existing company page post.",
        inputSchema={
            "type": "object",
            "properties": {
                "post_id": _POST_ID,
                "text": {"type": "string", "description": "New post text (max 3000 chars)"},
            },
            "required": ["post_id", "text"],
        },
    ),
    Tool(
        name="linkedin_delete_post",
        description="Delete a post from the company page. This cannot be undone.",
        inputSchema={
            "type": "object",
            "properties": {"post_id": _POST_ID},
            "required": ["post_id"],
        },
    ),
    # ── Comments ──────────────────────────────────────────────────
    Tool(
        name="linkedin_get_comments",
        description="Get comments on a company page post.",
        inputSchema={
            "type": "object",
            "properties": {
                "post_urn": _POST_ID,
                "count": {"type": "integer", "default": 10, "minimum": 1, "maximum": 100},
                "start": {"type": "integer", "default": 0, "minimum": 0},
            },
            "required": ["post_urn"],
        },
    ),
    Tool(
        name="linkedin_create_comment",
        description="Comment on a post as the company page (max 1250 chars).",
        inputSchema={
            "type": "object",
            "properties": {"post_urn": _POST_ID, "text": {"type": "string"}},
            "required": ["post_urn", "text"],
        },
    ),
    Tool(
        name="linkedin_delete_comment",
        description="Delete a comment the company page made or can moderate.",
        inputSchema={
            "type": "object",
            "properties": {"post_urn": _POST_ID, "comment_id": {"type": "string"}},
            "required": ["post_urn", "comment_id"],
        },
    ),
    # ── Reactions ─────────────────────────────────────────────────
    Tool(
        name="linkedin_get_reactions",
        description="Get reactions on a post.",
        inputSchema={
            "type": "object",
            "properties": {
                "post_urn": _POST_ID,
                "count": {"type": "integer", "default": 10, "minimum": 1, "maximum": 100},
            },
            "required": ["post_urn"],
        },
    ),
    Tool(
        name="linkedin_react_to_post",
        description="React to a post as the company page.",
        inputSchema={
            "type": "object",
            "properties": {
                "post_urn": _POST_ID,
                "reaction_type": {
                    "type": "string",
                    "enum": ["LIKE", "PRAISE", "EMPATHY", "INTEREST", "APPRECIATION"],
                    "default": "LIKE",
                },
            },
            "required": ["post_urn"],
        },
    ),
    # ── Analytics ─────────────────────────────────────────────────
    Tool(
        name="linkedin_get_follower_stats",
        description="Get follower counts and growth over time for the company page.",
        inputSchema={"type": "object", "properties": {"time_granularity": _GRANULARITY}},
    ),
    Tool(
        name="linkedin_get_page_stats",
        description="Get page view and click statistics for the company page.",
        inputSchema={"type": "object", "properties": {"time_granularity": _GRANULARITY}},
    ),
    Tool(
        name="linkedin_get_post_stats",
        description="Get engagement statistics (impressions, clicks, likes, comments, shares) for all posts or for specific post URNs.",
        inputSchema={
            "type": "object",
            "properties": {"post_urns": {"type": "array", "items": {"type": "string"}}},
        },
    ),
    Tool(
        name="linkedin_get_follower_demographics",
        description="Get follower breakdown by location, seniority, industry, company size and job function.",
        inputSchema={"type": "object", "properties": {}},
    ),
    # ── Media ─────────────────────────────────────────────────────
    Tool(
        name="linkedin_upload_image",
        description="Upload a local image (.jpg, .png, .gif; max 10 MB) and return its media_id for linkedin_create_post.",
        inputSchema={
            "type": "object",
            "properties": {
                "image_path": {
                    "type": "string",
                    "description": "Absolute path to the image file on this machine",
                }
            },
            "required": ["image_path"],
        },
    ),
    # ── Organization ──────────────────────────────────────────────
    Tool(
        name="linkedin_get_organization",
        description="Get company page details: name, description, industry, website, follower and staff counts.",
        inputSchema={"type": "object", "properties": {}},
    ),
]


async def _dispatch(client: LinkedInPagesClient, name: str, args: dict[str, Any]) -> Any:
    if name == "linkedin_create_post":
        return await client.create_post(
            text=args["text"],
            visibility=args.get("visibility", "PUBLIC"),
            article_url=args.get("article_url"),
            article_title=args.get("article_title"),
            article_description=args.get("article_description"),
            media_id=args.get("media_id"),
            media_title=args.get("media_title"),
        )
    if name == "linkedin_get_posts":
        return await client.get_posts(count=args.get("count", 10), start=args.get("start", 0))
    if name == "linkedin_get_post":
        return await client.get_post(normalize_post_urn(args["post_id"]))
    if name == "linkedin_update_post":
        return await client.update_post(normalize_post_urn(args["post_id"]), args["text"])
    if name == "linkedin_delete_post":
        return await client.delete_post(normalize_post_urn(args["post_id"]))
    if name == "linkedin_get_comments":
        return await client.get_comments(
            normalize_post_urn(args["post_urn"]),
            count=args.get("count", 10),
            start=args.get("start", 0),
        )
    if name == "linkedin_create_comment":
        return await client.create_comment(normalize_post_urn(args["post_urn"]), args["text"])
    if name == "linkedin_delete_comment":
        return await client.delete_comment(normalize_post_urn(args["post_urn"]), args["comment_id"])
    if name == "linkedin_get_reactions":
        return await client.get_reactions(
            normalize_post_urn(args["post_urn"]), count=args.get("count", 10)
        )
    if name == "linkedin_react_to_post":
        return await client.add_reaction(
            normalize_post_urn(args["post_urn"]), reaction_type=args.get("reaction_type", "LIKE")
        )
    if name == "linkedin_get_follower_stats":
        return await client.get_follower_statistics(args.get("time_granularity", "MONTH"))
    if name == "linkedin_get_page_stats":
        return await client.get_page_statistics(args.get("time_granularity", "MONTH"))
    if name == "linkedin_get_post_stats":
        urns = [normalize_post_urn(u) for u in args["post_urns"]] if args.get("post_urns") else None
        return await client.get_share_statistics(urns)
    if name == "linkedin_get_follower_demographics":
        return await client.get_follower_demographics()
    if name == "linkedin_upload_image":
        return await client.upload_image(args["image_path"])
    if name == "linkedin_get_organization":
        return await client.get_organization()
    raise LinkedInAPIError(404, f"unknown tool: {name}")


async def _handle_tool(name: str, arguments: dict[str, Any]) -> str:
    """Run one tool. Every failure comes back as a JSON error object, never a crash."""
    try:
        async with _get_client() as client:
            result = await _dispatch(client, name, arguments or {})
    except LinkedInAPIError as exc:
        log.warning("tool %s failed: %s (%s)", name, exc.message, exc.status)
        return json.dumps(exc.to_dict(), indent=2, default=str)
    except KeyError as exc:
        return json.dumps(
            {"error": f"missing required argument: {exc.args[0]}", "status": 400}, indent=2
        )
    except Exception as exc:  # last-resort guard so one bad call never kills the server
        log.exception("unexpected error in tool %s", name)
        return json.dumps(
            {"error": f"unexpected error: {type(exc).__name__}: {exc}", "status": 500}, indent=2
        )
    return json.dumps(result, indent=2, default=str)


def main() -> None:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "WARNING"))
    server = Server("linkedin-pages-mcp")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return TOOLS

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        return [TextContent(type="text", text=await _handle_tool(name, arguments))]

    async def run() -> None:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())

    asyncio.run(run())


if __name__ == "__main__":
    main()
