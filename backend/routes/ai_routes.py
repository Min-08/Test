from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Dict, Any
from datetime import datetime, timedelta

from sqlalchemy.orm import Session
import json as pyjson

from ..models.schemas import QuestionLogIn, QuestionLogOut, SuggestionResponse, ChatRequest, ChatResponse
from ..models.db_models import QuestionLog, User, Quest, TimerLog
from ..database import get_db
from ..services.ai_service import handle_chat
from ..services.tagging_service import decide_tag_for_subject


router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/logs/questions", response_model=QuestionLogOut)
def add_question_log(payload: QuestionLogIn, db: Session = Depends(get_db)):
    user = db.get(User, payload.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    row = QuestionLog(user_id=payload.user_id, subject=payload.subject, text=payload.text, difficulty=payload.difficulty)
    db.add(row)
    db.commit()
    return QuestionLogOut(id=str(row.id), user_id=row.user_id, subject=row.subject, text=row.text, difficulty=row.difficulty, created_at=row.created_at)


@router.get("/planner/suggest", response_model=SuggestionResponse)
def suggest(user_id: str = Query(...), db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 3과목 고정 비율
    try:
        ratio = pyjson.loads(user.subject_ratio_json)
    except Exception:
        ratio = {"국어": 0.33, "수학": 0.34, "영어": 0.33}
    ratio = {k: ratio.get(k, 0.0) for k in ["국어", "수학", "영어"]}
    daily = int(user.daily_minutes_goal or 90)

    cutoff = datetime.utcnow() - timedelta(days=7)
    # 최근 7일 과목별 총 초 → 분 환산
    seconds_by_subject: Dict[str, int] = {"국어": 0, "수학": 0, "영어": 0}
    q_alias = db.query(Quest).subquery()
    logs = (
        db.query(TimerLog, Quest.subject)
        .join(Quest, Quest.id == TimerLog.quest_id)
        .filter(TimerLog.user_id == user_id, TimerLog.created_at >= cutoff)
        .all()
    )
    for log, subj in logs:
        if subj in seconds_by_subject:
            seconds_by_subject[subj] += int(log.delta_seconds or 0)
    minutes_by_subject = {k: v // 60 for k, v in seconds_by_subject.items()}

    suggestions = []
    notes = []
    # skip subjects that already have an active time quest
    active_subjects = {
        r.subject
        for r in db.query(Quest).filter(
            Quest.user_id == user_id,
            Quest.type == "time",
            Quest.status.in_(["pending", "in_progress"]),
        ).all()
    }
    # Allowed focus-time options
    ALLOWED = [25, 50, 90]
    for subj in ["국어", "수학", "영어"]:
        if subj in active_subjects:
            continue
        want = int(daily * float(ratio.get(subj, 0)))
        have = int(minutes_by_subject.get(subj, 0))
        # choose nearest allowed duration
        base = min(ALLOWED, key=lambda x: abs(x - max(1, want)))
        add = base
        if have < want * 0.8:
            # under-invested → pick next higher allowed if available
            higher = [x for x in ALLOWED if x > base]
            add = higher[0] if higher else base
            notes.append(f"{subj}: 최근7일 {have}분 < 목표 {want}분(80%) → +10분 보정")
        # decide single tag per subject using recent logs
        tags_en, tags_ko = decide_tag_for_subject(db, user_id, subj)
        # Avoid suggesting duplicate subject+tag if an active quest already exists with that tag
        dup = False
        for r in db.query(Quest).filter(
            Quest.user_id == user_id,
            Quest.subject == subj,
            Quest.type == "time",
            Quest.status.in_(["pending", "in_progress"]),
        ).all():
            try:
                import json as pyjson
                existing_ko = pyjson.loads(r.tags_ko_json) if r.tags_ko_json else []
                if tags_ko and tags_ko[0] in (existing_ko or []):
                    dup = True
                    break
            except Exception:
                continue
        if dup:
            continue
        suggestions.append({
            "id": f"sg_{subj}_{int(datetime.utcnow().timestamp())}",
            "type": "time",
            "title": f"{subj} 학습 {add}분",
            "subject": subj,
            "goal_value": add,
            "progress_value": 0,
            "status": "pending",
            "source": "ai_generated",
            "tags": tags_en,
            "tags_ko": tags_ko,
        })

    return SuggestionResponse(quests=suggestions, notes=notes)


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest):
    # All key handling on server side; frontend only sends question
    answer = handle_chat(payload.user_id, payload.text, subject=payload.subject, difficulty=payload.difficulty)
    return ChatResponse(answer=answer)
