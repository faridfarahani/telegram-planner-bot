from __future__ import annotations

import asyncio
import contextlib
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import TelegramNetworkError
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from app.config import load_settings
from app.db import Database
from app.handlers import build_router
from app.reminders import run_reminder_loop


LOGGER = logging.getLogger(__name__)


async def prepare_telegram(bot: Bot) -> None:
    """Prepare bot API state and tolerate temporary Telegram connectivity failures."""
    while True:
        try:
            await bot.get_me()
            await bot.set_my_commands([BotCommand(command="start", description="شروع")])
            await bot.delete_webhook(drop_pending_updates=False)
            return
        except TelegramNetworkError as exc:
            LOGGER.error(
                "Cannot connect to Telegram API. Check internet/VPN/proxy. "
                "Retrying in 10 seconds. Error: %s",
                exc,
            )
            await asyncio.sleep(10)


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    settings = load_settings()
    db = Database(settings.database_path)
    await db.init()

    session = AiohttpSession(proxy=settings.telegram_proxy) if settings.telegram_proxy else AiohttpSession()
    bot = Bot(token=settings.bot_token, session=session)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(build_router(db, settings))

    reminder_task: asyncio.Task | None = None

    try:
        if settings.telegram_proxy:
            LOGGER.info("Telegram proxy is enabled.")

        await prepare_telegram(bot)

        reminder_task = asyncio.create_task(
            run_reminder_loop(bot, db, settings),
            name="reminder-loop",
        )

        LOGGER.info("Telegram bot is connected and polling started.")
        await dp.start_polling(bot)
    finally:
        if reminder_task is not None:
            reminder_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await reminder_task
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
