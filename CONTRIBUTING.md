# Contributing

Thanks for your interest in `hevy-analytics`.

## Development setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

Set your local API key (never commit secrets):

```bash
export HEVY_API_KEY="your-key"
```

## Quality gates

Run before opening a pull request:

```bash
python3 -m ruff check .
python3 -m mypy src tests
python3 -m pytest
```

## Pull request expectations

- Keep changes scoped and reviewable.
- Include tests for behavior changes.
- Update docs when behavior or interfaces change.
- Keep MCP tool names stable unless a breaking change is intentionally documented.
- Keep CLI JSON output stable once shipped.

## Commit style

Use Conventional Commit prefixes:

- `feat`
- `fix`
- `refactor`
- `docs`
- `test`
- `chore`
