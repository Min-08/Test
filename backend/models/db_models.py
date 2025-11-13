from __future__ import annotations

from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship

from ..database import Base


class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True)
    display_name = Column(String, nullable=False)
    daily_minutes_goal = Column(Integer, default=90)
    subject_ratio_json = Column(Text, default='{"국어":0.33,"수학":0.34,"영어":0.33}')


class Quest(Base):
    __tablename__ = "quests"
    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    type = Column(String, default="time")
    title = Column(String, nullable=False)
    subject = Column(String, nullable=False)  # 국어/수학/영어
    goal_value = Column(Integer, nullable=False)  # minutes target
    progress_minutes = Column(Integer, default=0)
    progress_seconds_remainder = Column(Integer, default=0)
    status = Column(String, default="pending")
    source = Column(String, default="user_defined")
    # tags_json: JSON string of English tags (e.g., ["problem-solving","review"])
    tags_json = Column(Text, nullable=True)
    # tags_ko_json: JSON string of Korean tags (e.g., ["문제풀이","복습"]) 
    tags_ko_json = Column(Text, nullable=True)
    # meta_json: arbitrary metadata for non-time quests (e.g., AI problem payload)
    meta_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TimerLog(Base):
    __tablename__ = "timer_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    quest_id = Column(String, ForeignKey("quests.id"), nullable=False)
    subject = Column(String, nullable=True)
    delta_seconds = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class QuestionLog(Base):
    __tablename__ = "question_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    subject = Column(String, nullable=False)
    text = Column(Text, nullable=False)
    difficulty = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class QuestResultLog(Base):
    __tablename__ = "quest_result_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    quest_id = Column(String, ForeignKey("quests.id"), nullable=False)
    subject = Column(String, nullable=False)
    result = Column(String, nullable=False)  # 'success' | 'failure'
    created_at = Column(DateTime, default=datetime.utcnow)

