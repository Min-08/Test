from __future__ import annotations

from pathlib import Path
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session


DB_PATH = Path(__file__).resolve().parent / "app.db"
DATABASE_URL = f"sqlite:///{DB_PATH.as_posix()}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from .models import db_models  # noqa: F401 ensure models are imported
    Base.metadata.create_all(bind=engine)
    # Lightweight migration for new columns introduced after initial creation
    try:
        with engine.connect() as conn:
            rows = conn.exec_driver_sql("PRAGMA table_info(quests)").fetchall()
            cols = [row[1] for row in rows]
            if "tags_json" not in cols:
                conn.exec_driver_sql("ALTER TABLE quests ADD COLUMN tags_json TEXT")
            if "tags_ko_json" not in cols:
                conn.exec_driver_sql("ALTER TABLE quests ADD COLUMN tags_ko_json TEXT")
            if "meta_json" not in cols:
                conn.exec_driver_sql("ALTER TABLE quests ADD COLUMN meta_json TEXT")
            rows = conn.exec_driver_sql("PRAGMA table_info(timer_logs)").fetchall()
            timer_cols = [row[1] for row in rows]
            if "subject" not in timer_cols:
                conn.exec_driver_sql("ALTER TABLE timer_logs ADD COLUMN subject TEXT")
    except Exception:
        # Ignore migration errors in MVP
        pass

