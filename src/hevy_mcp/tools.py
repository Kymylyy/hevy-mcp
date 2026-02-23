from __future__ import annotations

from collections import Counter, defaultdict
from datetime import timedelta
from statistics import mean, median
from typing import Any

from .analytics import classify_trend, fatigue_risk_level
from .config import (
    MAX_ROUTINE_EXERCISES_OUTPUT,
    MAX_WORKOUT_ROWS_OUTPUT,
    SEARCH_HISTORY_LOOKBACK_DAYS,
    SEARCH_MATCH_CANDIDATES,
)
from .errors import NoDataError, NotFoundError
from .response import render_response
from .service import HevyService
from .utils import (
    estimate_e1rm,
    format_number,
    format_set,
    is_working_set,
    normalize_text,
    parse_iso_datetime,
    utc_now,
)


def search_exercise(service: HevyService, name: str) -> str:
    query = service.validate_name(name)
    candidates = service.rank_templates(query, limit=SEARCH_MATCH_CANDIDATES)
    usage = service.load_recent_template_usage(SEARCH_HISTORY_LOOKBACK_DAYS)
    matches = _rerank_matches_with_history(query, candidates, usage)[:5]
    if not matches:
        raise NotFoundError(
            f"No exercise found for '{query}'.",
            "Use a broader keyword, for example 'squat' instead of a long variant.",
        )

    details = [
        "| title | id | type | primary muscle | equipment | recent sets | custom |",
        "|---|---|---|---|---|---|---|",
    ]
    for match in matches:
        recent_sets = usage.get(str(match.get("id", "")), 0)
        details.append(
            (
                "| {title} | {id} | {type} | {primary} | {equipment} | {recent_sets} | {custom} |"
            ).format(
                title=match.get("title", "-"),
                id=match.get("id", "-"),
                type=match.get("type", "-"),
                primary=match.get("primary_muscle_group", "-"),
                equipment=match.get("equipment", "-"),
                recent_sets=recent_sets if recent_sets else "-",
                custom="yes" if match.get("is_custom") else "no",
            )
        )

    top = matches[0]
    summary = (
        f"Found {len(matches)} match(es) for '{query}'. "
        f"Best match: {top.get('title', 'unknown')} ({top.get('id', '-')})."
    )
    notes = [
        (
            "- Matching order: exact match -> recent user history boost "
            f"({SEARCH_HISTORY_LOOKBACK_DAYS}d) -> text similarity (difflib)."
        )
    ]
    return render_response(summary, "Exercise catalog snapshot (cached up to 12h).", details, notes)


