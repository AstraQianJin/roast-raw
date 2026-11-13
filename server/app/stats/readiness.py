from collections.abc import Mapping, Sequence
from datetime import date
from math import isfinite
import re
from statistics import fmean, pstdev
from typing import Any


_SUBJECTIVES = ("recovery", "arousal", "nutrition")
_PHYSIOLOGICAL = ("hrv", "rhr")
_BASELINE_DAYS = 28


def _day(value: Any) -> date | None:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _number(value: Any) -> bool:
    return type(value) in (int, float) and isfinite(value)


def _positive(value: Any) -> bool:
    return _number(value) and value > 0


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _time_adjustment(value: Any) -> float:
    if not isinstance(value, str) or not re.fullmatch(r"(?:[01][0-9]|2[0-3]):[0-5][0-9]", value):
        return 0.0
    hour, minute = map(int, value.split(":"))
    minutes = hour * 60 + minute
    if 5 * 60 <= minutes < 9 * 60:
        return -3.0
    if 9 * 60 <= minutes < 12 * 60:
        return -1.5
    if 17 * 60 <= minutes < 21 * 60:
        return -1.0
    return 0.0


def _baseline(prior: Sequence[Mapping[str, Any]], field: str) -> dict:
    # Last valid reading per day wins; use the latest 28 distinct valid days.
    daily = {}
    for entry in prior:
        value = entry.get(field)
        if _positive(value):
            daily[_day(entry.get("date"))] = value
    days = sorted(daily)[-_BASELINE_DAYS:]
    result = {
        "count": len(days),
        "requiredDays": _BASELINE_DAYS,
        "dates": [day.isoformat() for day in days],
        "mean": None,
        "sigma": None,
        "status": "insufficient_history",
    }
    if len(days) == _BASELINE_DAYS:
        readings = [daily[day] for day in days]
        result["mean"] = fmean(readings)
        result["sigma"] = pstdev(readings)
        result["status"] = "ready" if result["sigma"] > 0 else "zero_variance"
    return result


def score_readiness(record: Mapping[str, Any], history: Sequence[Mapping[str, Any]]) -> dict:
    current_day = _day(record.get("date"))
    if current_day is None:
        raise ValueError("date: expected a valid YYYY-MM-DD date")
    prior = []
    for entry in history:
        if not isinstance(entry, Mapping):
            continue
        entry_day = _day(entry.get("date"))
        if entry_day is not None and entry_day < current_day:
            prior.append(entry)

    scores = {}
    for field in _SUBJECTIVES:
        value = record.get(field)
        scores[field] = (value - 1) / 6 * 100 if type(value) is int and 1 <= value <= 7 else None
    sleep = record.get("sleep_score")
    scores["sleep_score"] = float(sleep) if _number(sleep) and 0 <= sleep <= 100 else None

    baseline = {field: _baseline(prior, field) for field in _PHYSIOLOGICAL}
    for field in _PHYSIOLOGICAL:
        value = record.get(field)
        reference = baseline[field]
        scores[field] = None
        if _positive(value) and reference["status"] == "ready":
            z_score = (value - reference["mean"]) / reference["sigma"]
            if field == "rhr":
                z_score = -z_score
            scores[field] = _clamp(50 + z_score / 2 * 50, 0.0, 100.0)

    valid = [value for value in scores.values() if value is not None]
    score = fmean(valid) if len(valid) >= 3 else None
    rec = _clamp(0.75 + 0.5 * score / 100, 0.55, 1.25) if score is not None else None
    advice = [
        "Advisory only: readiness and time estimates never change prescribed loads automatically.",
        "Insufficient matched observations for a personal time curve: performance_index "
        "is not available in the readiness record contract. At least eight weeks of "
        "distinct prior observations with session_time and a positive personal-benchmark "
        "performance ratio are required. A personal time curve is not implemented.",
    ]
    if score is None:
        advice.append("At least three valid scored inputs are required for a readiness score and REC.")
    if record.get("joint_pain") is True:
        advice.append("Caution: joint pain reported. Avoid painful movements and seek qualified guidance; loads are not changed automatically.")

    return {
        "scores": scores,
        "validInputs": len(valid),
        "score": score,
        "rec": rec,
        "baseline": baseline,
        "timeAdjustmentPct": _time_adjustment(record.get("session_time")),
        "timeBasis": "experience",
        "advice": advice,
    }
