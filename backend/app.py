from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import json

from .routes.quest_routes import router as quest_router
from .routes.timer_routes import router as timer_router
from .routes.ai_routes import router as ai_router
from .routes.stats_routes import router as stats_router
from .routes.admin_routes import router as admin_router
from .database import init_db, SessionLocal
from .models.db_models import User, Quest


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
        # Initialize DB tables
        init_db()
        # Seed default user and quests if empty
        db = SessionLocal()
        try:
            user = db.get(User, "u1")
            if not user:
                user = User(id="u1", display_name="Demo User", daily_minutes_goal=90,
                            subject_ratio_json='{"국어":0.33,"수학":0.34,"영어":0.33}')
                db.add(user)
                db.commit()
            # Seed quests
            seed_path = Path(__file__).resolve().parents[1] / "data" / "seed_quests.json"
            if seed_path.exists():
                with seed_path.open("r", encoding="utf-8") as f:
                    quests = json.load(f)
                for q in quests:
                    if not db.get(Quest, q["id"]):
                        db.add(Quest(
                            id=q["id"], user_id=q["user_id"], type=q.get("type","time"), title=q["title"],
                            subject=q.get("subject","기타"), goal_value=int(q["goal_value"]),
                            progress_minutes=int(q.get("progress_value",0)),
                            status=q.get("status","pending"), source=q.get("source","ai_generated")
                        ))
                db.commit()
        except Exception:
            pass
        finally:
            db.close()

    app.include_router(quest_router)
    app.include_router(timer_router)
    app.include_router(ai_router)
    app.include_router(stats_router)
    app.include_router(admin_router)
    return app


app = create_app()
