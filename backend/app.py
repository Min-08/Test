from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import json

from .routes.quest_routes import router as quest_router
from .routes.timer_routes import router as timer_router
from .routes.ai_routes import router as ai_router
from .routes.ai_problem_routes import router as ai_problem_router
from .routes.stats_routes import router as stats_router
from .routes.admin_routes import router as admin_router
from .database import init_db, SessionLocal
from .models.db_models import User, Quest
from .constants import (
    SUBJECT_KO_KOREAN,
    DEFAULT_SUBJECT_RATIO_JSON,
)


def create_app() -> FastAPI:
    app = FastAPI(title="Personalized Learning Quest Planner", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    async def startup_event():
        init_db()
        db = SessionLocal()
        try:
            user = db.get(User, "u1")
            if not user:
                user = User(
                    id="u1",
                    display_name="Demo User",
                    daily_minutes_goal=90,
                    subject_ratio_json=DEFAULT_SUBJECT_RATIO_JSON,
                )
                db.add(user)
                db.commit()
            elif user.subject_ratio_json != DEFAULT_SUBJECT_RATIO_JSON:
                user.subject_ratio_json = DEFAULT_SUBJECT_RATIO_JSON
                db.add(user)
                db.commit()

            seed_path = Path(__file__).resolve().parents[1] / "data" / "seed_quests.json"
            if seed_path.exists():
                with seed_path.open("r", encoding="utf-8") as handle:
                    quests = json.load(handle)
                for q in quests:
                    if db.get(Quest, q["id"]):
                        continue
                    db.add(
                        Quest(
                            id=q["id"],
                            user_id=q.get("user_id", "u1"),
                            type=q.get("type", "time"),
                            title=q.get("title", "Unnamed Quest"),
                            subject=q.get("subject", SUBJECT_KO_KOREAN),
                            goal_value=int(q.get("goal_value", 0)),
                            progress_minutes=int(q.get("progress_value", 0)),
                            status=q.get("status", "pending"),
                            source=q.get("source", "ai_generated"),
                            tags_json=json.dumps(q.get("tags") or []),
                            tags_ko_json=json.dumps(q.get("tags_ko") or []),
                            meta_json=json.dumps(q.get("meta") or {}),
                        )
                    )
                db.commit()

            # Any lingering in-progress time quests should start as paused when server boots
            db.query(Quest).filter(Quest.type == "time", Quest.status == "in_progress").update({"status": "paused"})
            db.commit()
        finally:
            db.close()

    app.include_router(quest_router)
    app.include_router(timer_router)
    app.include_router(ai_router)
    app.include_router(ai_problem_router)
    app.include_router(stats_router)
    app.include_router(admin_router)
    return app


app = create_app()
