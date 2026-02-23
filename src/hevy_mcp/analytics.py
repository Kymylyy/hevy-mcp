from __future__ import annotations

from statistics import median


def classify_trend(session_best_e1rm: list[float]) -> tuple[str, float | None]:
    if len(session_best_e1rm) < 3:
        return "stagnating", None

    bucket = max(1, int(len(session_best_e1rm) * 0.4))
    early = median(session_best_e1rm[:bucket])
    late = median(session_best_e1rm[-bucket:])
    if early <= 0:
        return "stagnating", None

    change = (late - early) / early * 100
    if change >= 2:
        return "improving", change
    if change <= -2:
        return "declining", change
    return "stagnating", change


def fatigue_risk_level(signal_count: int) -> str:
    if signal_count <= 0:
        return "low"
    if signal_count == 1:
        return "moderate"
    return "high"
