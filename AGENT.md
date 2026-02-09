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

## Security Recommendations

- Apply defense-in-depth: validate inputs at API boundaries and again before internal use.
- Never trust user input: treat all third-party data as attacker-controlled.
- Minimize attack surface: avoid exposing passthrough URLs or file paths without allowlists.
- Enforce least privilege: scope credentials to the minimum required and avoid reusing user-supplied tokens across requests.
- Validate inputs against strict schemas (type, length, charset); reject early with clear errors.
- Sanitize strings before use in interpreted contexts (URLs, file paths, queries).
- Use cryptography for data in transit and at rest when needed.
- Handle internal errors defensively: no stack traces to clients; return safe, structured errors.
- Separate concerns: isolate networking, storage, and auth logic into distinct modules.
- Keep security layers usable: defaults should be safe without breaking common workflows.
