from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    bot_token: str
    timezone: str
    database_path: Path
    reminder_grace_minutes: int
    telegram_proxy: str | None


def load_settings() -> Settings:
    load_dotenv()

    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN is not configured. Copy .env.example to .env and set BOT_TOKEN.")

    timezone = os.getenv("BOT_TIMEZONE", "Asia/Tehran").strip() or "Asia/Tehran"
    database_path = Path(os.getenv("DATABASE_PATH", "data/plan_bot.sqlite3")).expanduser()
    reminder_grace_minutes = int(os.getenv("REMINDER_GRACE_MINUTES", "10"))
    telegram_proxy = os.getenv("TELEGRAM_PROXY", "").strip() or None

    if reminder_grace_minutes < 0 or reminder_grace_minutes > 60:
        raise RuntimeError("REMINDER_GRACE_MINUTES must be between 0 and 60.")

    return Settings(
        bot_token=token,
        timezone=timezone,
        database_path=database_path,
        reminder_grace_minutes=reminder_grace_minutes,
        telegram_proxy=telegram_proxy,
    )
