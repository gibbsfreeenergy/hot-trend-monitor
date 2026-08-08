from __future__ import annotations

import os
from dataclasses import dataclass


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    app_env: str = os.getenv("APP_ENV", "development")
    app_port: int = _int("APP_PORT", 8080)
    database_url: str = os.getenv("DATABASE_URL", "")
    redis_url: str = os.getenv("REDIS_URL", "")
    newsnow_api_url: str = os.getenv(
        "NEWSNOW_API_URL", "https://newsnow.busiyi.world/api/s"
    )
    newsnow_xhs_id: str = os.getenv("NEWSNOW_XHS_ID", "xiaohongshu")
    xhs_trend_url: str = os.getenv("XHS_TREND_URL", "")
    xhs_cookie: str = os.getenv("XHS_COOKIE", "")
    http_proxy_url: str = os.getenv("HTTP_PROXY_URL", "")
    collect_interval_seconds: int = max(60, _int("COLLECT_INTERVAL_SECONDS", 120))
    collect_on_startup: bool = _bool("COLLECT_ON_STARTUP", True)
    allow_sample_fallback: bool = _bool("ALLOW_SAMPLE_FALLBACK", True)
    log_level: str = os.getenv("LOG_LEVEL", "INFO")


settings = Settings()

