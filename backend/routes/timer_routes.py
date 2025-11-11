from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime

from sqlalchemy.orm import Session

from ..models.schemas import TimerUpdateRequest, Quest as QuestSchema
from ..models.db_models import Quest as QuestModel, TimerLog, User
from ..database import get_db


router = APIRouter(prefix="/timer", tags=["timer"])


@router.post("/update", response_model=QuestSchema)
def timer_update(payload: TimerUpdateRequest, db: Session = Depends(get_db)):
    row = None
    # Resolve quest by quest_id or subject
    if payload.quest_id:
        row = db.get(QuestModel, payload.quest_id)
        if not row or row.user_id != payload.user_id:
            raise HTTPException(status_code=404, detail="Quest not found")
    else:
        if not payload.subject:
            raise HTTPException(status_code=400, detail="subject or quest_id required")
        # find active quest for subject
        row = (
            db.query(QuestModel)
            .filter(
                QuestModel.user_id == payload.user_id,
                QuestModel.subject == payload.subject,
                QuestModel.type == "time",
                QuestModel.status.in_(["pending", "in_progress"]),
            )
            .order_by(QuestModel.created_at.asc())
            .first()
        )
        if row is None:
            # auto-create quest for this subject (ensure max 3 total subjects rule)
            user = db.get(User, payload.user_id)
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            # count existing active subjects
            active_subjects = {
                r.subject
                for r in db.query(QuestModel)
                .filter(
                    QuestModel.user_id == payload.user_id,
                    QuestModel.type == "time",
                    QuestModel.status.in_(["pending", "in_progress"]),
                )
                .all()
            }
            if payload.subject in ["국어", "수학", "영어"] and payload.subject not in active_subjects:
                import json as pyjson
                from datetime import datetime as dt
                try:
                    ratio = pyjson.loads(user.subject_ratio_json)
                except Exception:
                    ratio = {"국어": 0.33, "수학": 0.34, "영어": 0.33}
                daily = int(user.daily_minutes_goal or 90)
                want = int(daily * float(ratio.get(payload.subject, 0)))
                goal = max(20, min(60, max(20, int(want * 0.5))))
                row = QuestModel(
                    id=f"auto_{payload.subject}_{int(dt.utcnow().timestamp())}",
                    user_id=payload.user_id,
                    type="time",
                    title=f"{payload.subject} 학습 {goal}분",
                    subject=payload.subject,
                    goal_value=goal,
                    status="pending",
                    source="ai_generated",
                )
                db.add(row)
                db.commit()
                row = db.get(QuestModel, row.id)
            else:
                raise HTTPException(status_code=409, detail="Active quests for 3 subjects already exist")
    if row.status == "completed":
        return QuestSchema(
            id=row.id, user_id=row.user_id, type=row.type, title=row.title, subject=row.subject,
            goal_value=row.goal_value, progress_value=row.progress_minutes, status=row.status,
            source=row.source, created_at=row.created_at, updated_at=row.updated_at
        )

    # accumulate seconds, convert to minutes precisely
    total_seconds = (row.progress_seconds_remainder or 0) + max(0, int(payload.delta_seconds))
    inc_minutes = total_seconds // 60
    row.progress_seconds_remainder = total_seconds % 60
    row.progress_minutes = int(row.progress_minutes or 0) + int(inc_minutes)

    # status update
    row.status = "completed" if row.progress_minutes >= int(row.goal_value) else "in_progress"
    row.updated_at = datetime.utcnow()

    # log
    db.add(TimerLog(user_id=payload.user_id, quest_id=row.id, delta_seconds=max(0, int(payload.delta_seconds))))
    db.add(row)
    db.commit()

    return QuestSchema(
        id=row.id, user_id=row.user_id, type=row.type, title=row.title, subject=row.subject,
        goal_value=row.goal_value, progress_value=row.progress_minutes, status=row.status,
        source=row.source, created_at=row.created_at, updated_at=row.updated_at
    )
