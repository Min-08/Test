from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import json

from sqlalchemy.orm import Session

from ..models.db_models import QuestionLog, Quest


TAG_MAP: Dict[str, str] = {
    "학습": "study",
    "복습": "review",
    "문제풀이": "problem-solving",
    "단어암기(영어)": "english-vocabulary",
    "듣기(영어)": "english-listening",
    "독해(영어)": "english-reading",
}

KEYWORDS: Dict[str, Dict[str, List[str]]] = {
    "영어": {
        "듣기(영어)": ["듣기", "리스닝", "listening", "shadowing", "발음", "dictation", "lc", "audio", "podcast"],
        "단어암기(영어)": ["단어", "어휘", "vocabulary", "vocab", "암기", "word list", "flashcard", "anki"],
        "독해(영어)": ["독해", "reading", "comprehension", "passage", "지문", "rc"],
        "복습": ["복습", "요약", "정리", "summary", "revise"],
    },
    "수학": {
        "문제풀이": ["문제", "풀이", "연습문제", "기출", "equation", "integral", "derivative", "matrix", "증명"],
        "복습": ["복습", "요약", "정리", "개념 정리", "summary", "revise"],
    },
    "국어": {
        "복습": ["복습", "요약", "정리", "개념 정리", "summary", "revise"],
    },
}


def _count_keywords(texts: List[str], keywords: List[str]) -> int:
    lowered = [t.lower() for t in texts]
    count = 0
    for kw in keywords:
        needle = kw.lower()
        count += sum(1 for text in lowered if needle in text)
    return count


def decide_tag_for_subject(db: Session, user_id: str, subject: str, days: int = 7) -> Tuple[List[str], List[str]]:
    cutoff = datetime.utcnow() - timedelta(days=days)
    logs = (
        db.query(QuestionLog)
        .filter(QuestionLog.user_id == user_id, QuestionLog.created_at >= cutoff)
        .all()
    )
    subject_logs = [log for log in logs if (log.subject or subject) == subject]
    texts = [log.text or "" for log in subject_logs]

    keyword_map = KEYWORDS.get(subject, {})
    scores: Dict[str, int] = {}
    for tag, keywords in keyword_map.items():
        scores[tag] = _count_keywords(texts, keywords)

    hard_logs = [log for log in subject_logs if (log.difficulty or "").lower() == "hard"]
    if subject == "수학" and hard_logs:
        scores["문제풀이"] = scores.get("문제풀이", 0) + 1
    if subject == "영어" and hard_logs:
        listening_keywords = keyword_map.get("듣기(영어)", [])
        if _count_keywords([log.text or "" for log in hard_logs], listening_keywords):
            scores["듣기(영어)"] = scores.get("듣기(영어)", 0) + 1
        else:
            scores["복습"] = scores.get("복습", 0) + 1
    if subject == "국어" and hard_logs:
        scores["복습"] = scores.get("복습", 0) + 1

    if scores:
        tag, value = max(scores.items(), key=lambda item: item[1])
        if value >= 2:
            return [TAG_MAP.get(tag, "study")], [tag]

    if subject == "영어" and _count_keywords(texts, keyword_map.get("독해(영어)", [])) >= 1:
        return [TAG_MAP["독해(영어)"]], ["독해(영어)"]

    return [TAG_MAP["학습"]], ["학습"]


def has_active_subject_tag(db: Session, user_id: str, subject: str, ko_tag: str) -> Quest | None:
    """Return the first quest that already uses the requested Korean tag, or None."""
    rows = (
        db.query(Quest)
        .filter(
            Quest.user_id == user_id,
            Quest.subject == subject,
            Quest.type == "time",
            Quest.status.in_(["pending", "in_progress", "paused"]),
        )
        .all()
    )
    for row in rows:
        try:
            tags_ko = json.loads(row.tags_ko_json) if row.tags_ko_json else []
            if ko_tag in tags_ko:
                return row
        except Exception:
            continue
    return None