def exercise_progression(service: HevyService, name: str, weeks: int = 12) -> str:
    query = service.validate_name(name)
    requested_weeks = service.validate_weeks(weeks)
    matches = service.rank_templates(query)
    if not matches:
        raise NotFoundError(
            f"No exercise found for '{query}'.",
            "Use search_exercise first to confirm template naming.",
        )

    selected = matches[0]
    template_id = str(selected.get("id", ""))
    history = service.load_history(template_id)
    if not history:
        raise NoDataError(
            f"No exercise history available for {selected.get('title', template_id)}.",
            "Log at least one workout for this exercise and retry.",
        )

    now = utc_now()
    start = now - timedelta(weeks=requested_weeks)
    filtered: list[dict[str, Any]] = []
    for row in history:
        start_raw = row.get("workout_start_time")
        if not isinstance(start_raw, str):
            continue
        if parse_iso_datetime(start_raw) < start:
            continue
        if not is_working_set(row.get("set_type")):
            continue
        if row.get("weight_kg") is None and row.get("reps") is None:
            continue
        filtered.append(row)

    if not filtered:
        raise NoDataError(
            "No working sets found in the requested time window.",
            "Increase weeks or choose another exercise.",
        )

    sessions: dict[str, dict[str, Any]] = {}
    for row in filtered:
        workout_id = str(row.get("workout_id", "unknown-workout"))
        bucket = sessions.setdefault(
            workout_id,
            {
                "title": row.get("workout_title", "Workout"),
                "start": parse_iso_datetime(str(row.get("workout_start_time"))),
                "sets": [],
            },
        )
        bucket["sets"].append(row)

    ordered = sorted(sessions.values(), key=lambda item: item["start"])
    session_best_e1rm: list[float] = []
    weekly_best: dict[str, float] = {}
    best_row: dict[str, Any] | None = None
    best_score = -1.0
    pr_load = 0.0
    pr_reps = 0
    pr_e1rm = 0.0

    for session in ordered:
        local_best = 0.0
        for row in session["sets"]:
            weight = row.get("weight_kg")
            reps = row.get("reps")
            e1rm = estimate_e1rm(weight, reps)
            if e1rm is not None:
                pr_e1rm = max(pr_e1rm, e1rm)
                local_best = max(local_best, e1rm)
            if isinstance(weight, (int, float)):
                pr_load = max(pr_load, float(weight))
            if isinstance(reps, (int, float)):
                pr_reps = max(pr_reps, int(reps))

            score = (e1rm or 0.0) + float(weight or 0.0) * 0.01 + float(reps or 0.0) * 0.001
            if score > best_score:
                best_score = score
                best_row = row

        if local_best > 0:
            session_best_e1rm.append(local_best)
            week_key = str(session["start"].date() - timedelta(days=session["start"].weekday()))
            weekly_best[week_key] = max(local_best, weekly_best.get(week_key, 0.0))

    trend_label, trend_change = classify_trend(session_best_e1rm)
    trend_suffix = f" ({format_number(trend_change, 1)}%)" if trend_change is not None else ""
    best_set_text = format_set(best_row) if best_row is not None else "n/a"

    summary = (
        f"{selected.get('title', query)} trend: {trend_label}{trend_suffix}. "
        f"Best set in window: {best_set_text}."
    )
    window = (
        f"Last {requested_weeks} week(s): {start.date()} to {now.date()} | "
        f"sessions: {len(ordered)} | sets: {len(filtered)}"
    )

    details = [
        f"- PR load: {format_number(pr_load)}kg" if pr_load else "- PR load: n/a",
        f"- PR reps: {pr_reps}" if pr_reps else "- PR reps: n/a",
        f"- Peak e1RM: {format_number(pr_e1rm)}kg" if pr_e1rm else "- Peak e1RM: n/a",
        "- Weekly best e1RM:",
    ]
    for week in sorted(weekly_best.keys())[-8:]:
        details.append(f"- {week}: {format_number(weekly_best[week])}kg")

    notes = [
        "- e1RM formula: weight * (1 + reps/30).",
        "- Only working sets are included (normal, failure, dropset).",
    ]
    return render_response(summary, window, details, notes)


def recent_workouts(service: HevyService, days: int = 7) -> str:
    requested_days = service.validate_days(days)
    now = utc_now()
    start = now - timedelta(days=requested_days)
    workouts = service.client.get_workouts_since(start)
    if not workouts:
        raise NoDataError(
            "No workouts found in the requested window.",
            "Increase days and run recent_workouts again.",
        )

    ordered = sorted(
        workouts,
        key=lambda row: parse_iso_datetime(str(row.get("start_time"))),
        reverse=True,
    )
    durations: list[float] = []
    details: list[str] = []

    for workout in ordered[:MAX_WORKOUT_ROWS_OUTPUT]:
        start_raw = workout.get("start_time")
        if not isinstance(start_raw, str):
            continue
        start_at = parse_iso_datetime(start_raw)
        end_raw = workout.get("end_time")
        duration_minutes = 0.0
        if isinstance(end_raw, str):
            duration_minutes = max(
                (parse_iso_datetime(end_raw) - start_at).total_seconds() / 60,
                0.0,
            )
            durations.append(duration_minutes)

        summaries: list[str] = []
        for exercise in workout.get("exercises", []):
            if not isinstance(exercise, dict):
                continue
            title = str(exercise.get("title", "Exercise"))
            sets = exercise.get("sets", [])
            if not isinstance(sets, list):
                continue
            candidates = [
                row
                for row in sets
                if isinstance(row, dict) and is_working_set(row.get("type"))
            ]
            ranked = sorted(
                candidates,
                key=lambda row: (
                    estimate_e1rm(row.get("weight_kg"), row.get("reps")) or 0.0,
                    float(row.get("weight_kg") or 0.0),
                    float(row.get("reps") or 0.0),
                ),
                reverse=True,
            )
            if ranked:
                summaries.append(f"{title}: {', '.join(format_set(row) for row in ranked[:2])}")

        if not summaries:
            summaries.append("no working sets logged")

        details.append(
            f"- {start_at.date()} | {workout.get('title', 'Workout')} | "
            f"{format_number(duration_minutes)} min | {'; '.join(summaries[:6])}"
        )

    avg_duration = mean(durations) if durations else 0.0
    summary = (
        f"{len(ordered)} workout(s) in last {requested_days} day(s). "
        f"Average duration: {format_number(avg_duration)} minutes."
    )
    notes = ["- Warmup sets are excluded from key-set summaries."]
    if len(ordered) > MAX_WORKOUT_ROWS_OUTPUT:
        notes.append(f"- Output truncated to {MAX_WORKOUT_ROWS_OUTPUT} workouts.")
    return render_response(summary, f"{start.date()} to {now.date()}", details, notes)


