from __future__ import annotations

from typing import Any, Iterable, Sequence, List, Dict


DEFAULT_ALLOWED_MINUTES: Sequence[int] = (15, 20, 25, 30, 35, 40, 45, 50, 60, 75, 90)


def _coerce_allowed_minutes(values: Any) -> List[int]:
    if values is None:
        return []
    if isinstance(values, (int, float)):
        return [max(1, int(values))]
    if isinstance(values, (str, bytes)):
        try:
            return [max(1, int(values))]
        except Exception:
            return []
    if isinstance(values, Iterable):
        result: List[int] = []
        for item in values:
            try:
                number = int(item)
            except Exception:
                continue
            if number > 0:
                result.append(number)
        if result:
            return sorted(set(result))
    return []


def _pick_minutes(preferred: float, allowed: Sequence[int], mode: str) -> int:
    if not allowed:
        allowed = DEFAULT_ALLOWED_MINUTES
    if mode == "fixed":
        return int(preferred)
    if mode == "ceil":
        higher = [m for m in allowed if m >= preferred]
        return higher[0] if higher else allowed[-1]
    if mode == "floor":
        lower = [m for m in allowed if m <= preferred]
        return lower[-1] if lower else allowed[0]
    # default nearest
    return min(allowed, key=lambda m: abs(m - preferred))


def resolve_goal_minutes(goal_data: Any, defaults: Dict[str, Any] | None = None) -> int:
    defaults = defaults or {}
    allowed = _coerce_allowed_minutes(defaults.get("allowed_minutes")) or list(DEFAULT_ALLOWED_MINUTES)
    preferred = defaults.get("preferred")
    mode = (defaults.get("mode") or defaults.get("strategy") or "nearest").lower()
    min_minutes = defaults.get("min") or defaults.get("min_minutes")
    max_minutes = defaults.get("max") or defaults.get("max_minutes")

    if isinstance(goal_data, (int, float)):
        preferred = goal_data
        mode = "fixed"
    elif isinstance(goal_data, dict):
        allowed = _coerce_allowed_minutes(goal_data.get("allowed_minutes")) or allowed
        preferred = goal_data.get("preferred", goal_data.get("minutes", preferred))
        mode = (goal_data.get("mode") or goal_data.get("strategy") or mode).lower()
        min_minutes = goal_data.get("min") or goal_data.get("min_minutes") or min_minutes
        max_minutes = goal_data.get("max") or goal_data.get("max_minutes") or max_minutes
    elif goal_data is not None:
        try:
            preferred = int(goal_data)
            mode = "fixed"
        except Exception:
            pass

    if preferred is None:
        preferred = allowed[0]

    candidate = _pick_minutes(float(preferred), allowed, mode)

    if min_minutes is not None:
        candidate = max(candidate, int(min_minutes))
    if max_minutes is not None:
        candidate = min(candidate, int(max_minutes))

    return max(0, int(candidate))
