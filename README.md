# hevy-mcp

MCP server for personal Hevy training analytics.

## Features

- `search_exercise(name)`
- `exercise_progression(name, weeks=12)`
- `recent_workouts(days=7)`
- `weekly_volume(weeks=4)`
- `fatigue_check()`
- `suggest_accessories()`
- `training_log(days=30)`
- `get_routines()`

All tools return markdown with a stable response structure:

- `## Summary`
- `## Data Window`
- `## Details`
- `## Notes`

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

Set API key in environment:

```bash
export HEVY_API_KEY="your-key"
```

Or keep it in local `.env` (ignored by git):

```bash
set -a
source .env
set +a
```

Run MCP server:

```bash
python3 run_hevy_mcp.py
```

## Claude Desktop / Claude Code config

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

## Development checks

Run checks in this order:

```bash
python3 -m ruff check .
python3 -m mypy src tests
python3 -m pytest
```

## Notes

- Server is read-only (GET endpoints only).
- Secrets are loaded from environment; do not commit local API key files.
- Fuzzy matching uses Python `difflib` to avoid extra runtime dependencies.
- `search_exercise` boosts matches for exercises seen in recent workout history.
- `get_routines` includes per-exercise set schemes (set type, reps/load, RIR/rest when available).