def weekly_volume(service: HevyService, weeks: int = 4) -> str:
    requested_weeks = service.validate_weeks(weeks)
    now = utc_now()
    start = now - timedelta(weeks=requested_weeks)
    workouts = service.client.get_workouts_since(start)
    if not workouts:
        raise NoDataError(
            "No workouts available in the requested period.",
            "Increase weeks and run weekly_volume again.",
        )

    templates = {str(row.get("id")): row for row in service.load_templates()}
    weekly_credits: dict[str, defaultdict[str, float]] = defaultdict(lambda: defaultdict(float))
    muscle_totals: defaultdict[str, float] = defaultdict(float)
    working_set_count = 0

    for workout in workouts:
        start_raw = workout.get("start_time")
        if not isinstance(start_raw, str):
            continue
        workout_time = parse_iso_datetime(start_raw)
        week_key = str(workout_time.date() - timedelta(days=workout_time.weekday()))

        for exercise in workout.get("exercises", []):
            if not isinstance(exercise, dict):
                continue
            template = templates.get(str(exercise.get("exercise_template_id", "")), {})
            primary = str(template.get("primary_muscle_group", "other"))
            secondaries = [
                item
                for item in template.get("secondary_muscle_groups", [])
                if isinstance(item, str)
            ]
            sets = exercise.get("sets", [])
            if not isinstance(sets, list):
                continue
            for set_row in sets:
                if not isinstance(set_row, dict) or not is_working_set(set_row.get("type")):
                    continue
                working_set_count += 1
                weekly_credits[week_key][primary] += 1.0
                muscle_totals[primary] += 1.0
                for muscle in secondaries:
                    weekly_credits[week_key][muscle] += 0.5
                    muscle_totals[muscle] += 0.5

    if working_set_count == 0:
        raise NoDataError(
            "No working sets found for volume analysis.",
            "Ensure workouts contain normal/failure/dropset entries.",
        )

    push = sum(muscle_totals[m] for m in ("chest", "shoulders", "triceps"))
    pull = sum(muscle_totals[m] for m in ("lats", "upper_back", "traps", "biceps", "forearms"))
    quads = muscle_totals["quadriceps"]
    hamstrings = muscle_totals["hamstrings"] + muscle_totals["glutes"]
    upper = sum(
        muscle_totals[m]
        for m in (
            "chest",
            "shoulders",
            "triceps",
            "lats",
            "upper_back",
            "traps",
            "biceps",
            "forearms",
        )
    )
    lower = sum(
        muscle_totals[m]
        for m in ("quadriceps", "hamstrings", "glutes", "calves", "abductors", "adductors")
    )

    def ratio(left: float, right: float) -> str:
        return "n/a" if right == 0 else format_number(left / right, 2)

    weekly_avg = sum(muscle_totals.values()) / max(requested_weeks, 1)
    sorted_muscles = sorted(muscle_totals.items(), key=lambda row: row[1], reverse=True)
    concentration = "n/a"
    if sorted_muscles:
        concentration = f"{sorted_muscles[0][0]} ({format_number(sorted_muscles[0][1])} credits)"

    details: list[str] = []
    for week in sorted(weekly_credits.keys()):
        top = sorted(weekly_credits[week].items(), key=lambda row: row[1], reverse=True)[:8]
        details.append(f"- {week}: {', '.join(f'{m}:{format_number(v)}' for m, v in top)}")
    details.extend(
        [
            f"- Push/Pull ratio: {ratio(push, pull)}",
            f"- Quad/Hamstring ratio: {ratio(quads, hamstrings)}",
            f"- Upper/Lower ratio: {ratio(upper, lower)}",
        ]
    )

    summary = (
        f"Average weekly volume: {format_number(weekly_avg)} muscle credits. "
        f"Biggest concentration: {concentration}."
    )
    notes = [
        "- Volume unit is working-set credit (primary 1.0, each secondary 0.5).",
        "- This is distribution-focused volume, not tonnage.",
    ]
    return render_response(summary, f"{start.date()} to {now.date()}", details, notes)


