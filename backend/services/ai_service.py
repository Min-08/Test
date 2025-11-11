from __future__ import annotations

from typing import Optional, Tuple
from textwrap import shorten
import json

from ..models.db_models import QuestionLog
from ..config import settings
from ..database import SessionLocal


SYSTEM_PROMPT = (
    "당신은 학생의 학습을 돕는 친절하고 간결한 튜터입니다. "
    "답변은 단계별로 짧고 명확하게 하며, 바로 적용할 수 있는 예시 1개를 포함하세요. "
    "어려운 용어는 간단히 풀어 설명하고, 마지막에 오개념 체크용 짧은 질문 1개를 추가하세요."
)


def _call_openai(messages: list[dict], *, model: Optional[str] = None) -> str:
    if not settings.OPENAI_API_KEY:
        return "[DEMO] OpenAI API 키가 설정되지 않았습니다. .env의 OPENAI_API_KEY를 설정하세요."
    try:
        # Lazy import to avoid dependency issues if not installed
        from openai import OpenAI  # type: ignore
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        resp = client.chat.completions.create(
            model=model or settings.OPENAI_MODEL,
            messages=messages,
            temperature=0.3,
            timeout=settings.OPENAI_TIMEOUT,
        )
        return resp.choices[0].message.content or ""
    except Exception as e:
        return f"[ERROR] AI 호출 실패: {e}"

def _classify_subject_and_difficulty(text: str) -> Tuple[str, str, str]:
    """Return (subject, difficulty, tier) where tier in {mini, full}.
    If API key missing or error, fallback to heuristic.
    """
    if not settings.OPENAI_API_KEY:
        # heuristic fallback
        t = text.lower()
        if any(k in t for k in ["미분", "적분", "방정식", "함수", "matrix", "integral", "derivative", "x^", "sqrt"]):
            subj = "수학"
        elif any(ch.isalpha() for ch in t) and sum(ch.isalpha() for ch in t) > len(t) * 0.4:
            subj = "영어"
        else:
            subj = "국어"
        difficulty = "hard" if len(text) > 200 or any(k in t for k in ["증명", "복잡", "어려움"]) else "medium"
        tier = "full" if difficulty == "hard" else "mini"
        return subj, difficulty, tier

    sys = "아래 질문을 보고 과목(국어/수학/영어)과 난이도(easy/medium/hard)를 판단하고, 사용할 모델 티어(mini/full)를 추천하세요. JSON으로만 답하세요. 예: {\"subject\":\"수학\",\"difficulty\":\"hard\",\"tier\":\"full\"}"
    user = text[:4000]
    msg = [{"role": "system", "content": sys}, {"role": "user", "content": user}]
    out = _call_openai(msg, model=settings.OPENAI_MODEL_CLASSIFY)
    try:
        data = json.loads(out)
        subj = data.get("subject") or "국어"
        diff = data.get("difficulty") or "medium"
        tier = data.get("tier") or ("full" if diff == "hard" else "mini")
        if subj not in ("국어", "수학", "영어"):
            subj = "국어"
        if diff not in ("easy", "medium", "hard"):
            diff = "medium"
        if tier not in ("mini", "full"):
            tier = "mini"
        return subj, diff, tier
    except Exception:
        # fallback heuristic
        return _classify_subject_and_difficulty(text)


def handle_chat(user_id: str, text: str, subject: Optional[str] = None, difficulty: Optional[str] = None) -> str:
    # Determine subject/difficulty if missing
    subj, diff, tier = subject or None, difficulty or None, None
    if subj is None or diff is None:
        subj_c, diff_c, tier_c = _classify_subject_and_difficulty(text)
        subj = subj or subj_c
        diff = diff or diff_c
        tier = tier_c
    else:
        # decide tier from provided difficulty
        tier = "full" if diff == "hard" else "mini"

    # Persist question log
    db = SessionLocal()
    try:
        row = QuestionLog(user_id=user_id, subject=subj, text=text, difficulty=diff)
        db.add(row)
        db.commit()
    finally:
        db.close()

    model_to_use = settings.OPENAI_MODEL_FULL if tier == "full" else settings.OPENAI_MODEL_MINI

    user_msg = shorten(text, width=6000, placeholder="…")
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"[과목: {subj}]\n{user_msg}"},
    ]
    return _call_openai(messages, model=model_to_use)
