from hevy_analytics.analytics import classify_trend, fatigue_risk_level


def test_classify_trend_improving() -> None:
    label, change = classify_trend([100.0, 101.0, 103.5, 105.0, 106.0])
    assert label == "improving"
    assert change is not None
    assert change > 0


def test_classify_trend_declining() -> None:
    label, change = classify_trend([110.0, 108.0, 105.0, 102.0, 100.0])
    assert label == "declining"
    assert change is not None
    assert change < 0


def test_fatigue_risk_level_buckets() -> None:
    assert fatigue_risk_level(0) == "low"
    assert fatigue_risk_level(1) == "moderate"
    assert fatigue_risk_level(3) == "high"
