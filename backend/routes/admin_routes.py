from __future__ import annotations

from fastapi import APIRouter, Query, Depends
from pathlib import Path
import json

from sqlalchemy.orm import Session

from ..database import get_db
from ..models.db_models import User, Quest, TimerLog, QuestionLog


router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/reset_all")
def reset_all(seed: bool = Query(False), db: Session = Depends(get_db)):
    # delete in order to avoid FK issues (logs -> quests -> users)
    logs_deleted = db.query(TimerLog).delete(synchronize_session=False)
    qlogs_deleted = db.query(QuestionLog).delete(synchronize_session=False)
    quests_deleted = db.query(Quest).delete(synchronize_session=False)
    users_deleted = db.query(User).delete(synchronize_session=False)
    db.commit()

    # recreate default user
    u = User(id="u1", display_name="Demo User", daily_minutes_goal=90,
             subject_ratio_json='{"국어":0.33,"수학":0.34,"영어":0.33}')
    db.add(u)
    db.commit()

    created_quests = 0
    if seed:
        seed_path = Path(__file__).resolve().parents[2] / "data" / "seed_quests.json"
        if seed_path.exists():
            try:
                with seed_path.open("r", encoding="utf-8") as f:
                    quests = json.load(f)
                for q in quests:
                    if q.get("user_id") != "u1":
                        q["user_id"] = "u1"
                    db.add(Quest(
                        id=q["id"], user_id=q["user_id"], type=q.get("type","time"), title=q["title"],
                        subject=q.get("subject","국어"), goal_value=int(q.get("goal_value", 30)),
                        progress_minutes=int(q.get("progress_value", 0)), status=q.get("status","pending"),
                        source=q.get("source","ai_generated")
                    ))
                    created_quests += 1
                db.commit()
            except Exception:
                pass

    return {
        "ok": True,
        "deleted": {
            "timer_logs": logs_deleted,
            "question_logs": qlogs_deleted,
            "quests": quests_deleted,
            "users": users_deleted,
        },
        "seeded_quests": created_quests,
        "user": "u1",
    }

