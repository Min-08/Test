from fastapi import APIRouter, HTTPException, Query, Depends
from sqlalchemy.orm import Session

from ..models.schemas import QuestionLogIn, QuestionLogOut, SuggestionResponse, ChatRequest, ChatResponse
from ..models.db_models import QuestionLog, User
from ..database import get_db
from ..services.ai_service import handle_chat
from ..services.planner_service import generate_planner_response


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
    quests, notes = generate_planner_response(db, user, days=7)
    return SuggestionResponse(quests=quests, notes=notes)


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest):
    # All key handling on server side; frontend only sends question
    answer = handle_chat(payload.user_id, payload.text, subject=payload.subject, difficulty=payload.difficulty)
    return ChatResponse(answer=answer)