def fatigue_check(service: HevyService) -> str:
    now = utc_now()
    start = now - timedelta(days=21)
    workouts = service.client.get_workouts_since(start)
    if not workouts:
        raise NoDataError(
            "No recent workouts available for fatigue analysis.",
            "Log more sessions and run fatigue_check again.",
        )

    lift_keywords = {
        "squat": ("squat",),
        "hinge": ("deadlift", "rdl"),
        "press": ("bench", "press"),
        "row": ("row",),
        "vertical_pull": ("pulldown", "pull up", "pull-up", "chin"),
    }
    exposures: defaultdict[str, list[float]] = defaultdict(list)

    recent_cutoff = now - timedelta(days=7)
    recent_failure = recent_working = 0
    prior_failure = prior_working = 0
    workout_dates = []

    sorted_workouts = sorted(
        workouts,
        key=lambda row: parse_iso_datetime(str(row.get("start_time"))),
    )
    for workout in sorted_workouts:
        start_raw = workout.get("start_time")
        if not isinstance(start_raw, str):
            continue
        start_at = parse_iso_datetime(start_raw)
        workout_dates.append(start_at.date())
        bucket_recent = start_at >= recent_cutoff

        for exercise in workout.get("exercises", []):
            if not isinstance(exercise, dict):
                continue
            title = str(exercise.get("title", "")).lower()
            lift = ""
            for candidate, keywords in lift_keywords.items():
                if any(keyword in title for keyword in keywords):
                    lift = candidate
                    break

            sets = exercise.get("sets", [])
            if not isinstance(sets, list):
                continue
            top_set = 0.0
            for set_row in sets:
                if not isinstance(set_row, dict) or not is_working_set(set_row.get("type")):
                    continue
                if bucket_recent:
                    recent_working += 1
                    if set_row.get("type") == "failure":
                        recent_failure += 1
                else:
                    prior_working += 1
                    if set_row.get("type") == "failure":
                        prior_failure += 1

                e1rm = estimate_e1rm(set_row.get("weight_kg"), set_row.get("reps"))
                if e1rm is not None:
                    top_set = max(top_set, e1rm)
            if lift and top_set > 0:
                exposures[lift].append(top_set)

    signals: list[str] = []
    affected: list[str] = []

    for lift, values in exposures.items():
        if len(values) < 4:
            continue
        recent_values = values[-3:]
        baseline = values[:-3][-3:] if len(values) > 3 else values[:-3]
        if not baseline:
            continue
        baseline_avg = mean(baseline)
        recent_avg = mean(recent_values)
        if baseline_avg > 0 and (recent_avg - baseline_avg) / baseline_avg <= -0.05:
            signals.append("performance_drop")
            affected.append(lift)

    prior_ratio = (prior_failure / prior_working) if prior_working else 0.0
    recent_ratio = (recent_failure / recent_working) if recent_working else 0.0
    ratio_increase = recent_ratio - prior_ratio
    if recent_working >= 3 and (
        (
            prior_ratio > 0
            and recent_ratio >= prior_ratio * 1.3
            and ratio_increase >= 0.1
        )
        or (prior_ratio == 0 and recent_ratio >= 0.3)
    ):
        signals.append("effort_creep")

    unique_dates = sorted(set(workout_dates))
    if len(unique_dates) >= 4:
        gaps = [
            float((unique_dates[i] - unique_dates[i - 1]).days)
            for i in range(1, len(unique_dates))
        ]
        baseline_gap = median(gaps[:-1]) if len(gaps) > 1 else gaps[0]
        latest_gap = gaps[-1]
        if baseline_gap > 0 and latest_gap > baseline_gap * 1.5:
            signals.append("frequency_drop")

    risk = fatigue_risk_level(len(signals))
    confidence = "high" if len(sorted_workouts) >= 8 else "low"
    details = [f"- Triggered signals: {', '.join(signals) if signals else 'none'}"]
    if affected:
        details.append(f"- Affected lifts: {', '.join(sorted(set(affected)))}")
    details.append(f"- Recent failure ratio: {format_number(recent_ratio * 100, 1)}%")
    details.append(f"- Prior failure ratio: {format_number(prior_ratio * 100, 1)}%")

    notes = [
        "- Not medical advice. Treat this as a training-signal heuristic.",
        f"- Confidence: {confidence} (based on recent data volume).",
    ]
    if risk == "high":
        notes.append("- Consider a short deload or temporary intensity reduction.")
    elif risk == "moderate":
        notes.append("- Consider trimming failure sets for 1-2 sessions.")
    else:
        notes.append("- Current fatigue signal looks manageable.")

    return render_response(
        f"Fatigue risk level: {risk}.",
        f"{start.date()} to {now.date()}",
        details,
        notes,
    )


