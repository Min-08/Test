from __future__ import annotations

from fastapi import APIRouter, Query, Depends
from typing import Dict, List
from datetime import datetime, timedelta

from sqlalchemy.orm import Session
from sqlalchemy import func

from ..database import get_db
from ..models.db_models import TimerLog, Quest


router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/summary")
def summary(user_id: str = Query(...), days: int = Query(7, ge=1, le=30), db: Session = Depends(get_db)):
    cutoff = datetime.utcnow() - timedelta(days=days)

    # 과목별 총합(분)
    rows = (
        db.query(Quest.subject, func.sum(TimerLog.delta_seconds))
        .join(Quest, Quest.id == TimerLog.quest_id)
        .filter(TimerLog.user_id == user_id, TimerLog.created_at >= cutoff)
        .group_by(Quest.subject)
        .all()
    )
    totals_by_subject: Dict[str, int] = {"국어": 0, "수학": 0, "영어": 0}
    for subj, sec_sum in rows:
        if subj in totals_by_subject:
            totals_by_subject[subj] = int((sec_sum or 0) // 60)

    # 일별 합계(분)
    daily: List[Dict] = []
    for i in range(days):
        d = (datetime.utcnow() - timedelta(days=(days - 1 - i))).date()
        day_start = datetime.combine(d, datetime.min.time())
        day_end = day_start + timedelta(days=1)
        day_rows = (
            db.query(Quest.subject, func.sum(TimerLog.delta_seconds))
            .join(Quest, Quest.id == TimerLog.quest_id)
            .filter(TimerLog.user_id == user_id, TimerLog.created_at >= day_start, TimerLog.created_at < day_end)
            .group_by(Quest.subject)
            .all()
        )
        mb = {"국어": 0, "수학": 0, "영어": 0}
        for subj, sec_sum in day_rows:
            if subj in mb:
                mb[subj] = int((sec_sum or 0) // 60)
        daily.append({"date": d.isoformat(), "minutes_by_subject": mb, "total_minutes": sum(mb.values())})

    # 연속 학습일 수(최근부터 역순): 하루 총합 > 0 인 날 연속 카운트
    streak = 0
    for item in reversed(daily):
        if item["total_minutes"] > 0:
            streak += 1
        else:
            break

    return {
        "range_days": days,
        "totals_by_subject": totals_by_subject,
        "total_minutes": sum(totals_by_subject.values()),
        "daily": daily,
        "streak_days": streak,
    }
