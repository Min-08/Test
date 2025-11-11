from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
import json

from ..database import get_db
from ..models.schemas import Quest as QuestSchema
from ..models.db_models import Quest
from ..services.ai_problem_service import generate_ai_problem_quest


router = APIRouter(prefix="/ai/quests", tags=["ai-quests"])


@router.post("/ai_problem", response_model=QuestSchema)
def create_ai_problem(user_id: str = Query(...), subject: str = Query(...), db: Session = Depends(get_db)):
    if subject not in ["국어", "수학", "영어"]:
        raise HTTPException(status_code=400, detail="subject must be one of 국어/수학/영어")
    q = generate_ai_problem_quest(db, user_id, subject)
    return QuestSchema(
        id=q.id,
        user_id=q.user_id,
        type=q.type,
        title=q.title,
        subject=q.subject,
        goal_value=q.goal_value,
        progress_value=q.progress_minutes or 0,
        status=q.status,
        source=q.source,
        tags=(json.loads(q.tags_json) if q.tags_json else None),
        tags_ko=(json.loads(q.tags_ko_json) if q.tags_ko_json else None),
        meta=(json.loads(q.meta_json) if q.meta_json else None),
        created_at=q.created_at,
        updated_at=q.updated_at,
    )

