import logging

from aiogram import Bot

from db import get_all_users, update_last_data, get_last_data
from parser import fetch_all

logger = logging.getLogger(__name__)


def _program_key(item: dict) -> str:
    """Уникальный ключ для программы: университет + название."""
    return f"{item.get('university', '')}||{item.get('program_name', '')}"


def _build_change_message(item: dict, old: dict) -> str:
    diff = item["position"] - old["position"]
    arrow = "🔻" if diff > 0 else "🔺"
    msg = (
        f"⚠️ <b>Внимание! Изменилась позиция!</b>\n"
        f"🏛 {item.get('university', '')}\n"
        f"🎓 {item.get('program_name', '')}\n"
        f"{arrow} Старое место: {old['position']} (оригиналы: {old['position_original']})\n"
        f"{arrow} <b>Новое место: {item['position']}</b> (оригиналы: {item['position_original']})"
    )
    old_comp = old.get("competitor_count")
    new_comp = item.get("competitor_count")
    if old_comp is not None and new_comp is not None and old_comp != new_comp:
        msg += f"\n⚔️ Конкурентов: {old_comp} → {new_comp}"
    elif new_comp is not None:
        msg += f"\n⚔️ Реальных конкурентов: {new_comp}"
    return msg


async def monitor_users(bot: Bot):
    logger.info("Запуск мониторинга...")
    users = await get_all_users()

    for user in users:
        telegram_id = user["telegram_id"]
        user_code = user["user_code"]

        try:
            new_data = await fetch_all(user_code)
        except Exception as e:
            logger.error("Ошибка парсинга для %s: %s", telegram_id, e)
            continue

        if not new_data:
            continue

        old_data = await get_last_data(telegram_id)

        # Собираем все новые записи в плоский список по ключу
        new_flat: dict[str, dict] = {}
        for uni, items in new_data.items():
            for item in items:
                new_flat[_program_key(item)] = item

        # Собираем старые записи
        old_flat: dict[str, dict] = {}
        for uni, items in old_data.items():
            for item in items:
                old_flat[_program_key(item)] = item

        changes_detected = False
        for key, item in new_flat.items():
            old = old_flat.get(key)
            if old and (
                old["position"] != item["position"]
                or old["position_original"] != item["position_original"]
                or old.get("competitor_count") != item.get("competitor_count")
            ):
                changes_detected = True
                try:
                    await bot.send_message(
                        telegram_id,
                        _build_change_message(item, old),
                        parse_mode="HTML",
                    )
                except Exception as e:
                    logger.error("Ошибка уведомления %s: %s", telegram_id, e)

        if changes_detected or not old_data:
            await update_last_data(telegram_id, new_data)

    logger.info("Мониторинг завершён.")
