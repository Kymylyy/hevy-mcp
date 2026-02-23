# Project Notes

## Purpose

Build a focused MCP server for Hevy data analysis with a small, stable tool surface.

## Architecture

- Runtime: Python 3.12
- MCP layer: FastMCP
- API client: httpx with retry/backoff and user-safe error mapping
- Core services:
  - `hevy_mcp.client.HevyApiClient`
  - `hevy_mcp.service.HevyService`
  - `hevy_mcp.tools` (8 tools)

## Data/behavior contracts

- All tools return markdown sections in fixed order.
- Input guards:
  - `days`: `1..365`
  - `weeks`: `1..52`
  - `name`: min length 2
- Retry policy: up to 3 retries for `429` and `5xx`.
- Caching:
  - templates: 12h
  - search results: 12h
  - exercise history: 5m

## Operational assumptions

- Read-only v1 (no write endpoints).
- UTC internally for filtering windows.
- `HEVY_API_KEY` required at startup.

## Implementation notes

- Fuzzy search uses `difflib.SequenceMatcher`.
- Tool logs are emitted as JSON to stderr.
- If output grows too large, tools truncate low-priority rows.
