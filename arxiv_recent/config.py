"""Application configuration via pydantic-settings."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=os.environ.get("ENV_FILE", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    # arXiv — comma-separated strings to avoid pydantic-settings JSON parse issues
    arxiv_categories_str: str = Field(default="cs.CL,cs.AI", alias="ARXIV_CATEGORIES")
    arxiv_include_keywords_str: str = Field(default="", alias="ARXIV_INCLUDE_KEYWORDS")
    arxiv_exclude_keywords_str: str = Field(default="", alias="ARXIV_EXCLUDE_KEYWORDS")
    max_papers_per_day: int = Field(default=50, ge=1, le=500)
    time_window_hours: int = Field(default=72, ge=1, le=168)

    # LLM
    vllm_url: str = Field(default="")
    vllm_model_name: str = Field(default="/mnt/ssd/model/Qwen3-VL-30B-A3B-Instruct-FP8")
    vllm_api_key: str = Field(default="")
    llm_max_concurrency: int = Field(default=4, ge=1, le=32)
    llm_rate_limit_rpm: int = Field(default=30, ge=1, le=600)

    # Database
    db_path: str = Field(default="data/arxiv_recent.db")

    # Email
    smtp_host: str = Field(default="")
    smtp_port: int = Field(default=587)
    smtp_user: str = Field(default="")
    smtp_pass: str = Field(default="")
    email_from: str = Field(default="")
    email_to: str = Field(default="")

    # Telegram
    telegram_bot_token: str = Field(default="")
    telegram_chat_id: str = Field(default="")

    # Push
    push_channels_str: str = Field(default="", alias="PUSH_CHANNELS")

    # Scheduler
    schedule_time: str = Field(default="08:30")
    schedule_tz: str = Field(default="America/Los_Angeles")

    @property
    def arxiv_categories(self) -> list[str]:
        return [s.strip() for s in self.arxiv_categories_str.split(",") if s.strip()]

    @property
    def arxiv_include_keywords(self) -> list[str]:
        return [s.strip() for s in self.arxiv_include_keywords_str.split(",") if s.strip()]

    @property
    def arxiv_exclude_keywords(self) -> list[str]:
        return [s.strip() for s in self.arxiv_exclude_keywords_str.split(",") if s.strip()]

    @property
    def push_channels(self) -> list[str]:
        return [s.strip() for s in self.push_channels_str.split(",") if s.strip()]

    @property
    def db_full_path(self) -> Path:
        p = Path(self.db_path)
        if not p.is_absolute():
            p = _project_root() / p
        return p

    @property
    def email_configured(self) -> bool:
        return bool(self.smtp_host and self.email_from and self.email_to)

    @property
    def telegram_configured(self) -> bool:
        return bool(self.telegram_bot_token and self.telegram_chat_id)


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    global _settings
    _settings = None
