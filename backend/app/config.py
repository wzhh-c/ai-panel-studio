"""Application configuration — reads environment variables via Pydantic Settings."""

import logging
import sys

from pydantic_settings import BaseSettings, SettingsConfigDict


def setup_logging(level: int = logging.INFO) -> None:
    """Configure root logger with a stdout stream handler.

    Args:
        level: Logging level (default: INFO).
    """
    root = logging.getLogger()
    root.setLevel(level)

    if not root.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        fmt = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(fmt)
        root.addHandler(handler)


class Settings(BaseSettings):
    """Global settings loaded from .env and environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── DeepSeek API ──────────────────────────────────────
    DEEPSEEK_API_KEY: str
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"

    # ── Database ──────────────────────────────────────────
    DATABASE_URL: str = "sqlite:///./panel.db"

    # ── LLM ───────────────────────────────────────────────
    LLM_MODEL: str = "deepseek-v4-pro"


settings = Settings()
setup_logging()
