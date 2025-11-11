from __future__ import annotations

import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    # dotenv is optional for runtime; continue if unavailable
    pass


@dataclass
class Settings:
    OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY")
    # Classification and answer model names (override as needed)
    OPENAI_MODEL_CLASSIFY: str = os.getenv("OPENAI_MODEL_CLASSIFY", "gpt-5-nano")
    OPENAI_MODEL_MINI: str = os.getenv("OPENAI_MODEL_MINI", "gpt-5-mini")
    OPENAI_MODEL_FULL: str = os.getenv("OPENAI_MODEL_FULL", "gpt-5")
    # Backward-compat default
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-5-mini")
    OPENAI_TIMEOUT: int = int(os.getenv("OPENAI_TIMEOUT", "30"))


settings = Settings()
