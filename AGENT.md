# GitHub Copilot Agent Instructions

This repository contains the FreeFeed MCP server (Python, FastAPI, MCP stdio).

## Expectations

- Keep tracking changes in [CHANGELOG.md]
- Update [API.md] is anything changed in [freefeed_mcp_server/api.py]
- Prefer minimal, targeted edits; keep behavior changes explicit
- Favor existing patterns in `freefeed_mcp_server/`

## Key Paths

- MCP server: `freefeed_mcp_server/server.py`
- REST API: `freefeed_mcp_server/api.py`
- API client: `freefeed_mcp_server/client.py`
- Docs: `README.md`, `API.md`, `FEATURES.md`, `SKILL.md`

## Local Run Commands

- MCP server: `python -m freefeed_mcp_server`
- REST API: `python -m freefeed_mcp_server.api`
- Uvicorn: `uvicorn freefeed_mcp_server.api:app --reload`

## Tests

- Pytest: `pytest`

## Logging

- Controlled via `LOG_LEVEL` (default `INFO`)
- Logs may be written to `./logs/freefeed_server.log` and `./logs/freefeed_client.log`

## Conventions

- Use Pydantic models for request/response schemas
- Prefer returning structured JSON for tool outputs
- When adding MCP tools, update docs and examples
