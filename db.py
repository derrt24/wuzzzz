import json

import aiosqlite
from config import DB_PATH


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        # Проверяем, есть ли таблица со старой схемой
        cursor = await db.execute("PRAGMA table_info(users)")
        columns = await cursor.fetchall()
        col_names = [c[1] for c in columns]

        if "last_data" not in col_names:
            # Пересоздаём таблицу с новой схемой
            await db.execute("DROP TABLE IF EXISTS users")
            await db.commit()

        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                user_code TEXT NOT NULL,
                last_data TEXT DEFAULT '{}'
            )
        """)
        await db.commit()


async def add_user(telegram_id: int, user_code: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO users (telegram_id, user_code, last_data) "
            "VALUES (?, ?, '{}')",
            (telegram_id, user_code),
        )
        await db.commit()


async def get_all_users():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM users")
        return await cursor.fetchall()


async def get_user(telegram_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
        )
        return await cursor.fetchone()


async def update_last_data(telegram_id: int, data: dict):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET last_data = ? WHERE telegram_id = ?",
            (json.dumps(data, ensure_ascii=False), telegram_id),
        )
        await db.commit()


async def get_last_data(telegram_id: int) -> dict:
    user = await get_user(telegram_id)
    if user and user["last_data"]:
        return json.loads(user["last_data"])
    return {}
