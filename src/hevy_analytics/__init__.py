from collections.abc import Sequence

from .mcp_server import create_mcp_server

__all__ = ["create_mcp_server", "run_mcp", "run_cli"]


def run_mcp() -> None:
    from .mcp_server import main

    main()


def run_cli(argv: Sequence[str] | None = None) -> int:
    from .cli import main

    return main(argv)
