# bot.py — простой бот «подписка → дата → имя → подтверждение»
import os
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor

# === ВАЖНО: ЗАПОЛНИ ЭТИ ДВЕ СТРОКИ ===
API_TOKEN = "8260960372:AAFMrTN7DUrYhD_E-D1hF1l5ZTPuu679zP8"   # пример: "1234567890:AA..."; можно хранить в переменной BOT_TOKEN
CHANNEL   = "@slavicruna"               # можно @username ИЛИ числовой ID вида -1002552649165
# =====================================

# Если хочешь брать токен из переменной окружения на Render — раскомментируй:
# API_TOKEN = os.getenv("BOT_TOKEN") or API_TOKEN

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN, parse_mode=types.ParseMode.HTML)
dp  = Dispatcher(bot)

# Память шагов на время работы процесса
user_state = {}   # user_id -> "waiting_date" | {"date": "...", "step": "waiting_name"} | ...

def gate_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("Открыть канал", url=f"https://t.me/{CHANNEL.lstrip('@')}"),
        InlineKeyboardButton("Подписался", callback_data="check_sub")
    )
    return kb

def confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup().add(
        InlineKeyboardButton("Данные верны", callback_data="confirm_data")
    )

@dp.message_handler(commands=["start"])
async def start_cmd(message: types.Message):
    await message.answer(
        "Привет! 🌿 Чтобы получить руну, подпишитесь на наш канал:\n"
        f"{'@'+CHANNEL.lstrip('@')}\n\n"
        "После подписки нажмите кнопку 👇 «Подписался».",
        reply_markup=gate_kb()
    )

@dp.callback_query_handler(lambda c: c.data == "check_sub")
async def check_sub(call: types.CallbackQuery):
    uid = call.from_user.id
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL, user_id=uid)
        if member.status in ("member", "administrator", "creator"):
            user_state[uid] = "waiting_date"
            try:
                await call.message.edit_reply_markup()  # уберём кнопки под старым сообщением
            except Exception:
                pass
            await bot.send_message(uid, "Введите вашу дату рождения (например: 05.11.1992) ⤵️")
        else:
            await call.answer("Похоже, подписки ещё нет 🙈", show_alert=True)
    except Exception as e:
        logging.warning(f"get_chat_member error: {e}")
        await call.answer("Не удалось проверить подписку, попробуйте ещё раз.", show_alert=True)

@dp.message_handler(lambda m: user_state.get(m.from_user.id) == "waiting_date")
async def get_date(message: types.Message):
    uid = message.from_user.id
    date_text = (message.text or "").strip()
    # Мини-валидация: ДД.ММ.ГГГГ
    import re
    if not re.fullmatch(r"(0?[1-9]|[12]\d|3[01])\.(0?[1-9]|1[0-2])\.(19\d{2}|20\d{2})", date_text):
        await message.answer("Формат даты: <b>ДД.ММ.ГГГГ</b> (например: 05.11.1992).")
        return
    user_state[uid] = {"date": date_text, "step": "waiting_name"}
    await message.answer("Отлично 🌿 Теперь введите ваше имя ⤵️")

@dp.message_handler(lambda m: isinstance(user_state.get(m.from_user.id), dict) and user_state[m.from_user.id].get("step") == "waiting_name")
async def get_name(message: types.Message):
    uid = message.from_user.id
    name = (message.text or "").strip()
    if not (2 <= len(name) <= 40):
        await message.answer("Имя должно быть длиной 2–40 символов. Попробуйте ещё раз 🙂")
        return
    data = user_state.get(uid, {})
    data["name"] = name
    data["step"] = "confirm"
    user_state[uid] = data
    await message.answer(
        f"Проверьте данные:\n"
        f"📅 Дата: <b>{data['date']}</b>\n"
        f"👤 Имя: <b>{data['name']}</b>\n\n"
        f"Если всё верно — нажмите кнопку ниже 👇",
        reply_markup=confirm_kb()
    )

@dp.callback_query_handler(lambda c: c.data == "confirm_data")
async def confirm_data(call: types.CallbackQuery):
    uid = call.from_user.id
    data = user_state.get(uid, {})
    if data.get("step") != "confirm":
        await call.answer("Нет данных для подтверждения. Нажмите /start", show_alert=True)
        return
    try:
        await call.message.edit_reply_markup()
    except Exception:
        pass
    # Здесь ты вручную потом отвечаешь пользователю (как ты и хотела)
    await bot.send_message(
        uid,
        "Спасибо 🌿 Мы приняли вашу дату рождения и имя.\n"
        "Так как всё обрабатывается вручную, нужно немного подождать 🙌"
    )
    # почистим состояние
    user_state.pop(uid, None)

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
