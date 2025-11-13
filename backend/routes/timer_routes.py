from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime
import json

from sqlalchemy.orm import Session

from ..models.schemas import TimerUpdateRequest, Quest as QuestSchema
from ..models.db_models import Quest as QuestModel, TimerLog, User
from ..database import get_db
from ..services.tagging_service import has_active_subject_tag
from ..services.goal_policy import resolve_goal_minutes, DEFAULT_ALLOWED_MINUTES
from ..constants import SUBJECTS, STUDY_TAG, STUDY_TAG_KO, SUBJECT_KO_KOREAN


router = APIRouter(prefix="/timer", tags=["timer"])


def _quest_schema(row: QuestModel) -> QuestSchema:
    return QuestSchema(
        id=row.id,
        user_id=row.user_id,
        type=row.type,
        title=row.title,
        subject=row.subject,
        goal_value=row.goal_value,
        progress_value=row.progress_minutes,
        progress_seconds=int((row.progress_minutes or 0) * 60 + (row.progress_seconds_remainder or 0)),
        status=row.status,
        source=row.source,
        tags=(json.loads(row.tags_json) if row.tags_json else None),
        tags_ko=(json.loads(row.tags_ko_json) if row.tags_ko_json else None),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _parse_tags(row: QuestModel) -> tuple[list[str], list[str]]:
    tags = []
    tags_ko = []
    if row.tags_json:
        try:
            tags = json.loads(row.tags_json)
        except Exception:
            tags = []
    if row.tags_ko_json:
        try:
            tags_ko = json.loads(row.tags_ko_json)
        except Exception:
            tags_ko = []
    return tags, tags_ko


@router.post("/update", response_model=QuestSchema)
def timer_update(payload: TimerUpdateRequest, db: Session = Depends(get_db)):
    row = None

    if payload.quest_id:
        row = db.get(QuestModel, payload.quest_id)
        if not row or row.user_id != payload.user_id:
            raise HTTPException(status_code=404, detail="Quest not found")
    else:
        if not payload.subject:
            raise HTTPException(status_code=400, detail="subject or quest_id required")

        rows = (
            db.query(QuestModel)
            .filter(
                QuestModel.user_id == payload.user_id,
                QuestModel.subject == payload.subject,
                QuestModel.type == "time",
                QuestModel.status.in_(["pending", "in_progress", "paused"]),
            )
            .order_by(QuestModel.created_at.asc())
            .all()
        )

        for candidate in rows:
            tags, tags_ko = _parse_tags(candidate)
            if STUDY_TAG in tags or STUDY_TAG_KO in tags_ko:
                row = candidate
                break

        if row is None:
            user = db.get(User, payload.user_id)
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            if payload.subject not in SUBJECTS:
                raise HTTPException(status_code=400, detail="Unsupported subject")

            try:
                ratio = json.loads(user.subject_ratio_json)
            except Exception:
                ratio = {}
            daily = int(user.daily_minutes_goal or 90)
            want = max(1, int(daily * float(ratio.get(payload.subject, 0))))
            goal = resolve_goal_minutes(
                {"preferred": want, "mode": "nearest"},
                {"allowed_minutes": DEFAULT_ALLOWED_MINUTES},
            )

            tags_en = [STUDY_TAG]
            tags_ko = [STUDY_TAG_KO]
            existing_study = has_active_subject_tag(db, payload.user_id, payload.subject, STUDY_TAG_KO)
            if existing_study:
                row = existing_study
            else:
                row = QuestModel(
                    id=f"auto_{payload.subject}_{int(datetime.utcnow().timestamp())}",
                    user_id=payload.user_id,
                    type="time",
                    title=f"{payload.subject} 학습 {goal}분",
                    subject=payload.subject or SUBJECT_KO_KOREAN,
                    goal_value=goal,
                    status="pending",
                    source="ai_generated",
                    tags_json=json.dumps(tags_en),
                    tags_ko_json=json.dumps(tags_ko),
                )
                db.add(row)
                db.commit()

    if row.status == "completed":
        completed = _quest_schema(row)
        db.delete(row)
        db.commit()
        return completed

    delta_seconds = max(0, int(payload.delta_seconds))
    total_seconds = (row.progress_seconds_remainder or 0) + delta_seconds
    inc_minutes = total_seconds // 60
    row.progress_seconds_remainder = total_seconds % 60
    row.progress_minutes = int(row.progress_minutes or 0) + int(inc_minutes)
    row.status = "completed" if row.progress_minutes >= int(row.goal_value or 0) else "in_progress"
    row.updated_at = datetime.utcnow()

    if delta_seconds > 0:
        db.add(
            TimerLog(
                user_id=payload.user_id,
                quest_id=row.id,
                subject=row.subject,
                delta_seconds=delta_seconds,
            )
        )
    db.add(row)
    db.commit()

    result = _quest_schema(row)
    if result.status == "completed":
        db.delete(row)
        db.commit()
    return result
