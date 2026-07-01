"""
Точка входа в Телеграм-бота для мониторинга конкурсных списков.
Поддерживаются: СПбПУ (Политех), СПбГУ.
"""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import BOT_TOKEN, MONITOR_INTERVAL_MINUTES
from db import init_db
from handlers import router
from monitor import monitor_users

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    if BOT_TOKEN == "ВАШ_ТОКЕН_СЮДА":
        logger.error("❌ Не указан BOT_TOKEN! Вставьте токен в config.py")
        return

    await init_db()
    logger.info("База данных инициализирована.")

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        monitor_users,
        trigger="interval",
        minutes=MONITOR_INTERVAL_MINUTES,
        kwargs={"bot": bot},
        id="monitor_all",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Мониторинг запущен (каждые %d мин).", MONITOR_INTERVAL_MINUTES)

    asyncio.create_task(monitor_users(bot))

    logger.info("Бот запущен...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
