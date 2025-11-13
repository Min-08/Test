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
    # total seconds progress (minutes*60 + remainder), for smooth UI updates
    progress_seconds: Optional[int] = None
    status: str = Field(default="pending")  # pending | in_progress | completed
    source: str = Field(default="user_defined")
    # English tags (e.g., ["problem-solving","english-vocabulary","review","english-listening"]) 
    tags: Optional[List[str]] = None
    # Korean tags (e.g., ["문제풀이","단어암기(영어)","복습","듣기(영어)"]) 
    tags_ko: Optional[List[str]] = None
    # Optional metadata for AI/problem quests (problem text, answer, hints, etc.)
    meta: Optional[dict] = None
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


class QuestResultRequest(BaseModel):
    user_id: str
    result: str  # 'success' | 'failure'


class QuestResultResponse(BaseModel):
    ok: bool


class PatchQuestRequest(BaseModel):
    status: Optional[str] = None
    progress_value: Optional[int] = None


class QuestAnswerRequest(BaseModel):
    user_id: str
    answer: str


class QuestAnswerResponse(BaseModel):
    correct: bool
    expected_answer: Optional[str] = None
    explanation: Optional[str] = None
