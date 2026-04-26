# hevy-analytics

[![CI](https://github.com/Kymylyy/hevy-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/Kymylyy/hevy-mcp/actions/workflows/ci.yml)

`hevy-analytics` is a shared Hevy analytics core with two adapters:
- `hevy-mcp` for LLM and MCP-compatible clients
- `hevy-cli` for cronjobs, automation, and dashboard ingestion

It exposes focused tools for exercise search, progression analysis, workout summaries,
volume distribution, fatigue signals, accessory suggestions, training logging, and routine inspection.

## Architecture

- `hevy_analytics.service` and related modules contain the analytics core.
- `hevy_analytics.mcp_server` renders the existing markdown contract for MCP clients.
- `hevy_analytics.cli` exposes the same capabilities for automation with `json` or `markdown` output.

## Features

- `search_exercise(name)`
- `exercise_progression(name, weeks=12)`
- `recent_workouts(days=7, limit=30)`
- `weekly_volume(weeks=4)`
- `fatigue_check()`
- `suggest_accessories()`
- `training_log(days=30)`
- `top_exercises(days=30, limit=5)`
- `get_routines()`

MCP tools return markdown with a stable section contract:

- `## Summary`
- `## Data Window`
- `## Details`
- `## Notes`

## Requirements

- Python 3.11+
- Hevy API key

## Quickstart

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
export HEVY_API_KEY="your-key"
```

### MCP

```bash
hevy-mcp
```

Compatibility wrapper:

```bash
python3 run_hevy_mcp.py
```

### CLI

```bash
hevy-cli recent-workouts --days 14 --output json --pretty
hevy-cli weekly-volume --weeks 6 --output markdown
hevy-cli training-log --days 30 --out data/training-log.json
```

## MCP Configuration Example

```json
{
  "mcpServers": {
    "hevy": {
      "command": "python3",
      "args": ["/absolute/path/to/run_hevy_mcp.py"],
      "env": {
        "HEVY_API_KEY": "your-key"
      }
    }
  }
}
```

## CLI Output

- Default output is `json` for automation and cronjobs.
- `--output markdown` preserves the human-readable MCP-style rendering.
- `--out PATH` writes snapshots directly to a file for downstream ingestion.
- `--fail-on-no-data` exits non-zero when a command returns `status=no_data`.
- Exit codes: `0` for success, `1` for errors, `3` for `no_data` when `--fail-on-no-data` is set.

## Cron Example

```cron
0 6 * * * cd /absolute/path/to/hevy-mcp && /absolute/path/to/.venv/bin/hevy-cli recent-workouts --days 2 --out data/recent-workouts.json --pretty
15 6 * * * cd /absolute/path/to/hevy-mcp && /absolute/path/to/.venv/bin/hevy-cli weekly-volume --weeks 4 --out data/weekly-volume.json --pretty
```

## Constraints

- Read-only integration (GET-oriented API usage).
- Input guards:
  - `days`: `1..365`
  - `weeks`: `1..52`
  - `limit`: `≥ 1`
  - `name`: minimum 2 characters
- Fuzzy matching uses `difflib` (no external fuzzy dependency).

## Migration Notes

- Python package changed from `hevy_mcp` to `hevy_analytics`.
- Distribution name changed from `hevy-mcp` to `hevy-analytics`.
- `hevy-mcp` remains the MCP executable for compatibility.
- New automation entrypoint: `hevy-cli`.
- `run_hevy_mcp.py` remains as a thin compatibility wrapper.

## Development

Run checks in this order:

```bash
python3 -m ruff check .
python3 -m mypy src tests
python3 -m pytest
```

GitHub Actions runs these checks on `push` and `pull_request`.

## Security

If you find a security issue, follow `/SECURITY.md`.
Do not open public issues for secrets or vulnerabilities.

## License

MIT. See `/LICENSE`.
