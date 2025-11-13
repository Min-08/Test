from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence
import json
import re

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..config import settings
from ..constants import SUBJECTS, STUDY_TAG, STUDY_TAG_KO
from ..models.db_models import (
    Quest,
    QuestionLog,
    QuestResultLog,
    TimerLog,
    User,
)
from ..services.tagging_service import decide_tag_for_subject
from ..services.goal_policy import DEFAULT_ALLOWED_MINUTES, resolve_goal_minutes

ALLOWED_MINUTES: Sequence[int] = DEFAULT_ALLOWED_MINUTES
EXCLUDED_TAGS = {"study"}
PLANNER_SYSTEM_PROMPT = (
    "너는 학습 스케줄러 AI다. 입력 JSON을 바탕으로 과목별 추천 학습 퀘스트를 결정해라. "
    "출력은 반드시 JSON이며 형식은 {\"recommendations\": [...], \"notes\": [...]} 뿐이다. "
    "각 추천 항목은 subject/title/minutes/primary_tag_ko 필드를 포함해야 한다. "
    "minutes 값은 allowed_minutes 중 하나여야 하며, subject는 allowed_subjects 중 하나여야 한다. "
    "필요하면 primary_tag_en, reason을 추가할 수 있다. 한 과목당 1개의 추천만 허용한다."
)


def _safe_ratio(user: User) -> Dict[str, float]:
    try:
        raw = json.loads(user.subject_ratio_json or "{}")
    except Exception:
        raw = {}
    ratio: Dict[str, float] = {}
    for subj in SUBJECTS:
        value = float(raw.get(subj, 0))
        ratio[subj] = value
    total = sum(ratio.values())
    if total <= 0:
        equal = 1 / len(SUBJECTS)
        return {subj: equal for subj in SUBJECTS}
    return ratio


