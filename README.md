# hevy-mcp

[![CI](https://github.com/Kymylyy/hevy-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/Kymylyy/hevy-mcp/actions/workflows/ci.yml)

`hevy-mcp` is a read-only MCP server for Hevy training analytics.
It exposes focused tools for exercise search, progression analysis, workout summaries,
volume distribution, fatigue signals, accessory suggestions, training logging, and routine inspection.

## Features

- `search_exercise(name)`
- `exercise_progression(name, weeks=12)`
- `recent_workouts(days=7)`
- `weekly_volume(weeks=4)`
- `fatigue_check()`
- `suggest_accessories()`
- `training_log(days=30)`
- `top_exercises(days=30, limit=5)`
- `get_routines()`

All tools return markdown with a stable section contract:

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
hevy-mcp
```

You can also run:

```bash
python3 run_hevy_mcp.py
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

## Constraints

- Read-only integration (GET-oriented API usage).
- Input guards:
  - `days`: `1..365`
  - `weeks`: `1..52`
  - `limit`: `≥ 1`
  - `name`: minimum 2 characters
- Fuzzy matching uses `difflib` (no external fuzzy dependency).

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