def suggest_accessories(service: HevyService) -> str:
    now = utc_now()
    baseline_start = now - timedelta(weeks=4)
    recent_start = now - timedelta(days=10)
    very_recent_start = now - timedelta(days=2)
    workouts = service.client.get_workouts_since(baseline_start)
    if not workouts:
        raise NoDataError(
            "No workouts available for accessory recommendations.",
            "Log sessions first, then rerun suggest_accessories.",
        )

    templates = service.load_templates()
    templates_by_id = {str(row.get("id")): row for row in templates}
    by_primary: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for template in templates:
        primary = template.get("primary_muscle_group")
        if isinstance(primary, str):
            by_primary[primary].append(template)

    recent: defaultdict[str, float] = defaultdict(float)
    baseline: defaultdict[str, float] = defaultdict(float)
    very_recent: defaultdict[str, float] = defaultdict(float)

    for workout in workouts:
        start_raw = workout.get("start_time")
        if not isinstance(start_raw, str):
            continue
        workout_time = parse_iso_datetime(start_raw)
        for exercise in workout.get("exercises", []):
            if not isinstance(exercise, dict):
                continue
            template = templates_by_id.get(str(exercise.get("exercise_template_id", "")), {})
            primary = str(template.get("primary_muscle_group", "other"))
            secondaries = [
                item
                for item in template.get("secondary_muscle_groups", [])
                if isinstance(item, str)
            ]

            sets = exercise.get("sets", [])
            if not isinstance(sets, list):
                continue
            for set_row in sets:
                if not isinstance(set_row, dict) or not is_working_set(set_row.get("type")):
                    continue
                baseline[primary] += 1.0
                for muscle in secondaries:
                    baseline[muscle] += 0.5
                if workout_time >= recent_start:
                    recent[primary] += 1.0
                    for muscle in secondaries:
                        recent[muscle] += 0.5
                if workout_time >= very_recent_start:
                    very_recent[primary] += 1.0
                    for muscle in secondaries:
                        very_recent[muscle] += 0.5

    muscles = sorted(
        {
            str(row.get("primary_muscle_group", "other"))
            for row in templates
            if isinstance(row.get("primary_muscle_group"), str)
        }
    )
    chronic = [muscle for muscle in muscles if baseline[muscle] / 4.0 < 4.0]
    recent_under = [muscle for muscle in muscles if recent[muscle] < 3.0]
    heavily = {muscle for muscle, value in very_recent.items() if value >= 4.0}

    priority: list[str] = []
    for muscle in sorted(chronic, key=lambda row: baseline[row]):
        if muscle not in priority:
            priority.append(muscle)
    for muscle in sorted(recent_under, key=lambda row: recent[row]):
        if muscle not in priority:
            priority.append(muscle)

    suggestions: list[tuple[str, str]] = []
    used: set[str] = set()
    for muscle in priority:
        if muscle in heavily:
            continue
        options = sorted(
            by_primary.get(muscle, []),
            key=lambda row: (bool(row.get("is_custom", False)), str(row.get("title", ""))),
        )
        for option in options:
            option_id = str(option.get("id", ""))
            title = str(option.get("title", ""))
            if not option_id or not title or option_id in used:
                continue
            suggestions.append((title, muscle))
            used.add(option_id)
            break
        if len(suggestions) >= 6:
            break

    if not suggestions:
        raise NoDataError(
            "Could not generate accessory suggestions from current data.",
            "Retry after logging more workouts with exercise-template IDs.",
        )

    summary = f"Accessory priorities: {', '.join(m for _, m in suggestions[:4])}."
    details = [
        f"- {title} ({muscle}) -> 2-4 sets, 8-20 reps, RPE 6-8"
        for title, muscle in suggestions
    ]
    notes = [
        "- Suggestions prioritize undertrained muscles and avoid heavily hit muscles in last 48h.",
        "- Keep accessory work low-fatigue and technique-focused.",
    ]
    return render_response(summary, f"Last 4 weeks up to {now.date()}", details, notes)


