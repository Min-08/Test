from __future__ import annotations

from fastapi import APIRouter, Query, Depends
from pathlib import Path
import json

from sqlalchemy.orm import Session

from ..database import get_db
from ..models.db_models import User, Quest, TimerLog, QuestionLog
from ..constants import SUBJECT_KO_KOREAN, DEFAULT_SUBJECT_RATIO_JSON


router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/reset_all")
def reset_all(seed: bool = Query(False), db: Session = Depends(get_db)):
    timer_deleted = db.query(TimerLog).delete(synchronize_session=False)
    question_deleted = db.query(QuestionLog).delete(synchronize_session=False)
    quest_deleted = db.query(Quest).delete(synchronize_session=False)
    user_deleted = db.query(User).delete(synchronize_session=False)
    db.commit()

    user = User(
        id="u1",
        display_name="Demo User",
        daily_minutes_goal=90,
        subject_ratio_json=DEFAULT_SUBJECT_RATIO_JSON,
    )
    db.add(user)
    db.commit()

    created = 0
    if seed:
        seed_path = Path(__file__).resolve().parents[2] / "data" / "seed_quests.json"
        if seed_path.exists():
            try:
                with seed_path.open("r", encoding="utf-8") as handle:
                    quests = json.load(handle)
                for q in quests:
                    db.add(
                        Quest(
                            id=q["id"],
                            user_id=q.get("user_id", "u1"),
                            type=q.get("type", "time"),
                            title=q.get("title", "Unnamed Quest"),
                            subject=q.get("subject", SUBJECT_KO_KOREAN),
                            goal_value=int(q.get("goal_value", 0)),
                            progress_minutes=int(q.get("progress_value", 0)),
                            status=q.get("status", "pending"),
                            source=q.get("source", "ai_generated"),
                            tags_json=json.dumps(q.get("tags") or []),
                            tags_ko_json=json.dumps(q.get("tags_ko") or []),
                            meta_json=json.dumps(q.get("meta") or {}),
                        )
                    )
                    created += 1
                db.commit()
            except Exception:
                pass

    return {
        "ok": True,
        "deleted": {
            "timer_logs": timer_deleted,
            "question_logs": question_deleted,
            "quests": quest_deleted,
            "users": user_deleted,
        },
        "seeded_quests": created,
        "user": "u1",
    }

