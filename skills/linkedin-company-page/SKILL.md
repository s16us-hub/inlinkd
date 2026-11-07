---
name: linkedin-company-page
description: Manage a LinkedIn Company Page from an AI agent: draft and publish posts with approval, read comments and engagement, and report follower and post analytics. Uses the official LinkedIn Community Management API through the inlinkd MCP server. Use when the user wants to post to, moderate, or measure their LinkedIn company page.
---

# LinkedIn Company Page

Manage a LinkedIn company page through the `linkedin-pages-mcp` MCP server (package name `inlinkd` on GitHub). Every action goes through LinkedIn's official API. This skill does not scrape LinkedIn.

## Before you start

1. The user needs LinkedIn Community Management API access and an OAuth access token from an admin of the page. Access is reviewed by LinkedIn and is not automatic.
2. The MCP server must have these environment variables set by the user:
   - `LINKEDIN_ACCESS_TOKEN`
   - `LINKEDIN_ORGANIZATION_ID` (the numeric company page ID)
3. If the tools return HTTP 401 or 403, the token has expired or lacks the scope. Tell the user to re-authorize. Do not ask for the token in chat.

Never ask the user to paste a token into the conversation, and never write a token to a file.

## Tools

| Area | Tools |
|---|---|
| Posts | `linkedin_create_post`, `linkedin_get_posts`, `linkedin_get_post`, `linkedin_update_post`, `linkedin_delete_post` |
| Comments | `linkedin_get_comments`, `linkedin_create_comment`, `linkedin_delete_comment` |
| Reactions | `linkedin_get_reactions`, `linkedin_react_to_post` |
| Analytics | `linkedin_get_follower_stats`, `linkedin_get_page_stats`, `linkedin_get_post_stats`, `linkedin_get_follower_demographics` |
| Media | `linkedin_upload_image` (returns a `media_id` for a post) |
| Page | `linkedin_get_organization` |

Post IDs must be full URNs such as `urn:li:share:123`. A bare number is rejected.

## Publishing a post

Publishing is public and cannot be fully undone, so always follow this order:

1. Write the draft and show the full text to the user, including any article link or image.
2. Ask for explicit approval. "Looks good" counts. Silence does not.
3. Only after approval, call `linkedin_create_post`. If the user attached an image, call `linkedin_upload_image` first and pass the returned `media_id`.
4. Report the returned `post_id`.

Never publish because a schedule, a previous draft, or a general instruction seemed to imply it. Each post needs approval for that specific text.

Limits: 3000 characters per post, 1250 per comment, and images up to 10 MB in .jpg, .png, or .gif.

## Moderation and replies

- Read comments with `linkedin_get_comments` before replying.
- Draft every reply and get approval before calling `linkedin_create_comment`.
- Delete a comment only when the user asks for that specific comment.
- Do not store commenters' names or profile data beyond the current task. LinkedIn's API terms limit how long member data may be kept.

## Reporting analytics

- Start with `linkedin_get_follower_stats` and `linkedin_get_post_stats` for a quick summary.
- Use `DAY` granularity for recent trends and `MONTH` for long-term growth.
- Report the figures exactly as returned. If a field is missing, say so rather than estimating it.

## Errors

Tool results are JSON. An `error` field with a `status` tells you what went wrong:

- `400`: bad input. Fix the argument and retry once.
- `401` or `403`: token expired or missing scope. Stop and tell the user.
- `429`: rate limited. Wait and retry later, not in a loop.
- `5xx` or `503`: LinkedIn or the network is failing. Report it and stop after one retry.

## Things this skill does not do

- It does not edit the page's About section, logo, banner, or admin list. The LinkedIn API does not support those changes here.
- It does not run ads.
- It does not post on personal profiles.
