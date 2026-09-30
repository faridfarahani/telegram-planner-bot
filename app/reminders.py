from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from aiogram import Bot

from .config import Settings
from .constants import REMINDER_PRESETS
from .db import Database
from .utils import day_code_for_date, fa_digits, jalali_date_label, weekday_label

logger = logging.getLogger(__name__)


def _slot_is_due(now: datetime, hhmm: str, grace_minutes: int) -> bool:
    hour, minute = (int(part) for part in hhmm.split(":"))
    scheduled = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    delta = now - scheduled
    grace_seconds = max(60, grace_minutes * 60)
    return 0 <= delta.total_seconds() < grace_seconds


def _summary_text(local_date: str, reminder_time: str, rows: list[dict]) -> str:
    lines = [
        "یادآوری پلن ها",
        f"{weekday_label(local_date)} {jalali_date_label(local_date)} - ساعت {fa_digits(reminder_time)}",
        "",
    ]

    for row in rows:
        count = int(row["tick_count"])
        required = int(row["required_ticks"])
        remaining = max(0, required - count)
        if remaining == 0:
            lines.append(f"✅ {row['name']} — {fa_digits(count)} از {fa_digits(required)} — کامل")
        else:
            lines.append(
                f"⏳ {row['name']} — {fa_digits(count)} از {fa_digits(required)} — "
                f"{fa_digits(remaining)} تیک مانده"
            )

    return "\n".join(lines)


async def run_reminder_loop(bot: Bot, db: Database, settings: Settings) -> None:
    while True:
        try:
            users = await db.list_users_with_reminders()
            for user in users:
                try:
                    timezone_name = user["timezone"] or settings.timezone
                    now = datetime.now(ZoneInfo(timezone_name))
                    local_date = now.date().isoformat()
                    day_code = day_code_for_date(now.date())

                    reminder_plans = await db.list_reminder_plans(int(user["id"]))
                    due_slots: set[str] = set()

                    for plan in reminder_plans:
                        if day_code not in set(plan["days"]):
                            continue
                        preset = plan["reminder_preset"]
                        for slot in REMINDER_PRESETS.get(preset, ()):
                            if _slot_is_due(now, slot, settings.reminder_grace_minutes):
                                due_slots.add(slot)

                    if not due_slots:
                        continue

                    summary_rows = await db.get_daily_summary(int(user["id"]), local_date, day_code)
                    if not summary_rows:
                        continue

                    for slot in sorted(due_slots):
                        already_sent = await db.reminder_already_sent(int(user["id"]), local_date, slot)
                        if already_sent:
                            continue

                        await bot.send_message(
                            chat_id=int(user["chat_id"]),
                            text=_summary_text(local_date, slot, summary_rows),
                        )
                        await db.mark_reminder_sent(int(user["id"]), local_date, slot)
                except Exception:
                    logger.exception("Failed to process reminder for user_id=%s", user.get("id"))
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Reminder loop iteration failed")

        await asyncio.sleep(20)
