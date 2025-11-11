from typing import Dict, Any

DB_USERS: Dict[str, Any] = {}
DB_QUESTS: Dict[str, Any] = {}
DB_TIMER_LOGS: Dict[str, Any] = {}
DB_QUESTION_LOGS: Dict[str, Any] = {}


def seed_default_user():
    # Simple single-user seed for MVP
    if "u1" not in DB_USERS:
        DB_USERS["u1"] = {
            "id": "u1",
            "display_name": "Demo User",
            "daily_minutes_goal": 90,
            "subject_ratio": {"국어": 0.3, "수학": 0.3, "영어": 0.3, "기타": 0.1},
        }