def _subject_minutes(db: Session, user_id: str, days: int) -> Dict[str, int]:
    cutoff = datetime.utcnow() - timedelta(days=days)
    subject_expr = func.coalesce(TimerLog.subject, Quest.subject)
    rows = (
        db.query(subject_expr.label("subject"), func.sum(TimerLog.delta_seconds))
        .outerjoin(Quest, Quest.id == TimerLog.quest_id)
        .filter(TimerLog.user_id == user_id, TimerLog.created_at >= cutoff)
        .group_by(subject_expr)
        .all()
    )
    data = {subj: 0 for subj in SUBJECTS}
    for subj, value in rows:
        if subj in data:
            data[subj] = int((value or 0) // 60)
    return data


def _active_time_quests(db: Session, user_id: str) -> List[Quest]:
    return (
        db.query(Quest)
        .filter(
            Quest.user_id == user_id,
            Quest.type == "time",
            Quest.status.in_(["pending", "in_progress", "paused"]),
        )
        .all()
    )


def _collect_tag_catalog(db: Session) -> List[Dict[str, str]]:
    catalog: List[Dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    rows = db.query(Quest.tags_json, Quest.tags_ko_json).all()
    for tags_json, tags_ko_json in rows:
        tags = []
        tags_ko = []
        if tags_json:
            try:
                tags = json.loads(tags_json)
            except Exception:
                tags = []
        if tags_ko_json:
            try:
                tags_ko = json.loads(tags_ko_json)
            except Exception:
                tags_ko = []
        for ko_tag in tags_ko or []:
            en_tag = tags[0] if tags else None
            key = (ko_tag, en_tag or "")
            if key in seen:
                continue
            seen.add(key)
            catalog.append({"ko": ko_tag, "en": en_tag or ""})
    if not any(item["ko"] == STUDY_TAG_KO for item in catalog):
        catalog.append({"ko": STUDY_TAG_KO, "en": STUDY_TAG})
    return catalog


def _recent_questions(db: Session, user_id: str, days: int, limit_per_subject: int = 5) -> Dict[str, List[str]]:
    cutoff = datetime.utcnow() - timedelta(days=days)
    rows = (
        db.query(QuestionLog)
        .filter(QuestionLog.user_id == user_id, QuestionLog.created_at >= cutoff)
        .order_by(QuestionLog.created_at.desc())
        .all()
    )
    bucket: Dict[str, List[str]] = {subj: [] for subj in SUBJECTS}
    for row in rows:
        subj = row.subject or SUBJECTS[0]
        if subj not in bucket:
            bucket[subj] = []
        if len(bucket[subj]) < limit_per_subject:
            bucket[subj].append(row.text)
    return bucket


def _recent_results(db: Session, user_id: str, days: int, limit: int = 5) -> List[Dict[str, Any]]:
    cutoff = datetime.utcnow() - timedelta(days=days)
    rows = (
        db.query(QuestResultLog)
        .filter(QuestResultLog.user_id == user_id, QuestResultLog.created_at >= cutoff)
        .order_by(QuestResultLog.created_at.desc())
        .limit(limit)
        .all()
    )
    out: List[Dict[str, Any]] = []
    for row in rows:
        out.append(
            {
                "quest_id": row.quest_id,
                "subject": row.subject,
                "result": row.result,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
        )
    return out


def _slugify_tag(tag: str) -> str:
    slug = re.sub(r"[^0-9A-Za-z]+", "-", tag.strip()).strip("-")
    return slug.lower() or "custom"


def _ko_to_en(tag_ko: str, catalog: List[Dict[str, str]]) -> str:
    for item in catalog:
        if item["ko"] == tag_ko and item["en"]:
            return item["en"]
    return _slugify_tag(tag_ko)


def _make_quest_dict(subject: str, minutes: int, tag_en: str, tag_ko: str, title: str, reason: Optional[str] = None) -> Dict[str, Any]:
    identifier = f"sg_{subject}_{int(datetime.utcnow().timestamp())}_{abs(hash(title)) % 10000}"
    quest = {
        "id": identifier,
        "type": "time",
        "title": title,
        "subject": subject,
        "goal_value": minutes,
        "progress_value": 0,
        "status": "pending",
        "source": "ai_generated",
        "tags": [tag_en],
        "tags_ko": [tag_ko],
    }
    if reason:
        quest["meta"] = {"ai_reason": reason}
    return quest


def build_planner_context(db: Session, user: User, user_id: str, days: int = 7) -> Dict[str, Any]:
    ratio = _safe_ratio(user)
    daily_goal = int(user.daily_minutes_goal or 90)
    minutes_by_subject = _subject_minutes(db, user_id, days)
    target_by_subject = {subj: max(1, int(daily_goal * ratio.get(subj, 0))) for subj in SUBJECTS}
    active_quests = _active_time_quests(db, user_id)
    active_subjects = {q.subject for q in active_quests}
    active_tags: Dict[str, List[str]] = {subj: [] for subj in SUBJECTS}
    for quest in active_quests:
        if quest.tags_ko_json:
            try:
                tags_ko = json.loads(quest.tags_ko_json)
            except Exception:
                tags_ko = []
        else:
            tags_ko = []
        active_tags.setdefault(quest.subject, [])
        active_tags[quest.subject].extend(tags_ko)
    question_digest = _recent_questions(db, user_id, days)
    result_digest = _recent_results(db, user_id, days)
    tag_catalog = _collect_tag_catalog(db)
    return {
        "user": {
            "id": user.id,
            "daily_goal": daily_goal,
            "subject_ratio": ratio,
        },
        "subjects": list(SUBJECTS),
        "allowed_minutes": list(ALLOWED_MINUTES),
        "minutes_by_subject": minutes_by_subject,
        "target_minutes": target_by_subject,
        "active_subjects": list(active_subjects),
        "active_tags": active_tags,
        "question_digest": question_digest,
        "result_digest": result_digest,
        "tag_catalog": tag_catalog,
        "days_window": days,
    }


def _is_study_like(tags: List[str] | None, tags_ko: List[str] | None) -> bool:
    tags = tags or []
    tags_ko = tags_ko or []
    return (STUDY_TAG in tags) or (STUDY_TAG_KO in tags_ko) or any(tag in EXCLUDED_TAGS for tag in tags)


def _baseline_suggestions(db: Session, user_id: str, context: Dict[str, Any]) -> tuple[List[Dict[str, Any]], List[str]]:
    suggestions: List[Dict[str, Any]] = []
    notes: List[str] = []
    ratio = context["user"]["subject_ratio"]
    daily_goal = context["user"]["daily_goal"]
    minutes_by_subject = context["minutes_by_subject"]
    active_subjects = set(context["active_subjects"])
    for subject in context["subjects"]:
        if subject in active_subjects:
            continue
        want = max(1, int(daily_goal * float(ratio.get(subject, 0))))
        have = int(minutes_by_subject.get(subject, 0))
        mode = "ceil" if have < want * 0.8 else "nearest"
        minutes = resolve_goal_minutes(
            {"preferred": want, "mode": mode},
            {"allowed_minutes": ALLOWED_MINUTES},
        )
        if mode == "ceil":
            notes.append(f"{subject}: 최근 {context['days_window']}일 {have}분 < 목표 {want}분(80%) → 상향 추천")
        tags_en, tags_ko = decide_tag_for_subject(db, user_id, subject)
        # Avoid duplicate KO tags already active
        if tags_ko and tags_ko[0] in context["active_tags"].get(subject, []):
            continue
        if _is_study_like(tags_en, tags_ko):
            # Daily study cards are treated as goals, not suggestions
            continue
        title = f"{subject} {tags_ko[0] if tags_ko else '학습'} {minutes}분"
        suggestions.append(
            _make_quest_dict(
                subject,
                minutes,
                (tags_en or [STUDY_TAG])[0],
                (tags_ko or [STUDY_TAG_KO])[0],
                title,
            )
        )
    return suggestions, notes


def planner_payload_for_ai(context: Dict[str, Any], baseline: List[Dict[str, Any]], notes: List[str]) -> Dict[str, Any]:
    return {
        "user": context["user"],
        "subjects": context["subjects"],
        "allowed_minutes": context["allowed_minutes"],
        "minutes_by_subject": context["minutes_by_subject"],
        "target_minutes": context["target_minutes"],
        "active_subjects": context["active_subjects"],
        "active_tags": context["active_tags"],
        "recent_questions": context["question_digest"],
        "recent_results": context["result_digest"],
        "baseline": baseline,
        "baseline_notes": notes,
        "window_days": context["days_window"],
        "tag_catalog": context["tag_catalog"],
    }


def _call_planner_ai(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not settings.OPENAI_API_KEY:
        return None
    try:
        from openai import OpenAI  # type: ignore
    except Exception:
        return None
    try:
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL_FULL,
            temperature=0.2,
            messages=[
                {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps(payload, ensure_ascii=False, separators=(",", ":"))[:6000],
                },
            ],
        )
        content = response.choices[0].message.content or ""
        return json.loads(content)
    except Exception:
        return None


def _normalize_ai_response(
    data: Dict[str, Any],
    context: Dict[str, Any],
) -> List[Dict[str, Any]]:
    allowed_subjects = set(context["subjects"])
    active_subjects = set(context["active_subjects"])
    allowed_minutes = context["allowed_minutes"]
    tag_catalog = context["tag_catalog"]
    recommendations = data.get("recommendations", [])
    normalized: List[Dict[str, Any]] = []
    used_subjects: set[str] = set()
    for entry in recommendations:
        subject = entry.get("subject")
        if subject not in allowed_subjects:
            continue
        if subject in active_subjects or subject in used_subjects:
            continue
        minutes_raw = entry.get("minutes")
        try:
            minutes = int(minutes_raw)
        except Exception:
            continue
        minutes = max(1, minutes)
        minutes = min(allowed_minutes, key=lambda m: abs(m - minutes))
        tag_ko = entry.get("primary_tag_ko") or entry.get("tag_ko") or STUDY_TAG_KO
        tag_en = entry.get("primary_tag_en") or entry.get("tag") or _ko_to_en(tag_ko, tag_catalog)
        if _is_study_like([tag_en], [tag_ko]):
            continue
        title = entry.get("title") or f"{subject} {tag_ko} {minutes}분"
        reason = entry.get("reason")
        normalized.append(_make_quest_dict(subject, minutes, tag_en, tag_ko, title, reason))
        used_subjects.add(subject)
    return normalized


def generate_planner_response(db: Session, user: User, days: int = 7) -> tuple[List[Dict[str, Any]], List[str]]:
    context = build_planner_context(db, user, user.id, days=days)
    baseline, baseline_notes = _baseline_suggestions(db, user.id, context)
    payload = planner_payload_for_ai(context, baseline, baseline_notes)
    ai_raw = _call_planner_ai(payload)
    if ai_raw:
        ai_recs = _normalize_ai_response(ai_raw, context)
        if ai_recs:
            notes = ai_raw.get("notes") or []
            if baseline_notes:
                notes = baseline_notes + notes
            return ai_recs, notes
    return baseline, baseline_notes