def training_log(service: HevyService, days: int = 30) -> str:
    requested_days = service.validate_days(days)
    now = utc_now()
    start = now - timedelta(days=requested_days)
    workouts = service.client.get_workouts_since(start)
    if not workouts:
        raise NoDataError(
            "No workouts found in the requested period.",
            "Increase days and rerun training_log.",
        )

    ordered = sorted(workouts, key=lambda row: parse_iso_datetime(str(row.get("start_time"))))
    dates = [parse_iso_datetime(str(row.get("start_time"))).date() for row in ordered]
    gaps = [float((dates[i] - dates[i - 1]).days) for i in range(1, len(dates))]
    avg_gap = mean(gaps) if gaps else 0.0
    med_gap = median(gaps) if gaps else 0.0

    sessions_per_week = len(ordered) / max(requested_days / 7.0, 0.01)
    splits: Counter[str] = Counter()
    fallback = 0
    for workout in ordered:
        label = _split_label(str(workout.get("title", "")))
        splits[label] += 1
        if label == "Other":
            fallback += 1

    details = [f"- {name}: {count}" for name, count in splits.items()]
    details.append(f"- Average gap between sessions: {format_number(avg_gap, 1)} days")
    details.append(f"- Median gap between sessions: {format_number(med_gap, 1)} days")

    summary = (
        f"{len(ordered)} sessions in last {requested_days} day(s) "
        f"({format_number(sessions_per_week, 2)} sessions/week)."
    )
    notes = [f"- Split classifier fallback used on {fallback} workout title(s)."]
    return render_response(summary, f"{start.date()} to {now.date()}", details, notes)


