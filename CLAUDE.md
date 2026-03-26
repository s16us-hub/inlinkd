# CLAUDE.md — linkedin-pages-mcp

MCP server for LinkedIn Company Page management via the official Community Management API. MIT licensed.

## Commands

```bash
pip install -e ".[dev]"        # Install with dev deps
pytest tests/ -v               # Run tests
black src/ tests/              # Format
ruff check src/ tests/         # Lint
mypy src/                      # Type check
```

## Run

```bash
export LINKEDIN_ACCESS_TOKEN="ya29.xxx"
export LINKEDIN_ORGANIZATION_ID="111806031"
linkedin-pages-mcp             # stdio mode
python -m linkedin_pages_mcp   # alternative
```

## Structure

```
src/linkedin_pages_mcp/
  __init__.py       # Version
  __main__.py       # Entry point
  client.py         # LinkedIn API HTTP client
  server.py         # MCP server + tool definitions
```

## LinkedIn API

- Base: `https://api.linkedin.com/rest`
- Auth: OAuth 2.0 bearer token (3-legged, user must be page admin)
- Version header: `LinkedIn-Version: 202503`
- Docs: https://learn.microsoft.com/en-us/linkedin/marketing/community-management/

## Tools (16)

**Posts:** create, list, get, update, delete
**Comments:** list, create, delete
**Reactions:** list, add
**Analytics:** follower stats, page stats, post stats, follower demographics
**Media:** initialize image upload
**Organization:** get company details

## Do NOT

- Store LinkedIn member data beyond 48 hours (API policy)
- Auto-post without user intent (spam risk, ToS violation)
- Use unofficial/scraping libraries (this uses the official API only)
