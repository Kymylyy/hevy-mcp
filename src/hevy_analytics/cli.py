from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, cast

from .bootstrap import build_service, close_service
from .config import DEFAULT_RECENT_WORKOUTS_LIMIT
from .response import ToolResult, render_markdown, result_to_dict
from .service import HevyService
from .tools import (
    exercise_progression,
    fatigue_check,
    get_routines,
    recent_workouts,
    search_exercise,
    suggest_accessories,
    top_exercises,
    training_log,
    weekly_volume,
)

Handler = Callable[[HevyService, argparse.Namespace], ToolResult]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hevy-cli",
        description="Export Hevy analytics through the shared core used by MCP.",
    )
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--output", choices=("json", "markdown"), default="json")
    common.add_argument("--out", type=Path, help="Write output to a file instead of stdout.")
    common.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    common.add_argument(
        "--fail-on-no-data",
        action="store_true",
        help="Exit non-zero when the command returns status=no_data.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    search_parser = subparsers.add_parser("search-exercise", parents=[common])
    search_parser.add_argument("--name", required=True)
    search_parser.set_defaults(handler=_handle_search_exercise)

    progression_parser = subparsers.add_parser("exercise-progression", parents=[common])
    progression_parser.add_argument("--name", required=True)
    progression_parser.add_argument("--weeks", type=int, default=12)
    progression_parser.set_defaults(handler=_handle_exercise_progression)

    workouts_parser = subparsers.add_parser("recent-workouts", parents=[common])
    workouts_parser.add_argument("--days", type=int, default=7)
    workouts_parser.add_argument("--limit", type=int, default=DEFAULT_RECENT_WORKOUTS_LIMIT)
    workouts_parser.set_defaults(handler=_handle_recent_workouts)

    volume_parser = subparsers.add_parser("weekly-volume", parents=[common])
    volume_parser.add_argument("--weeks", type=int, default=4)
    volume_parser.set_defaults(handler=_handle_weekly_volume)

    fatigue_parser = subparsers.add_parser("fatigue-check", parents=[common])
    fatigue_parser.set_defaults(handler=_handle_fatigue_check)

    accessories_parser = subparsers.add_parser("suggest-accessories", parents=[common])
    accessories_parser.set_defaults(handler=_handle_suggest_accessories)

    log_parser = subparsers.add_parser("training-log", parents=[common])
    log_parser.add_argument("--days", type=int, default=30)
    log_parser.set_defaults(handler=_handle_training_log)

    top_parser = subparsers.add_parser("top-exercises", parents=[common])
    top_parser.add_argument("--days", type=int, default=30)
    top_parser.add_argument("--limit", type=int, default=5)
    top_parser.set_defaults(handler=_handle_top_exercises)

    routines_parser = subparsers.add_parser("get-routines", parents=[common])
    routines_parser.set_defaults(handler=_handle_get_routines)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        service = build_service()
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1

    try:
        handler = cast(Handler, args.handler)
        result = handler(service, args)
        rendered = _render_output(result, output_format=args.output, pretty=args.pretty)
        _write_output(rendered, destination=args.out)
        return _exit_code(result, fail_on_no_data=args.fail_on_no_data)
    except OSError as exc:
        print(f"Failed to write output: {exc}", file=sys.stderr)
        return 1
    finally:
        close_service(service)


def _execute(
    service: HevyService,
    tool_name: str,
    fn: Callable[..., ToolResult],
    *args: Any,
) -> ToolResult:
    return service.execute(tool_name, fn, *args)


def _handle_search_exercise(service: HevyService, args: argparse.Namespace) -> ToolResult:
    return _execute(
        service,
        "search_exercise",
        lambda name: search_exercise(service, name),
        args.name,
    )


def _handle_exercise_progression(service: HevyService, args: argparse.Namespace) -> ToolResult:
    return _execute(
        service,
        "exercise_progression",
        lambda name, weeks: exercise_progression(service, name, weeks),
        args.name,
        args.weeks,
    )


def _handle_recent_workouts(service: HevyService, args: argparse.Namespace) -> ToolResult:
    return _execute(
        service,
        "recent_workouts",
        lambda days, limit: recent_workouts(service, days, limit),
        args.days,
        args.limit,
    )


def _handle_weekly_volume(service: HevyService, args: argparse.Namespace) -> ToolResult:
    return _execute(
        service,
        "weekly_volume",
        lambda weeks: weekly_volume(service, weeks),
        args.weeks,
    )


def _handle_fatigue_check(service: HevyService, args: argparse.Namespace) -> ToolResult:
    return _execute(service, "fatigue_check", lambda: fatigue_check(service))


def _handle_suggest_accessories(service: HevyService, args: argparse.Namespace) -> ToolResult:
    return _execute(service, "suggest_accessories", lambda: suggest_accessories(service))


def _handle_training_log(service: HevyService, args: argparse.Namespace) -> ToolResult:
    return _execute(service, "training_log", lambda days: training_log(service, days), args.days)


def _handle_top_exercises(service: HevyService, args: argparse.Namespace) -> ToolResult:
    return _execute(
        service,
        "top_exercises",
        lambda days, limit: top_exercises(service, days, limit),
        args.days,
        args.limit,
    )


def _handle_get_routines(service: HevyService, args: argparse.Namespace) -> ToolResult:
    return _execute(service, "get_routines", lambda: get_routines(service))


def _render_output(result: ToolResult, *, output_format: str, pretty: bool) -> str:
    if output_format == "markdown":
        return render_markdown(result) + "\n"
    if output_format == "json":
        indent = 2 if pretty else None
        separators = None if pretty else (",", ":")
        return json.dumps(result_to_dict(result), indent=indent, separators=separators) + "\n"
    raise ValueError(f"Unsupported output format: {output_format}")


def _write_output(rendered: str, *, destination: Path | None) -> None:
    if destination is None:
        sys.stdout.write(rendered)
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(rendered, encoding="utf-8")


def _exit_code(result: ToolResult, *, fail_on_no_data: bool) -> int:
    if result.status == "error":
        return 1
    if result.status == "no_data" and fail_on_no_data:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