def get_routines(service: HevyService) -> str:
    routines = service.client.paginate("/routines", "routines", page_size=10)
    folders = service.client.get_routine_folders()
    if not routines:
        raise NoDataError(
            "No routines returned by Hevy API.",
            "Create at least one routine in Hevy and retry.",
        )

    folder_names = {
        str(folder.get("id")): str(folder.get("title", folder.get("name", "Unnamed Folder")))
        for folder in folders
        if isinstance(folder, dict)
    }

    grouped: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for routine in routines:
        folder_id = routine.get("routine_folder_id", routine.get("folder_id"))
        grouped[folder_names.get(str(folder_id), "Unfiled")].append(routine)

    details: list[str] = []
    for folder_name in sorted(grouped.keys()):
        details.append(f"- {folder_name}:")
        for routine in sorted(grouped[folder_name], key=lambda row: str(row.get("title", ""))):
            title = str(routine.get("title", "Untitled Routine"))
            exercises = routine.get("exercises", [])
            total_exercises = 0
            exercise_lines: list[str] = []
            planned_sets = 0
            if isinstance(exercises, list):
                shown = 0
                for exercise in exercises:
                    if not isinstance(exercise, dict):
                        continue
                    total_exercises += 1
                    exercise_title = str(exercise.get("title", "Exercise"))
                    set_rows = exercise.get("sets")
                    sets_count = exercise.get("sets_count")
                    set_plan = "no set plan"

                    if isinstance(set_rows, list):
                        structured_sets = sum(1 for row in set_rows if isinstance(row, dict))
                        if structured_sets > 0:
                            planned_sets += structured_sets
                            set_plan = _summarize_set_scheme(set_rows)
                        elif isinstance(sets_count, int):
                            planned_sets += sets_count
                            set_plan = f"{sets_count} set(s) planned"
                    elif isinstance(sets_count, int):
                        planned_sets += sets_count
                        set_plan = f"{sets_count} set(s) planned"
                    if shown < MAX_ROUTINE_EXERCISES_OUTPUT:
                        exercise_lines.append(f"  - {exercise_title}: {set_plan}")
                        shown += 1

                hidden = max(total_exercises - MAX_ROUTINE_EXERCISES_OUTPUT, 0)
                if hidden:
                    exercise_lines.append(f"  - ... {hidden} more exercise(s)")

            details.append(
                f"- {title} ({total_exercises} exercise(s), {planned_sets} planned sets)"
            )
            if exercise_lines:
                details.extend(exercise_lines)
            else:
                details.append("  - no exercises")

    summary = f"{len(routines)} routine(s) across {max(len(folder_names), 1)} folder(s)."
    notes = ["- Routines without folder mapping are listed under Unfiled."]
    return render_response(summary, "Current routine catalog", details, notes)


def _split_label(title: str) -> str:
    normalized = title.lower()
    if "upper" in normalized:
        return "Upper"
    if "lower" in normalized:
        return "Lower"
    if "full body" in normalized or "full" in normalized:
        return "Full Body"
    if "arm" in normalized or "delt" in normalized or "shoulder" in normalized:
        return "Arms/Delts"
    return "Other"


def _rerank_matches_with_history(
    query: str,
    matches: list[dict[str, Any]],
    usage_by_template: dict[str, int],
) -> list[dict[str, Any]]:
    normalized_query = normalize_text(query)
    scored: list[tuple[int, int, int, dict[str, Any]]] = []

    for index, match in enumerate(matches):
        title = str(match.get("title", ""))
        normalized_title = normalize_text(title)
        template_id = str(match.get("id", ""))
        usage = usage_by_template.get(template_id, 0)

        if normalized_title == normalized_query:
            group = 0
        elif usage > 0:
            group = 1
        else:
            group = 2
        scored.append((group, -usage, index, match))

    scored.sort(key=lambda row: (row[0], row[1], row[2]))
    return [row[3] for row in scored]


def _summarize_set_scheme(set_rows: list[Any]) -> str:
    rendered: list[str] = []
    for row in set_rows:
        if not isinstance(row, dict):
            continue
        rendered.append(_render_set_detail(row))
    if not rendered:
        return "no set plan"

    grouped: Counter[str] = Counter(rendered)
    chunks: list[str] = []
    for label in rendered:
        count = grouped.pop(label, 0)
        if count <= 0:
            continue
        chunks.append(f"{count}x {label}")
    return ", ".join(chunks)


def _render_set_detail(set_row: dict[str, Any]) -> str:
    label = format_set(set_row)

    set_type = set_row.get("type")
    reps = set_row.get("reps")
    if set_type == "failure" and isinstance(reps, (int, float)):
        rep_text = str(int(reps))
        if label.endswith(rep_text):
            label = f"{label}+"

    if isinstance(set_type, str) and set_type != "normal":
        label = f"{label} [{set_type}]"

    extras: list[str] = []
    rir = set_row.get("rir")
    if isinstance(rir, (int, float)):
        extras.append(f"RIR {format_number(float(rir), 1)}")
    rest_seconds = set_row.get("rest_seconds")
    if isinstance(rest_seconds, (int, float)):
        extras.append(f"rest {int(rest_seconds)}s")

    if extras:
        label = f"{label} ({', '.join(extras)})"
    return label
