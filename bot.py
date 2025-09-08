import re
import logging
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# 🔑 Данные твоего бота
API_TOKEN  = "8260960372:AAFMrTN7DUrYhD_E-D1hF1l5ZTPuu679zP8"
CHANNEL_ID = -1002552649165  # ID канала

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN, parse_mode="HTML")
dp = Dispatcher(bot)

DATE_RE = re.compile(r"^(0[1-9]|[12][0-9]|3[01])\.(0[1-9]|1[0-2])\.(19|20)\d{2}$")
NAME_RE = re.compile(r"^[A-Za-zА-Яа-яЁё\s\-]{2,40}$")

def gate_kb():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("Открыть канал", url="https://t.me/slavicruna"))
    kb.add(InlineKeyboardButton("Подписался", callback_data="check_sub"))
    return kb

def confirm_kb():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("Данные введены", callback_data="confirm"))
    return kb

@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    await message.answer(
        "Привет! 🌿 Чтобы получить руну, подпишитесь на наш канал:\n"
        "https://t.me/slavicruna\n\n"
        "После подписки нажмите кнопку 👇 «Подписался».",
        reply_markup=gate_kb()
    )

@dp.callback_query_handler(lambda c: c.data == "check_sub")
async def check_sub(call: types.CallbackQuery):
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=call.from_user.id)
        is_sub = member.status in ("creator", "administrator", "member")
    except Exception:
        is_sub = False
    if is_sub:
        await call.message.edit_reply_markup()
        await call.message.answer("Отлично 🌿\nТеперь введите вашу дату рождения в формате ДД.ММ.ГГГГ 👇")
        dp.data = {"step": "date"}
    else:
        await call.answer("Похоже, подписки ещё нет 🙏", show_alert=True)

@dp.message_handler()
async def collect(message: types.Message):
    if not hasattr(dp, "data"):
        return
    step = dp.data.get("step")
    if step == "date":
        if DATE_RE.match(message.text.strip()):
            dp.data["birth_date"] = message.text.strip()
            dp.data["step"] = "name"
            await message.answer("Теперь введите ваше имя 👇")
        else:
            await message.answer("Формат даты: ДД.ММ.ГГГГ (например, 05.11.1992)")
    elif step == "name":
        if NAME_RE.match(message.text.strip()):
            dp.data["user_name"] = message.text.strip()
            dp.data["step"] = "ready"
            await message.answer(
                f"Проверьте:\n\nДата рождения: <b>{dp.data['birth_date']}</b>\nИмя: <b>{dp.data['user_name']}</b>\n\n"
                "Если всё верно — нажмите кнопку.",
                reply_markup=confirm_kb()
            )
        else:
            await message.answer("Имя должно быть буквами (2–40 символов).")

@dp.callback_query_handler(lambda c: c.data == "confirm")
async def confirm(call: types.CallbackQuery):
    if not hasattr(dp, "data") or dp.data.get("step") != "ready":
        await call.answer("Нет данных.", show_alert=True)
        return
    await call.message.edit_reply_markup()
    await call.message.answer(
        "Спасибо 🌿 Мы приняли вашу дату рождения и имя.\n"
        "Так как всё обрабатывается вручную, нужно немного подождать 🙌"
    )
    dp.data = {}

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
