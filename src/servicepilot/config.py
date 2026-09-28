"""Environment-only configuration; secrets never enter source control."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

from servicepilot.paths import DEFAULT_CHECKPOINT_PATH, DEFAULT_DB_PATH


@dataclass(frozen=True, slots=True)
class Settings:
    model_mode: str = "mock"
    model_name: str = ""
    api_key: str = ""
    base_url: str = ""
    temperature: float = 0.1
    db_path: str = str(DEFAULT_DB_PATH)
    checkpoint_path: str = str(DEFAULT_CHECKPOINT_PATH)
    checkpoint_mode: str = "sqlite"
    host: str = "127.0.0.1"
    port: int = 8000
    cors_origins: tuple[str, ...] = ("http://localhost:5173", "http://127.0.0.1:5173")

    @property
    def uses_real_model(self) -> bool:
        return self.model_mode == "openai_compatible"

    def validate_model(self) -> None:
        if not self.uses_real_model:
            return
        missing = [
            name
            for name, value in {
                "SERVICEPILOT_MODEL_NAME": self.model_name,
                "SERVICEPILOT_API_KEY": self.api_key,
            }.items()
            if not value
        ]
        if missing:
            raise ValueError(f"OpenAI 兼容模式缺少配置：{', '.join(missing)}")


def get_settings(*, reload_env: bool = False) -> Settings:
    load_dotenv(override=reload_env)
    origins = tuple(
        item.strip()
        for item in os.getenv(
            "SERVICEPILOT_CORS_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173",
        ).split(",")
        if item.strip()
    )
    return Settings(
        model_mode=os.getenv("SERVICEPILOT_MODEL_MODE", "mock").strip().lower(),
        model_name=os.getenv("SERVICEPILOT_MODEL_NAME", "").strip(),
        api_key=os.getenv("SERVICEPILOT_API_KEY", "").strip(),
        base_url=os.getenv("SERVICEPILOT_BASE_URL", "").strip(),
        temperature=float(os.getenv("SERVICEPILOT_TEMPERATURE", "0.1")),
        db_path=os.getenv("SERVICEPILOT_DB_PATH", str(DEFAULT_DB_PATH)),
        checkpoint_path=os.getenv("SERVICEPILOT_CHECKPOINT_PATH", str(DEFAULT_CHECKPOINT_PATH)),
        checkpoint_mode=os.getenv("SERVICEPILOT_CHECKPOINT_MODE", "sqlite").strip().lower(),
        host=os.getenv("SERVICEPILOT_HOST", "127.0.0.1"),
        port=int(os.getenv("SERVICEPILOT_PORT", "8000")),
        cors_origins=origins,
    )
