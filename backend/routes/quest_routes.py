from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List
from datetime import datetime

from sqlalchemy.orm import Session

from ..models.schemas import Quest as QuestSchema
from ..models.db_models import Quest as QuestModel
from ..database import get_db


router = APIRouter(prefix="/quests", tags=["quests"])


@router.get("", response_model=List[QuestSchema])
def list_quests(user_id: str = Query(..., description="User ID"), db: Session = Depends(get_db)):
    rows = db.query(QuestModel).filter(QuestModel.user_id == user_id).all()
    return [QuestSchema(
        id=r.id, user_id=r.user_id, type=r.type, title=r.title, subject=r.subject,
        goal_value=r.goal_value, progress_value=r.progress_minutes, status=r.status,
        source=r.source, created_at=r.created_at, updated_at=r.updated_at
    ) for r in rows]


@router.post("", response_model=QuestSchema)
def create_quest(q: QuestSchema, db: Session = Depends(get_db)):
    # Enforce one active time-quest per subject (국어/수학/영어)
    if q.type == "time" and q.subject in ["국어", "수학", "영어"]:
        existing = (
            db.query(QuestModel)
            .filter(
                QuestModel.user_id == q.user_id,
                QuestModel.type == "time",
                QuestModel.subject == q.subject,
                QuestModel.status.in_(["pending", "in_progress"]),
            )
            .first()
        )
        if existing:
            # return existing instead of creating duplicate
            return QuestSchema(
                id=existing.id, user_id=existing.user_id, type=existing.type, title=existing.title,
                subject=existing.subject, goal_value=existing.goal_value, progress_value=existing.progress_minutes,
                status=existing.status, source=existing.source, created_at=existing.created_at, updated_at=existing.updated_at
            )
    if db.get(QuestModel, q.id):
        raise HTTPException(status_code=409, detail="Quest already exists")
    now = datetime.utcnow()
    row = QuestModel(
        id=q.id, user_id=q.user_id, type=q.type, title=q.title, subject=q.subject,
        goal_value=q.goal_value, progress_minutes=q.progress_value or 0, status=q.status,
        source=q.source, created_at=q.created_at or now, updated_at=q.updated_at or now
    )
    db.add(row)
    db.commit()
    return QuestSchema(
        id=row.id, user_id=row.user_id, type=row.type, title=row.title, subject=row.subject,
        goal_value=row.goal_value, progress_value=row.progress_minutes, status=row.status,
        source=row.source, created_at=row.created_at, updated_at=row.updated_at
    )


@router.patch("/{quest_id}", response_model=QuestSchema)
def patch_quest(quest_id: str, status: str | None = None, progress_value: int | None = None, db: Session = Depends(get_db)):
    row = db.get(QuestModel, quest_id)
    if not row:
        raise HTTPException(status_code=404, detail="Quest not found")
    if status is not None:
        row.status = status
    if progress_value is not None:
        row.progress_minutes = max(0, int(progress_value))
    row.updated_at = datetime.utcnow()
    db.add(row)
    db.commit()
    return QuestSchema(
        id=row.id, user_id=row.user_id, type=row.type, title=row.title, subject=row.subject,
        goal_value=row.goal_value, progress_value=row.progress_minutes, status=row.status,
        source=row.source, created_at=row.created_at, updated_at=row.updated_at
    )
