from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class Quest(BaseModel):
    id: str
    user_id: str
    type: str = Field(default="time")
    title: str
    subject: str
    goal_value: int  # minutes target
    progress_value: int = 0
    status: str = Field(default="pending")  # pending | in_progress | completed
    source: str = Field(default="user_defined")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class TimerUpdateRequest(BaseModel):
    user_id: str
    delta_seconds: int
    quest_id: Optional[str] = None
    subject: Optional[str] = None  # "국어" | "수학" | "영어"


class QuestionLogIn(BaseModel):
    user_id: str
    subject: str
    text: str
    difficulty: Optional[str] = None


class QuestionLogOut(QuestionLogIn):
    id: str
    created_at: datetime


class SuggestionResponse(BaseModel):
    quests: List[dict] = []
    notes: List[str] = []


class ChatRequest(BaseModel):
    user_id: str
    text: str
    subject: Optional[str] = None
    difficulty: Optional[str] = None


class ChatResponse(BaseModel):
    answer: str
