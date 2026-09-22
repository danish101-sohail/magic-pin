from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def _get(value: Any, key: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(key, default)
    return getattr(value, key, default)


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _merchant_signal(merchant: Any, signal: str) -> bool:
    signals = _get(merchant, "signals", []) or []
    return any(signal in str(item).lower() for item in signals)


def _score_trigger(merchant: Any, trigger: Any) -> float:
    kind = str(_get(trigger, "kind", "")).lower()
    urgency = _number(_get(trigger, "urgency"), 0)
    payload = _get(trigger, "payload", {}) or {}
    performance = _get(merchant, "performance", {}) or {}
    delta_7d = _get(performance, "delta_7d", {}) or {}

    # Base weights reflect business impact: customer recall is time-bound (50),
    # performance recovery is next (40), research is useful but less urgent (20),
    # and festivals are lowest (15). Urgency adds up to 25, while merchant
    # signals add up to 20 so observable account state can override a generic event.
    base_weights = {
        "recall_due": 50,
        "appointment_tomorrow": 50,
        "perf_dip": 40,
        "seasonal_perf_dip": 40,
        "perf_spike": 30,
        "research_digest": 20,
        "festival_upcoming": 15,
    }
    score = base_weights.get(kind, 0) + min(max(urgency, 0), 5) * 5

    delta_pct = _number(_get(payload, "delta_pct"), 0)
    if kind in {"perf_dip", "seasonal_perf_dip"}:
        score += min(abs(delta_pct) * 40, 20)
        score += min(abs(_number(_get(delta_7d, "calls_pct"))) * 20, 10)
        score += min(abs(_number(_get(delta_7d, "views_pct"))) * 20, 10)
    elif kind == "perf_spike":
        score += min(max(delta_pct, 0) * 20, 10)
        score += min(max(_number(_get(delta_7d, "calls_pct")), 0) * 10, 5)

    if kind == "recall_due" and _merchant_signal(merchant, "lapsed"):
        score += 10
    if kind in {"perf_dip", "seasonal_perf_dip"} and (
        _merchant_signal(merchant, "ctr_below") or _merchant_signal(merchant, "stale")
    ):
        score += 10
    if kind == "research_digest" and _merchant_signal(merchant, "engaged"):
        score += 5
    if kind == "festival_upcoming" and _get(payload, "days_until") is not None:
        score += max(0, 10 - min(_number(_get(payload, "days_until")), 10))

    return score


def pick_trigger(merchant: Any, active_triggers: Sequence[Any]) -> Any | None:
    """Return the highest-priority active trigger, or ``None`` when empty."""
    if not active_triggers:
        return None

    ranked = []
    for index, trigger in enumerate(active_triggers):
        kind = str(_get(trigger, "kind", "")).lower()
        ranked.append((
            _score_trigger(merchant, trigger),
            _number(_get(trigger, "urgency"), 0),
            -index,
            trigger,
        ))

    return max(ranked, key=lambda item: item[:3])[-1]


def priority_rank(trigger_kind: str | None) -> int:
    """Compatibility helper exposing the base weight for one trigger kind."""
    if not trigger_kind:
        return 0
    return {
        "recall_due": 50,
        "appointment_tomorrow": 50,
        "perf_dip": 40,
        "seasonal_perf_dip": 40,
        "perf_spike": 30,
        "research_digest": 20,
        "festival_upcoming": 15,
    }.get(trigger_kind.lower(), 0)
