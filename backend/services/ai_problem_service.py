from __future__ import annotations

from typing import Dict, Any, List
from datetime import datetime
import json

from sqlalchemy.orm import Session

from ..config import settings
from ..constants import SUBJECT_KO_ENGLISH
from ..models.db_models import Quest


AI_TAG_KO = "AI문제"
AI_TAG_EN = "ai-problem"


def _fallback_vocab_problem() -> Dict[str, Any]:
    return {
        "title_suffix": "단어 테스트",
        "difficulty": "medium",
        "question": "단어 'serene'의 뜻을 한국어로 입력하세요.",
        "correct_answers": ["고요한", "평온한"],
        "answer": "고요한",
        "explanation": "serene = 고요하고 평온한 상태",
        "input_type": "text",
        "model": "demo",
    }


def _fallback_math_problem() -> Dict[str, Any]:
    return {
        "title_suffix": "이차방정식",
        "difficulty": "medium",
        "question": "방정식 x^2 - 5x + 6 = 0 의 해를 모두 입력하세요.",
        "correct_answers": ["x=2,3", "2,3", "x=2 x=3"],
        "answer": "x=2, 3",
        "explanation": "인수분해 (x-2)(x-3)=0",
        "input_type": "text",
        "model": "demo",
    }


def _call_openai_problem(subject: str) -> Dict[str, Any]:
    if not settings.OPENAI_API_KEY:
        return _fallback_vocab_problem() if subject == SUBJECT_KO_ENGLISH else _fallback_math_problem()
    try:
        from openai import OpenAI  # type: ignore
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        if subject == SUBJECT_KO_ENGLISH:
            sys = (
                "너는 영어 단어 테스트를 만드는 튜터다. 한 단어를 제시하고 학생이 한국어 뜻을 직접 입력하도록 하라."
                "JSON으로만 답하고 키는 title_suffix, difficulty, question, correct_answers(배열), explanation 이다."
            )
            user = "영어 단어 테스트 1개 생성"
        else:
            sys = (
                "너는 수학 계산 문제를 내는 튜터다. 학생이 숫자를 직접 입력하도록 하라."
                "JSON으로만 답하고 키는 title_suffix, difficulty, question, correct_answers(배열), explanation 이다."
            )
            user = "고등 수학 계산 문제 1개 생성"
        resp = client.chat.completions.create(
            model=settings.OPENAI_MODEL_FULL,
            temperature=0.4,
            messages=[{"role": "system", "content": sys}, {"role": "user", "content": user}],
        )
        data = json.loads(resp.choices[0].message.content or "{}")
        data.setdefault("correct_answers", [data.get("answer")] if data.get("answer") else [])
        data.setdefault("input_type", "text")
        data["model"] = settings.OPENAI_MODEL_FULL
        return data
    except Exception:
        return _fallback_vocab_problem() if subject == SUBJECT_KO_ENGLISH else _fallback_math_problem()


def _ensure_answer_list(payload: Dict[str, Any]) -> List[str]:
    answers = payload.get("correct_answers")
    if isinstance(answers, list) and answers:
        return [str(a).strip() for a in answers if str(a).strip()]
    if payload.get("answer"):
        return [str(payload["answer"]).strip()]
    return []


def generate_ai_problem_quest(db: Session, user_id: str, subject: str) -> Quest:
    # Enforce one active AI-problem quest per subject
    existing = (
        db.query(Quest)
        .filter(
            Quest.user_id == user_id,
            Quest.subject == subject,
            Quest.type == "problem",
            Quest.status.in_(["pending", "in_progress", "paused"]),
        )
        .first()
    )
    if existing:
        return existing

    payload = _call_openai_problem(subject)
    title_suffix = payload.get("title_suffix") or "AI 문제"
    title = f"{subject} {title_suffix}"
    answers = _ensure_answer_list(payload)

    q = Quest(
        id=f"ai_{subject}_{int(datetime.utcnow().timestamp())}",
        user_id=user_id,
        type="problem",
        title=title,
        subject=subject,
        goal_value=0,  # no time constraint
        status="pending",
        source="ai_generated",
        tags_json=json.dumps([AI_TAG_EN]),
        tags_ko_json=json.dumps([AI_TAG_KO]),
        meta_json=json.dumps({
            "kind": "ai_problem",
            "difficulty": payload.get("difficulty"),
            "question": payload.get("question") or payload.get("problem"),
            "answer": payload.get("answer"),
            "correct_answers": answers,
            "explanation": payload.get("explanation"),
            "input_type": payload.get("input_type", "text"),
            "model": payload.get("model"),
        }),
    )
    db.add(q)
    db.commit()
    return q
