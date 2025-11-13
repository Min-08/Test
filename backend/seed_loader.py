from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple, Any
import json

from .services.goal_policy import resolve_goal_minutes


def _normalize_quest(raw: Dict[str, Any], meta: Dict[str, Any]) -> Dict[str, Any]:
    quest = dict(raw)
    goal_data = quest.pop("goal", None)
    quest["goal_value"] = resolve_goal_minutes(
        goal_data,
        meta.get("goal_defaults") or {},
    )
    quest.setdefault("progress_value", 0)
    quest.setdefault("status", "pending")
    quest.setdefault("source", "seed")
    quest.setdefault("tags", [])
    return quest


def load_seed_quests(seed_path: Path) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    if not seed_path.exists():
        return [], {}
    try:
        with seed_path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except Exception:
        return [], {}

    if isinstance(raw, dict):
        meta = raw.get("_meta") or {}
        quests = [_normalize_quest(q, meta) for q in raw.get("quests", []) if isinstance(q, dict)]
        return quests, meta
    if isinstance(raw, list):
        quests = [_normalize_quest(q, {}) for q in raw if isinstance(q, dict)]
        return quests, {}
    return [], {}
