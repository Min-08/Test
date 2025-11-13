from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List
from datetime import datetime
import json
import re

from sqlalchemy.orm import Session

from ..models.schemas import (
    Quest as QuestSchema,
    QuestResultRequest,
    QuestResultResponse,
    PatchQuestRequest,
    QuestAnswerRequest,
    QuestAnswerResponse,
)
from ..models.db_models import Quest as QuestModel, QuestResultLog
from ..database import get_db
from ..constants import SUBJECTS, SUBJECT_KO_KOREAN

STUDY_TAG = "study"
STUDY_TAG_KO = "\ud559\uc2b5"  # "학습"


router = APIRouter(prefix="/quests", tags=["quests"])


def _schema_from_row(row: QuestModel) -> QuestSchema:
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
        meta=(json.loads(row.meta_json) if row.meta_json else None),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _parse_tags(row: QuestModel) -> tuple[set[str], set[str]]:
    tags = set()
    tags_ko = set()
    if row.tags_json:
        try:
            tags = set(json.loads(row.tags_json))
        except Exception:
            tags = set()
    if row.tags_ko_json:
        try:
            tags_ko = set(json.loads(row.tags_ko_json))
        except Exception:
            tags_ko = set()
    return tags, tags_ko


def _normalized(text: str) -> str:
    return re.sub(r"\s+", "", (text or "")).lower()


def _extract_answers(meta: dict) -> list[str]:
    answers = meta.get("correct_answers") or meta.get("answer")
    if isinstance(answers, list):
        return [str(ans).strip() for ans in answers if str(ans).strip()]
    if isinstance(answers, str):
        return [answers.strip()]
    return []


@router.get("", response_model=List[QuestSchema])
def list_quests(user_id: str = Query(..., description="User ID"), db: Session = Depends(get_db)):
    rows = db.query(QuestModel).filter(QuestModel.user_id == user_id).all()
    response: List[QuestSchema] = []
    dirty = False
    for row in rows:
        if row.type == "time" and row.goal_value and row.goal_value > 0:
            if row.status == "completed" or row.progress_minutes >= row.goal_value:
                db.delete(row)
                dirty = True
                continue
        response.append(_schema_from_row(row))
    if dirty:
        db.commit()
    return response


@router.post("", response_model=QuestSchema)
def create_quest(q: QuestSchema, db: Session = Depends(get_db)):
    if q.type == "time" and q.subject in SUBJECTS:
        active = (
            db.query(QuestModel)
            .filter(
                QuestModel.user_id == q.user_id,
                QuestModel.type == "time",
                QuestModel.subject == q.subject,
                QuestModel.status.in_(["pending", "in_progress", "paused"]),
            )
            .all()
        )
        incoming_tags = set(q.tags or [])
        incoming_tags_ko = set(q.tags_ko or [])
        is_study = (STUDY_TAG in incoming_tags) or (STUDY_TAG_KO in incoming_tags_ko)

        for row in active:
            tags, tags_ko = _parse_tags(row)
            if is_study:
                if STUDY_TAG in tags or STUDY_TAG_KO in tags_ko:
                    return _schema_from_row(row)
            else:
                if (incoming_tags and (incoming_tags & tags)) or (incoming_tags_ko and (incoming_tags_ko & tags_ko)):
                    return _schema_from_row(row)

    if db.get(QuestModel, q.id):
        raise HTTPException(status_code=409, detail="Quest already exists")

    now = datetime.utcnow()
    row = QuestModel(
        id=q.id,
        user_id=q.user_id,
        type=q.type,
        title=q.title,
        subject=q.subject or SUBJECT_KO_KOREAN,
        goal_value=q.goal_value,
        progress_minutes=q.progress_value or 0,
        status=q.status,
        source=q.source,
        tags_json=json.dumps(q.tags or []),
        tags_ko_json=json.dumps(q.tags_ko or []),
        meta_json=json.dumps(q.meta or {}),
        created_at=q.created_at or now,
        updated_at=q.updated_at or now,
    )
    db.add(row)
    db.commit()
    return _schema_from_row(row)


@router.patch("/{quest_id}", response_model=QuestSchema)
def patch_quest(quest_id: str, payload: PatchQuestRequest, db: Session = Depends(get_db)):
    row = db.get(QuestModel, quest_id)
    if not row:
        raise HTTPException(status_code=404, detail="Quest not found")
    if payload.status is not None:
        row.status = payload.status
    if payload.progress_value is not None:
        row.progress_minutes = max(0, int(payload.progress_value))
    row.updated_at = datetime.utcnow()
    db.add(row)
    db.commit()
    return _schema_from_row(row)


@router.post("/{quest_id}/result", response_model=QuestResultResponse)
def submit_quest_result(quest_id: str, payload: QuestResultRequest, db: Session = Depends(get_db)):
    row = db.get(QuestModel, quest_id)
    if not row or row.user_id != payload.user_id:
        raise HTTPException(status_code=404, detail="Quest not found")
    if payload.result not in ("success", "failure"):
        raise HTTPException(status_code=400, detail="result must be 'success' or 'failure'")
    db.add(QuestResultLog(user_id=payload.user_id, quest_id=quest_id, subject=row.subject, result=payload.result))
    db.delete(row)
    db.commit()
    return QuestResultResponse(ok=True)


@router.post("/{quest_id}/answer", response_model=QuestAnswerResponse)
def submit_quest_answer(quest_id: str, payload: QuestAnswerRequest, db: Session = Depends(get_db)):
    row = db.get(QuestModel, quest_id)
    if not row or row.user_id != payload.user_id:
        raise HTTPException(status_code=404, detail="Quest not found")
    try:
        meta = json.loads(row.meta_json) if row.meta_json else {}
    except Exception:
        meta = {}
    answers = _extract_answers(meta)
    if not answers:
        raise HTTPException(status_code=400, detail="Quest does not accept written answers")

    normalized_expected = {_normalized(ans): ans for ans in answers}
    normalized_input = _normalized(payload.answer)
    correct = normalized_input in normalized_expected
    explanation = meta.get("explanation")
    expected_display = normalized_expected.get(normalized_input) or answers[0]

    if correct:
        db.add(QuestResultLog(user_id=payload.user_id, quest_id=quest_id, subject=row.subject, result="success"))
        db.delete(row)
        db.commit()
    else:
        db.add(QuestResultLog(user_id=payload.user_id, quest_id=quest_id, subject=row.subject, result="failure"))
        db.commit()

    return QuestAnswerResponse(correct=correct, expected_answer=expected_display, explanation=explanation)
