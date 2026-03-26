"""MCP server exposing LinkedIn Company Page management tools."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from linkedin_pages_mcp.client import LinkedInPagesClient


def _get_client() -> LinkedInPagesClient:
    token = os.environ.get("LINKEDIN_ACCESS_TOKEN", "")
    org_id = os.environ.get("LINKEDIN_ORGANIZATION_ID", "")
    if not token:
        raise ValueError("LINKEDIN_ACCESS_TOKEN environment variable is required")
    if not org_id:
        raise ValueError("LINKEDIN_ORGANIZATION_ID environment variable is required")
    return LinkedInPagesClient(access_token=token, organization_id=org_id)


TOOLS: list[Tool] = [
    # ── Posts ──────────────────────────────────────────────────────
    Tool(
        name="linkedin_create_post",
        description="Create a post on the LinkedIn company page. Supports text, articles (with URL), and media (with pre-uploaded media ID).",
        inputSchema={
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Post text/commentary (max 3000 chars)"},
                "visibility": {
                    "type": "string",
                    "enum": ["PUBLIC"],
                    "default": "PUBLIC",
                    "description": "Post visibility",
                },
                "article_url": {
                    "type": "string",
                    "description": "URL for article posts. LinkedIn will NOT auto-scrape — set article_title and article_description too.",
                },
                "article_title": {"type": "string", "description": "Title for article posts"},
                "article_description": {"type": "string", "description": "Description for article posts"},
                "media_id": {"type": "string", "description": "Pre-uploaded media URN for image/video posts"},
                "media_title": {"type": "string", "description": "Title for media posts"},
            },
            "required": ["text"],
        },
    ),
    Tool(
        name="linkedin_get_posts",
        description="List recent posts from the company page. Returns post IDs, text, engagement counts, and timestamps.",
        inputSchema={
            "type": "object",
            "properties": {
                "count": {"type": "integer", "default": 10, "description": "Number of posts to return (max 100)"},
                "start": {"type": "integer", "default": 0, "description": "Pagination offset"},
            },
        },
    ),
    Tool(
        name="linkedin_get_post",
        description="Get a single post by ID with full details.",
        inputSchema={
            "type": "object",
            "properties": {
                "post_id": {"type": "string", "description": "The post URN or ID"},
            },
            "required": ["post_id"],
        },
    ),
    Tool(
        name="linkedin_update_post",
        description="Update the text/commentary of an existing post.",
        inputSchema={
            "type": "object",
            "properties": {
                "post_id": {"type": "string", "description": "The post URN or ID"},
                "text": {"type": "string", "description": "New post text"},
            },
            "required": ["post_id", "text"],
        },
    ),
    Tool(
        name="linkedin_delete_post",
        description="Delete a post from the company page.",
        inputSchema={
            "type": "object",
            "properties": {
                "post_id": {"type": "string", "description": "The post URN or ID to delete"},
            },
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
                "post_urn": {"type": "string", "description": "The post URN"},
                "count": {"type": "integer", "default": 10, "description": "Number of comments to return"},
                "start": {"type": "integer", "default": 0, "description": "Pagination offset"},
            },
            "required": ["post_urn"],
        },
    ),
    Tool(
        name="linkedin_create_comment",
        description="Post a comment on behalf of the company page.",
        inputSchema={
            "type": "object",
            "properties": {
                "post_urn": {"type": "string", "description": "The post URN to comment on"},
                "text": {"type": "string", "description": "Comment text"},
            },
            "required": ["post_urn", "text"],
        },
    ),
    Tool(
        name="linkedin_delete_comment",
        description="Delete a comment from a post.",
        inputSchema={
            "type": "object",
            "properties": {
                "post_urn": {"type": "string", "description": "The post URN"},
                "comment_id": {"type": "string", "description": "The comment ID to delete"},
            },
            "required": ["post_urn", "comment_id"],
        },
    ),
    # ── Reactions ─────────────────────────────────────────────────
    Tool(
        name="linkedin_get_reactions",
        description="Get reactions on a post (likes, celebrates, etc.).",
        inputSchema={
            "type": "object",
            "properties": {
                "post_urn": {"type": "string", "description": "The post URN"},
                "count": {"type": "integer", "default": 10, "description": "Number of reactions to return"},
            },
            "required": ["post_urn"],
        },
    ),
    Tool(
        name="linkedin_react_to_post",
        description="Add a reaction to a post on behalf of the company page.",
        inputSchema={
            "type": "object",
            "properties": {
                "post_urn": {"type": "string", "description": "The post URN to react to"},
                "reaction_type": {
                    "type": "string",
                    "enum": ["LIKE", "PRAISE", "EMPATHY", "INTEREST", "APPRECIATION"],
                    "default": "LIKE",
                    "description": "Reaction type",
                },
            },
            "required": ["post_urn"],
        },
    ),
    # ── Analytics ─────────────────────────────────────────────────
    Tool(
        name="linkedin_get_follower_stats",
        description="Get follower statistics for the company page — counts, growth, and demographics (location, seniority, industry, company size, job function).",
        inputSchema={
            "type": "object",
            "properties": {
                "time_granularity": {
                    "type": "string",
                    "enum": ["DAY", "MONTH"],
                    "default": "MONTH",
                    "description": "Time granularity for stats",
                },
            },
        },
    ),
    Tool(
        name="linkedin_get_page_stats",
        description="Get page view and click statistics for the company page.",
        inputSchema={
            "type": "object",
            "properties": {
                "time_granularity": {
                    "type": "string",
                    "enum": ["DAY", "MONTH"],
                    "default": "MONTH",
                    "description": "Time granularity for stats",
                },
            },
        },
    ),
    Tool(
        name="linkedin_get_post_stats",
        description="Get engagement statistics (impressions, clicks, likes, comments, shares) aggregated across posts or for specific post URNs.",
        inputSchema={
            "type": "object",
            "properties": {
                "post_urns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of specific post URNs to get stats for. Omit for aggregate.",
                },
            },
        },
    ),
    Tool(
        name="linkedin_get_follower_demographics",
        description="Get follower demographics breakdown — location, seniority, industry, company size, job function.",
        inputSchema={"type": "object", "properties": {}},
    ),
    # ── Media ─────────────────────────────────────────────────────
    Tool(
        name="linkedin_init_image_upload",
        description="Initialize an image upload to LinkedIn. Returns an upload URL and media URN. After uploading the image binary to the URL, use the media URN in linkedin_create_post.",
        inputSchema={"type": "object", "properties": {}},
    ),
    # ── Organization ──────────────────────────────────────────────
    Tool(
        name="linkedin_get_organization",
        description="Get company page details — name, description, industry, website, follower count, staff count.",
        inputSchema={"type": "object", "properties": {}},
    ),
]


async def _handle_tool(name: str, arguments: dict[str, Any]) -> str:
    client = _get_client()
    try:
        if name == "linkedin_create_post":
            result = await client.create_post(
                text=arguments["text"],
                visibility=arguments.get("visibility", "PUBLIC"),
                article_url=arguments.get("article_url"),
                article_title=arguments.get("article_title"),
                article_description=arguments.get("article_description"),
                media_id=arguments.get("media_id"),
                media_title=arguments.get("media_title"),
            )
        elif name == "linkedin_get_posts":
            result = await client.get_posts(
                count=arguments.get("count", 10),
                start=arguments.get("start", 0),
            )
        elif name == "linkedin_get_post":
            result = await client.get_post(arguments["post_id"])
        elif name == "linkedin_update_post":
            result = await client.update_post(arguments["post_id"], arguments["text"])
        elif name == "linkedin_delete_post":
            result = await client.delete_post(arguments["post_id"])
        elif name == "linkedin_get_comments":
            result = await client.get_comments(
                post_urn=arguments["post_urn"],
                count=arguments.get("count", 10),
                start=arguments.get("start", 0),
            )
        elif name == "linkedin_create_comment":
            result = await client.create_comment(arguments["post_urn"], arguments["text"])
        elif name == "linkedin_delete_comment":
            result = await client.delete_comment(arguments["post_urn"], arguments["comment_id"])
        elif name == "linkedin_get_reactions":
            result = await client.get_reactions(
                post_urn=arguments["post_urn"],
                count=arguments.get("count", 10),
            )
        elif name == "linkedin_react_to_post":
            result = await client.add_reaction(
                post_urn=arguments["post_urn"],
                reaction_type=arguments.get("reaction_type", "LIKE"),
            )
        elif name == "linkedin_get_follower_stats":
            result = await client.get_follower_statistics(
                time_granularity=arguments.get("time_granularity", "MONTH"),
            )
        elif name == "linkedin_get_page_stats":
            result = await client.get_page_statistics(
                time_granularity=arguments.get("time_granularity", "MONTH"),
            )
        elif name == "linkedin_get_post_stats":
            result = await client.get_share_statistics(
                shares=arguments.get("post_urns"),
            )
        elif name == "linkedin_get_follower_demographics":
            result = await client.get_follower_demographics()
        elif name == "linkedin_init_image_upload":
            result = await client.initialize_image_upload()
        elif name == "linkedin_get_organization":
            result = await client.get_organization()
        else:
            result = {"error": f"Unknown tool: {name}"}
        return json.dumps(result, indent=2, default=str)
    finally:
        await client.close()


def main() -> None:
    server = Server("linkedin-pages-mcp")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return TOOLS

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        result = await _handle_tool(name, arguments)
        return [TextContent(type="text", text=result)]

    async def run() -> None:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())

    asyncio.run(run())


if __name__ == "__main__":
    main()
