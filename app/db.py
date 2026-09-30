from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite

from .utils import day_code_for_date, local_now


class Database:
    def __init__(self, path: Path):
        self.path = path

    @asynccontextmanager
    async def _connect(self):
        connection = await aiosqlite.connect(self.path)
        connection.row_factory = aiosqlite.Row
        await connection.execute("PRAGMA foreign_keys = ON")
        await connection.execute("PRAGMA busy_timeout = 5000")
        try:
            yield connection
        finally:
            await connection.close()

    async def init(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)

        async with self._connect() as db:
            await db.execute("PRAGMA journal_mode = WAL")
            await db.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_user_id INTEGER NOT NULL UNIQUE,
                    chat_id INTEGER NOT NULL,
                    username TEXT NULL,
                    first_name TEXT NULL,
                    timezone TEXT NOT NULL DEFAULT 'Asia/Tehran',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS plans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    required_ticks INTEGER NOT NULL CHECK (required_ticks BETWEEN 1 AND 5),
                    reminder_preset TEXT NULL CHECK (reminder_preset IS NULL OR reminder_preset IN ('a', 'b', 'c')),
                    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS plan_days (
                    plan_id INTEGER NOT NULL,
                    day_code TEXT NOT NULL CHECK (day_code IN ('sat','sun','mon','tue','wed','thu','fri')),
                    PRIMARY KEY (plan_id, day_code),
                    FOREIGN KEY (plan_id) REFERENCES plans(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS tick_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    plan_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    ticked_at_utc TEXT NOT NULL,
                    local_date TEXT NOT NULL,
                    local_time TEXT NOT NULL,
                    required_ticks_snapshot INTEGER NOT NULL,
                    FOREIGN KEY (plan_id) REFERENCES plans(id) ON DELETE CASCADE,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_tick_logs_plan_date
                    ON tick_logs(plan_id, local_date);

                CREATE INDEX IF NOT EXISTS idx_tick_logs_user_date
                    ON tick_logs(user_id, local_date);

                CREATE TABLE IF NOT EXISTS reminder_deliveries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    local_date TEXT NOT NULL,
                    reminder_time TEXT NOT NULL,
                    sent_at_utc TEXT NOT NULL,
                    UNIQUE (user_id, local_date, reminder_time),
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                );
                """
            )
            await db.commit()

    async def upsert_user(
        self,
        telegram_user_id: int,
        chat_id: int,
        username: str | None,
        first_name: str | None,
        timezone_name: str,
    ) -> int:
        now = datetime.now(timezone.utc).isoformat()
        async with self._connect() as db:
            await db.execute(
                """
                INSERT INTO users (
                    telegram_user_id, chat_id, username, first_name, timezone, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(telegram_user_id) DO UPDATE SET
                    chat_id = excluded.chat_id,
                    username = excluded.username,
                    first_name = excluded.first_name,
                    timezone = excluded.timezone,
                    updated_at = excluded.updated_at
                """,
                (telegram_user_id, chat_id, username, first_name, timezone_name, now, now),
            )
            await db.commit()
            cursor = await db.execute(
                "SELECT id FROM users WHERE telegram_user_id = ?",
                (telegram_user_id,),
            )
            row = await cursor.fetchone()
            return int(row["id"])

    async def list_plans(self, telegram_user_id: int) -> list[dict[str, Any]]:
        async with self._connect() as db:
            cursor = await db.execute(
                """
                SELECT p.id, p.name, p.required_ticks, p.reminder_preset
                FROM plans p
                JOIN users u ON u.id = p.user_id
                WHERE u.telegram_user_id = ? AND p.is_active = 1
                ORDER BY p.id ASC
                """,
                (telegram_user_id,),
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_plan(self, telegram_user_id: int, plan_id: int) -> dict[str, Any] | None:
        async with self._connect() as db:
            cursor = await db.execute(
                """
                SELECT p.id, p.name, p.required_ticks, p.reminder_preset
                FROM plans p
                JOIN users u ON u.id = p.user_id
                WHERE p.id = ? AND u.telegram_user_id = ? AND p.is_active = 1
                """,
                (plan_id, telegram_user_id),
            )
            row = await cursor.fetchone()
            if not row:
                return None

            days_cursor = await db.execute(
                "SELECT day_code FROM plan_days WHERE plan_id = ?",
                (plan_id,),
            )
            days = [item["day_code"] for item in await days_cursor.fetchall()]
            result = dict(row)
            result["days"] = days
            return result

    async def create_plan(
        self,
        telegram_user_id: int,
        name: str,
        required_ticks: int,
        days: list[str],
    ) -> int:
        if not name.strip():
            raise ValueError("Plan name is required")
        if required_ticks not in {1, 2, 3, 4, 5}:
            raise ValueError("required_ticks must be between 1 and 5")
        if not days:
            raise ValueError("At least one day is required")

        now = datetime.now(timezone.utc).isoformat()
        async with self._connect() as db:
            await db.execute("BEGIN IMMEDIATE")
            cursor = await db.execute(
                "SELECT id FROM users WHERE telegram_user_id = ?",
                (telegram_user_id,),
            )
            user = await cursor.fetchone()
            if not user:
                await db.rollback()
                raise RuntimeError("User not initialized")

            plan_cursor = await db.execute(
                """
                INSERT INTO plans (user_id, name, required_ticks, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user["id"], name.strip(), required_ticks, now, now),
            )
            plan_id = int(plan_cursor.lastrowid)
            await db.executemany(
                "INSERT INTO plan_days (plan_id, day_code) VALUES (?, ?)",
                [(plan_id, day) for day in sorted(set(days))],
            )
            await db.commit()
            return plan_id

    async def get_today_tick_count(self, telegram_user_id: int, plan_id: int, timezone_name: str) -> int:
        local_date = local_now(timezone_name).date().isoformat()
        async with self._connect() as db:
            cursor = await db.execute(
                """
                SELECT COUNT(*) AS count
                FROM tick_logs t
                JOIN users u ON u.id = t.user_id
                WHERE u.telegram_user_id = ? AND t.plan_id = ? AND t.local_date = ?
                """,
                (telegram_user_id, plan_id, local_date),
            )
            row = await cursor.fetchone()
            return int(row["count"])

    async def add_tick(
        self,
        telegram_user_id: int,
        plan_id: int,
        timezone_name: str,
    ) -> dict[str, Any]:
        now_local = local_now(timezone_name)
        local_date = now_local.date().isoformat()
        local_time = now_local.strftime("%H:%M:%S")
        day_code = day_code_for_date(now_local.date())
        utc_now = datetime.now(timezone.utc).isoformat()

        async with self._connect() as db:
            await db.execute("BEGIN IMMEDIATE")

            cursor = await db.execute(
                """
                SELECT p.id, p.required_ticks, p.name, u.id AS user_id
                FROM plans p
                JOIN users u ON u.id = p.user_id
                WHERE p.id = ? AND u.telegram_user_id = ? AND p.is_active = 1
                """,
                (plan_id, telegram_user_id),
            )
            plan = await cursor.fetchone()
            if not plan:
                await db.rollback()
                return {"status": "not_found"}

            day_cursor = await db.execute(
                "SELECT 1 FROM plan_days WHERE plan_id = ? AND day_code = ?",
                (plan_id, day_code),
            )
            if not await day_cursor.fetchone():
                await db.rollback()
                return {"status": "not_scheduled", "name": plan["name"]}

            count_cursor = await db.execute(
                "SELECT COUNT(*) AS count FROM tick_logs WHERE plan_id = ? AND local_date = ?",
                (plan_id, local_date),
            )
            current_count = int((await count_cursor.fetchone())["count"])
            required_ticks = int(plan["required_ticks"])

            if current_count >= required_ticks:
                await db.rollback()
                return {
                    "status": "complete",
                    "count": current_count,
                    "required": required_ticks,
                    "name": plan["name"],
                }

            await db.execute(
                """
                INSERT INTO tick_logs (
                    plan_id, user_id, ticked_at_utc, local_date, local_time, required_ticks_snapshot
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    plan_id,
                    plan["user_id"],
                    utc_now,
                    local_date,
                    local_time,
                    required_ticks,
                ),
            )
            await db.commit()
            new_count = current_count + 1
            return {
                "status": "added",
                "count": new_count,
                "required": required_ticks,
                "name": plan["name"],
            }

    async def get_plan_history(
        self,
        telegram_user_id: int,
        plan_id: int,
        limit: int = 40,
    ) -> list[dict[str, Any]]:
        async with self._connect() as db:
            cursor = await db.execute(
                """
                SELECT * FROM (
                    SELECT
                        t.id,
                        t.local_date,
                        t.local_time,
                        t.required_ticks_snapshot,
                        ROW_NUMBER() OVER (
                            PARTITION BY t.local_date
                            ORDER BY t.id ASC
                        ) AS ordinal
                    FROM tick_logs t
                    JOIN users u ON u.id = t.user_id
                    WHERE u.telegram_user_id = ? AND t.plan_id = ?
                ) history
                ORDER BY id DESC
                LIMIT ?
                """,
                (telegram_user_id, plan_id, limit),
            )
            return [dict(row) for row in await cursor.fetchall()]

    async def delete_plan(self, telegram_user_id: int, plan_id: int) -> bool:
        """Soft-delete a plan while preserving its historical tick data."""
        now = datetime.now(timezone.utc).isoformat()
        async with self._connect() as db:
            cursor = await db.execute(
                """
                UPDATE plans
                SET is_active = 0, updated_at = ?
                WHERE id = ?
                  AND user_id = (SELECT id FROM users WHERE telegram_user_id = ?)
                  AND is_active = 1
                """,
                (now, plan_id, telegram_user_id),
            )
            await db.commit()
            return cursor.rowcount == 1

    async def update_plan_name(self, telegram_user_id: int, plan_id: int, name: str) -> bool:
        name = name.strip()
        if not name:
            return False
        now = datetime.now(timezone.utc).isoformat()
        async with self._connect() as db:
            cursor = await db.execute(
                """
                UPDATE plans
                SET name = ?, updated_at = ?
                WHERE id = ?
                  AND user_id = (SELECT id FROM users WHERE telegram_user_id = ?)
                  AND is_active = 1
                """,
                (name, now, plan_id, telegram_user_id),
            )
            await db.commit()
            return cursor.rowcount == 1

    async def update_plan_days(self, telegram_user_id: int, plan_id: int, days: list[str]) -> bool:
        if not days:
            return False
        now = datetime.now(timezone.utc).isoformat()
        async with self._connect() as db:
            await db.execute("BEGIN IMMEDIATE")
            cursor = await db.execute(
                """
                SELECT p.id
                FROM plans p
                JOIN users u ON u.id = p.user_id
                WHERE p.id = ? AND u.telegram_user_id = ? AND p.is_active = 1
                """,
                (plan_id, telegram_user_id),
            )
            if not await cursor.fetchone():
                await db.rollback()
                return False

            await db.execute("DELETE FROM plan_days WHERE plan_id = ?", (plan_id,))
            await db.executemany(
                "INSERT INTO plan_days (plan_id, day_code) VALUES (?, ?)",
                [(plan_id, day) for day in sorted(set(days))],
            )
            await db.execute("UPDATE plans SET updated_at = ? WHERE id = ?", (now, plan_id))
            await db.commit()
            return True

    async def update_required_ticks(self, telegram_user_id: int, plan_id: int, required_ticks: int) -> bool:
        if required_ticks not in {1, 2, 3, 4, 5}:
            return False
        now = datetime.now(timezone.utc).isoformat()
        async with self._connect() as db:
            cursor = await db.execute(
                """
                UPDATE plans
                SET required_ticks = ?, updated_at = ?
                WHERE id = ?
                  AND user_id = (SELECT id FROM users WHERE telegram_user_id = ?)
                  AND is_active = 1
                """,
                (required_ticks, now, plan_id, telegram_user_id),
            )
            await db.commit()
            return cursor.rowcount == 1

    async def update_reminder_preset(self, telegram_user_id: int, plan_id: int, preset: str) -> bool:
        if preset not in {"a", "b", "c"}:
            return False
        now = datetime.now(timezone.utc).isoformat()
        async with self._connect() as db:
            cursor = await db.execute(
                """
                UPDATE plans
                SET reminder_preset = ?, updated_at = ?
                WHERE id = ?
                  AND user_id = (SELECT id FROM users WHERE telegram_user_id = ?)
                  AND is_active = 1
                """,
                (preset, now, plan_id, telegram_user_id),
            )
            await db.commit()
            return cursor.rowcount == 1

    async def list_users_with_reminders(self) -> list[dict[str, Any]]:
        async with self._connect() as db:
            cursor = await db.execute(
                """
                SELECT DISTINCT u.id, u.telegram_user_id, u.chat_id, u.timezone
                FROM users u
                JOIN plans p ON p.user_id = u.id
                WHERE p.is_active = 1 AND p.reminder_preset IS NOT NULL
                """
            )
            return [dict(row) for row in await cursor.fetchall()]

    async def list_reminder_plans(self, internal_user_id: int) -> list[dict[str, Any]]:
        async with self._connect() as db:
            cursor = await db.execute(
                """
                SELECT p.id, p.name, p.required_ticks, p.reminder_preset, d.day_code
                FROM plans p
                JOIN plan_days d ON d.plan_id = p.id
                WHERE p.user_id = ? AND p.is_active = 1 AND p.reminder_preset IS NOT NULL
                ORDER BY p.id ASC
                """,
                (internal_user_id,),
            )
            rows = await cursor.fetchall()

        grouped: dict[int, dict[str, Any]] = {}
        for row in rows:
            plan_id = int(row["id"])
            if plan_id not in grouped:
                grouped[plan_id] = {
                    "id": plan_id,
                    "name": row["name"],
                    "required_ticks": int(row["required_ticks"]),
                    "reminder_preset": row["reminder_preset"],
                    "days": [],
                }
            grouped[plan_id]["days"].append(row["day_code"])
        return list(grouped.values())

    async def reminder_already_sent(self, internal_user_id: int, local_date: str, reminder_time: str) -> bool:
        async with self._connect() as db:
            cursor = await db.execute(
                """
                SELECT 1 FROM reminder_deliveries
                WHERE user_id = ? AND local_date = ? AND reminder_time = ?
                """,
                (internal_user_id, local_date, reminder_time),
            )
            return await cursor.fetchone() is not None

    async def mark_reminder_sent(self, internal_user_id: int, local_date: str, reminder_time: str) -> None:
        async with self._connect() as db:
            await db.execute(
                """
                INSERT OR IGNORE INTO reminder_deliveries (
                    user_id, local_date, reminder_time, sent_at_utc
                ) VALUES (?, ?, ?, ?)
                """,
                (internal_user_id, local_date, reminder_time, datetime.now(timezone.utc).isoformat()),
            )
            await db.commit()

    async def get_daily_summary(self, internal_user_id: int, local_date: str, day_code: str) -> list[dict[str, Any]]:
        async with self._connect() as db:
            cursor = await db.execute(
                """
                SELECT
                    p.id,
                    p.name,
                    p.required_ticks,
                    COUNT(t.id) AS tick_count
                FROM plans p
                JOIN plan_days d ON d.plan_id = p.id AND d.day_code = ?
                LEFT JOIN tick_logs t
                    ON t.plan_id = p.id
                   AND t.local_date = ?
                WHERE p.user_id = ? AND p.is_active = 1
                GROUP BY p.id, p.name, p.required_ticks
                ORDER BY p.id ASC
                """,
                (day_code, local_date, internal_user_id),
            )
            return [dict(row) for row in await cursor.fetchall()]
