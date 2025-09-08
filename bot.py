# bot.py
import re
import logging
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# === ДАННЫЕ БОТА И КАНАЛА ===
API_TOKEN = "7744951627:AAGCKM9htp-7WmWntjeYKPq1G1wbUVcym0Y"
CHANNEL_ID = -1002293023304   # ID канала "Славянская Руна. Без мистики..."
# =============================

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN, parse_mode="HTML")
dp = Dispatcher(bot)

# Память для диалога
user_data = {}

def box(uid: int) -> dict:
    return user_data.setdefault(uid, {})

def set_step(uid: int, step: str) -> None:
    box(uid)['step'] = step

def get_step(uid: int):
    return box(uid).get('step')

# Проверки
DATE_RE = re.compile(r"^([0-2]\d|3[01])\.(0\d|1[0-2])\.(19\d{2}|20\d{2})$")
NAME_RE = re.compile(r"^[A-Za-zА-Яа-яЁё\- ]{2,40}$")

# Кнопки
def gate_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("Открыть канал", url="https://t.me/slavicruna"))
    kb.add(InlineKeyboardButton("Подписался", callback_data="check_sub"))
    return kb

def confirm_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("Данные введены", callback_data="confirm"))
    return kb

# Проверка подписки
async def is_subscribed(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in ("member", "administrator", "creator")
    except Exception as e:
        logging.warning(f"get_chat_member failed: {e}")
        return False

# Хэндлеры
@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    uid = message.from_user.id
    if await is_subscribed(uid):
        set_step(uid, "date")
        await message.answer("Отлично! Введите дату рождения в формате <b>ДД.ММ.ГГГГ</b> (например, 05.11.1992).")
    else:
        set_step(uid, None)
        await message.answer(
            "Привет! 🌿 Чтобы получить руну, подпишитесь на наш канал:\n"
            "https://t.me/slavicruna\n\nПосле подписки нажмите кнопку 👇 «Подписался».",
            reply_markup=gate_kb()
        )

@dp.callback_query_handler(lambda c: c.data == "check_sub")
async def check_sub(call: types.CallbackQuery):
    uid = call.from_user.id
    if await is_subscribed(uid):
        set_step(uid, "date")
        try:
            await call.message.edit_reply_markup()
        except Exception:
            pass
        await call.message.answer("Подписка найдена ✅\nВведите дату рождения <b>ДД.ММ.ГГГГ</b>.")
    else:
        await call.answer("Похоже, подписки ещё нет 🙈", show_alert=True)

@dp.message_handler()
async def collect(message: types.Message):
    uid = message.from_user.id
    step = get_step(uid)
    if not step:
        return

    if step == "date":
        date_text = message.text.strip()
        if DATE_RE.match(date_text):
            box(uid)['birth_date'] = date_text
            set_step(uid, "name")
            await message.answer("Теперь введите ваше имя ✍️ (2–40 букв).")
        else:
            await message.answer("Формат даты: <b>ДД.ММ.ГГГГ</b> (например, 05.11.1992).")

    elif step == "name":
        name = message.text.strip()
        if NAME_RE.match(name):
            box(uid)['user_name'] = name
            set_step(uid, "confirm")
            d = box(uid)
            await message.answer(
                f"Проверьте данные:\n"
                f"Дата рождения: <b>{d['birth_date']}</b>\n"
                f"Имя: <b>{d['user_name']}</b>\n\n"
                f"Если всё верно — нажмите кнопку ниже.",
                reply_markup=confirm_kb()
            )
        else:
            await message.answer("Имя должно содержать 2–40 букв (можно пробел и дефис).")

@dp.callback_query_handler(lambda c: c.data == "confirm")
async def confirm(call: types.CallbackQuery):
    uid = call.from_user.id
    if get_step(uid) != "confirm":
        await call.answer("Нет данных для подтверждения.", show_alert=True)
        return

    try:
        await call.message.edit_reply_markup()
    except Exception:
        pass

    d = box(uid)
    logging.info(f"CONFIRMED: uid={uid} date={d.get('birth_date')} name={d.get('user_name')}")
    await call.message.answer(
        "Спасибо 🙌 Мы приняли вашу дату рождения и имя.\n"
        "Как всё это обрабатывается вручную, нужно немного подождать 🕊️"
    )
    user_data.pop(uid, None)

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
