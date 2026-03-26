# linkedin-pages-mcp

MCP server for managing LinkedIn Company Pages via the official [Community Management API](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/community-management-overview). Post content, manage comments, track analytics, and more — all through the Model Context Protocol.

**This is the first MCP server for LinkedIn Company Page management using LinkedIn's official API.**

## Features

| Category | Tools |
|----------|-------|
| **Posts** | Create, list, get, update, delete posts (text, images, articles, polls) |
| **Comments** | Read, create, and delete comments on behalf of the company page |
| **Reactions** | Read reactions, react to posts (LIKE, PRAISE, EMPATHY, INTEREST, APPRECIATION) |
| **Analytics** | Follower stats and demographics, page views/clicks, per-post engagement |
| **Media** | Initialize image uploads for rich media posts |
| **Organization** | Get company page details (name, industry, website, staff count) |

16 tools total. All using LinkedIn's official REST API with proper OAuth 2.0 authentication.

## Prerequisites

1. A [LinkedIn Developer Application](https://developer.linkedin.com/) associated with your company page
2. **Community Management API** product enabled (apply via the Products tab)
3. An OAuth 2.0 access token from a user who is an admin of the company page
4. Your LinkedIn Organization ID (the numeric ID from your company page URL)

### Getting your Organization ID

Your company page URL looks like `https://www.linkedin.com/company/111806031/` — the number is your Organization ID.

### Getting an access token

LinkedIn uses 3-legged OAuth 2.0. You need these scopes:

- `w_organization_social` — post and comment on behalf of the company
- `r_organization_social` — read posts, comments, and engagement
- `rw_organization_admin` — manage page and read analytics

See [LinkedIn OAuth documentation](https://learn.microsoft.com/en-us/linkedin/shared/authentication/authentication) for the full flow.

## Installation

```bash
pip install linkedin-pages-mcp
```

Or from source:

```bash
git clone https://github.com/MCPWorks-Technologies-Inc/linkedin-pages-mcp.git
cd linkedin-pages-mcp
pip install -e .
```

## Configuration

Set environment variables:

```bash
export LINKEDIN_ACCESS_TOKEN="your-oauth-token"
export LINKEDIN_ORGANIZATION_ID="111806031"
```

Or create a `.env` file (see `.env.example`).

## Usage

### With Claude Code / Cursor / any MCP client (stdio)

Add to your `.mcp.json`:

```json
{
  "mcpServers": {
    "linkedin-pages": {
      "command": "linkedin-pages-mcp",
      "env": {
        "LINKEDIN_ACCESS_TOKEN": "your-oauth-token",
        "LINKEDIN_ORGANIZATION_ID": "111806031"
      }
    }
  }
}
```

Then ask your AI assistant:

> "Post an update to our LinkedIn company page about our latest release"

> "Show me our LinkedIn page analytics for this month"

> "Reply to the latest comments on our most recent post"

### With MCPWorks (remote, token-efficient)

Add as an MCP server plugin on your MCPWorks namespace:

> "Add the LinkedIn Pages MCP server to my namespace"

Then your MCPWorks functions can call LinkedIn tools from inside the sandbox:

```python
from functions import mcp__linkedin_pages__linkedin_get_posts
from functions import mcp__linkedin_pages__linkedin_get_follower_stats

posts = mcp__linkedin_pages__linkedin_get_posts(count=5)
stats = mcp__linkedin_pages__linkedin_get_follower_stats(time_granularity="MONTH")

top_post = max(posts['elements'], key=lambda p: p.get('engagement', 0))
result = {
    'followers': stats.get('followerCount'),
    'top_post': top_post.get('commentary', '')[:100],
    'total_posts': len(posts['elements']),
}
```

All LinkedIn data stays in the sandbox. Only the summary returns to the AI context.

## Available Tools

### Posts

| Tool | Description |
|------|-------------|
| `linkedin_create_post` | Create a text, article, or media post on the company page |
| `linkedin_get_posts` | List recent posts (paginated, sorted by last modified) |
| `linkedin_get_post` | Get a single post by ID |
| `linkedin_update_post` | Update post text/commentary |
| `linkedin_delete_post` | Delete a post |

### Comments

| Tool | Description |
|------|-------------|
| `linkedin_get_comments` | Get comments on a post |
| `linkedin_create_comment` | Comment on a post as the company page |
| `linkedin_delete_comment` | Delete a comment |

### Reactions

| Tool | Description |
|------|-------------|
| `linkedin_get_reactions` | Get reactions on a post |
| `linkedin_react_to_post` | React to a post as the company page |

### Analytics

| Tool | Description |
|------|-------------|
| `linkedin_get_follower_stats` | Follower counts and growth over time |
| `linkedin_get_page_stats` | Page views and clicks |
| `linkedin_get_post_stats` | Per-post engagement (impressions, clicks, likes, comments, shares) |
| `linkedin_get_follower_demographics` | Follower breakdown by location, seniority, industry, company size |

### Media

| Tool | Description |
|------|-------------|
| `linkedin_init_image_upload` | Get an upload URL and media URN for image posts |

### Organization

| Tool | Description |
|------|-------------|
| `linkedin_get_organization` | Get company page details |

## LinkedIn API Limits

| Tier | Calls/App/Day | Calls/Member/Day | Webhooks |
|------|---------------|-------------------|----------|
| Development | 500 | 100 | No |
| Standard | Unrestricted | Unrestricted | Yes |

Development tier is granted on application. Standard tier requires a video demo review by LinkedIn (~60 days).

## License

MIT License. See [LICENSE](LICENSE).

Built by [MCPWorks Technologies Inc.](https://mcpworks.io)
