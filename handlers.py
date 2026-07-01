import re

from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from db import add_user, get_user, update_last_data
from parser import fetch_all

router = Router()


class Registration(StatesGroup):
    waiting_for_code = State()


# Код поступающего — цифры, 6-8 знаков
CODE_PATTERN = re.compile(r"^\d{6,8}$")


def validate_code(code: str) -> bool:
    return bool(CODE_PATTERN.match(code.strip()))


def format_results(data: dict[str, list[dict]]) -> str:
    """Форматирует результаты поиска по всем вузам."""
    if not data:
        return "❌ Ваш код не найден ни в одном из вузов."

    lines: list[str] = []
    for university, programs in data.items():
        lines.append(f"🏛 <b>{university}</b>")
        lines.append("")
        for p in programs:
            lines.append(f"  🎓 {p['program_name']}")
            lines.append(f"     🏅 Место: {p['position']}")
            lines.append(f"     📄 С оригиналами: {p['position_original']}")
            if p.get("score"):
                lines.append(f"     📊 Баллы: {p['score']}")
            if p.get("priority"):
                lines.append(f"     🔢 Приоритет: {p['priority']}")
            if p.get("competitor_count") is not None:
                lines.append(f"     ⚔️ Реальных конкурентов: {p['competitor_count']}")
            if p.get("total_budget"):
                lines.append(f"     💰 Бюджетных мест: {p['total_budget']}")
            if p.get("total_applications"):
                lines.append(f"     👥 Всего заявлений: {p['total_applications']}")
            lines.append("")
        lines.append("")

    return "\n".join(lines)


def build_change_message(program_name: str, old: dict, new: dict) -> str:
    diff = new["position"] - old["position"]
    arrow = "🔻" if diff > 0 else "🔺"
    msg = (
        f"⚠️ <b>Внимание! Изменилась позиция!</b>\n"
        f"🏛 {new.get('university', '')}\n"
        f"🎓 {new.get('program_name', program_name)}\n"
        f"{arrow} Старое место: {old['position']} (оригиналы: {old['position_original']})\n"
        f"{arrow} <b>Новое место: {new['position']}</b> (оригиналы: {new['position_original']})"
    )
    old_comp = old.get("competitor_count")
    new_comp = new.get("competitor_count")
    if old_comp is not None and new_comp is not None and old_comp != new_comp:
        msg += f"\n⚔️ Конкурентов: {old_comp} → {new_comp}"
    elif new_comp is not None:
        msg += f"\n⚔️ Реальных конкурентов: {new_comp}"
    return msg


def make_check_keyboard():
    return types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(
                text="🔍 Проверить позиции сейчас",
                callback_data="check_positions"
            )]
        ]
    )


@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    user = await get_user(message.from_user.id)
    if user:
        await message.answer(
            f"👋 С возвращением! Ваш код: <code>{user['user_code']}</code>\n"
            "Используйте /my_status для проверки позиций.",
            reply_markup=make_check_keyboard(),
        )
        return

    await message.answer(
        "👋 Добро пожаловать в бот мониторинга конкурсных списков!\n\n"
        "Я проверяю ваши позиции одновременно в двух вузах:\n"
        "🏛 <b>СПбПУ (Политех)</b> и <b>СПбГУ</b>\n\n"
        "Пожалуйста, введите ваш уникальный код поступающего "
        "(6-8 цифр) — его можно посмотреть в личном кабинете абитуриента."
    )
    await state.set_state(Registration.waiting_for_code)


@router.message(Registration.waiting_for_code)
async def process_code(message: types.Message, state: FSMContext):
    code = message.text.strip()
    if not validate_code(code):
        await message.answer(
            "❌ Некорректный формат. Введите уникальный код поступающего "
            "(6-8 цифр) из личного кабинета."
        )
        return

    await add_user(message.from_user.id, code)
    await state.clear()

    await message.answer(
        f"✅ Код <code>{code}</code> сохранён!",
        reply_markup=make_check_keyboard(),
    )


@router.message(Command("my_status"))
async def cmd_my_status(message: types.Message):
    user = await get_user(message.from_user.id)
    if not user:
        await message.answer("❌ Вы не зарегистрированы. Отправьте /start")
        return

    msg = await message.answer("⏳ Запрашиваю данные с сайтов вузов...")

    try:
        data = await fetch_all(user["user_code"])
    except Exception as e:
        await msg.edit_text(f"⚠️ Ошибка при получении данных: {e}")
        return

    if not data:
        await msg.edit_text(
            "❌ Ваш код не найден ни в одном из вузов.\n"
            "Возможно, списки ещё не опубликованы."
        )
        return

    await update_last_data(message.from_user.id, data)
    await msg.edit_text(
        format_results(data),
        parse_mode="HTML",
        reply_markup=make_check_keyboard(),
    )


@router.callback_query(lambda c: c.data == "check_positions")
async def callback_check_positions(callback: types.CallbackQuery):
    await callback.answer()
    user = await get_user(callback.from_user.id)
    if not user:
        await callback.message.edit_text("❌ Вы не зарегистрированы. Отправьте /start")
        return

    await callback.message.edit_text("⏳ Запрашиваю данные с сайтов вузов...")

    try:
        data = await fetch_all(user["user_code"])
    except Exception as e:
        await callback.message.edit_text(f"⚠️ Ошибка при получении данных: {e}")
        return

    if not data:
        await callback.message.edit_text(
            "❌ Ваш код не найден ни в одном из вузов."
        )
        return

    await update_last_data(callback.from_user.id, data)
    await callback.message.edit_text(
        format_results(data),
        parse_mode="HTML",
        reply_markup=make_check_keyboard(),
    )


@router.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "ℹ️ <b>Доступные команды:</b>\n"
        "/start — регистрация / повторная регистрация\n"
        "/my_status — проверить текущие позиции\n"
        "/help — эта справка\n\n"
        "Бот проверяет <b>все специальности</b> в:\n"
        "🏛 СПбПУ (Политех) — my.spbstu.ru\n"
        "🏛 СПбГУ — enrollelists.spbu.ru\n\n"
        "Автоматический мониторинг — каждые 30 минут.",
        parse_mode="HTML",
    )
