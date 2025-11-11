from __future__ import annotations

from typing import Dict, Any
from datetime import datetime
import json

from sqlalchemy.orm import Session

from ..config import settings
from ..models.db_models import Quest


AI_TAG_KO = "AI문제"
AI_TAG_EN = "ai-problem"


def _call_openai_math_problem(subject: str) -> Dict[str, Any]:
    if not settings.OPENAI_API_KEY:
        # Fallback demo payload
        return {
            "title_suffix": "이차방정식 풀이",
            "difficulty": "medium",
            "problem": "다음 이차방정식 x^2 - 5x + 6 = 0 의 해를 구하시오.",
            "answer": "x=2, 3",
            "explanation": "인수분해: (x-2)(x-3)=0",
            "model": "demo",
        }
    try:
        from openai import OpenAI  # type: ignore
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        sys = (
            "너는 수학 튜터다. 학생에게 풀 문제 1개를 JSON 형태로 만들어라."
            "중등~고등 수준의 문제를 간결히 제시하고, 정답과 한 줄 풀이 요약을 포함해라."
            "출력은 JSON이며 키는 title_suffix, difficulty(easy|medium|hard), problem, answer, explanation 이다."
        )
        user = "수학 문제 1개 생성"
        resp = client.chat.completions.create(
            model=settings.OPENAI_MODEL_FULL,
            temperature=0.4,
            messages=[{"role": "system", "content": sys}, {"role": "user", "content": user}],
        )
        content = resp.choices[0].message.content or "{}"
        data = json.loads(content)
        data["model"] = settings.OPENAI_MODEL_FULL
        return data
    except Exception as e:
        return {
            "title_suffix": "연립방정식 풀이",
            "difficulty": "medium",
            "problem": "연립방정식 x+y=5, x-y=1 을 풀어 x, y 값을 구하시오.",
            "answer": "x=3, y=2",
            "explanation": "가감법으로 해결",
            "model": f"error:{e}",
        }


def generate_ai_problem_quest(db: Session, user_id: str, subject: str) -> Quest:
    # Enforce one active AI-problem quest per subject
    existing = (
        db.query(Quest)
        .filter(
            Quest.user_id == user_id,
            Quest.subject == subject,
            Quest.type == "problem",
            Quest.status.in_(["pending", "in_progress"]),
        )
        .first()
    )
    if existing:
        return existing

    payload = _call_openai_math_problem(subject)
    title_suffix = payload.get("title_suffix") or "AI 문제"
    title = f"{subject} {title_suffix}"

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
            "problem": payload.get("problem"),
            "answer": payload.get("answer"),
            "explanation": payload.get("explanation"),
            "model": payload.get("model"),
        }),
    )
    db.add(q)
    db.commit()
    return q

