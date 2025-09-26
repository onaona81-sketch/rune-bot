import os
import re
import logging
import threading
import time
import requests
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Настройка переменных среды
API_TOKEN = os.getenv("BOT_TOKEN")  # Задать BOT_TOKEN в среде выполнения
CHANNEL   = os.getenv("CHANNEL") or "@your_channel"
ADMIN_ID  = int(os.getenv("ADMIN_ID") or 1234567890)
OFFERTA_LINK = "https://drive.google.com/file/d/1td5YQZLRFUPdrKd9b5MTsDyjerOMXEXe/preview"

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

if not API_TOKEN:
    raise RuntimeError("❌ Переменная окружения BOT_TOKEN не задана!")

bot = Bot(token=API_TOKEN, parse_mode=types.ParseMode.HTML)
dp  = Dispatcher(bot, storage=MemoryStorage())

# ---- Периодический ping для поддержания активности приложения -----
def keep_awake():
    url = os.environ.get("RENDER_EXTERNAL_URL")
    if not url:
        log.info("RENDER_EXTERNAL_URL не задан — периодический ping отключён.")
        return
    while True:
        try:
            requests.get(url, timeout=10)
            log.info("Ping successful.")
        except Exception as e:
            log.warning(f"Ping failed: {e}")
        time.sleep(600)

# FSM состояний
from aiogram.dispatcher.filters.state import State, StatesGroup

class Form(StatesGroup):
    waiting_date      = State()
    waiting_name      = State()
    waiting_acceptance = State()

# Клавиатуры с кнопками
def gate_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("Открыть канал", url=f"https://t.me/{CHANNEL.lstrip('@')}"),
        InlineKeyboardButton("Подписался", callback_data="check_sub"),
    )
    return kb

def offerta_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("Прочитать оферту", url=OFFERTA_LINK),
        InlineKeyboardButton("Продолжаю оформление", callback_data="accept_offer_and_continue"),
    )
    return kb

# Хендлеры пользователя
@dp.message_handler(commands=["start"])
async def start_cmd(message: types.Message):
    await message.answer(
        "Привет! 🌿 Чтобы получить руну, подпишитесь на наш канал:\n"
        f"{CHANNEL}\n\n"
        "После подписки нажмите кнопку 👇 «Подписался».",
        reply_markup=gate_kb(),
    )

@dp.callback_query_handler(lambda c: c.data == "check_sub")
async def check_sub(call: types.CallbackQuery, state: FSMContext):
    uid = call.from_user.id
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL, user_id=uid)
        if member.status in ("member", "administrator", "creator"):
            await state.set_state(Form.waiting_acceptance)
            try:
                await call.message.edit_reply_markup()
            except Exception:
                pass
            await bot.send_message(uid, "Перед оформлением заявки внимательно прочтите нашу оферту."
                                      "\n\nНажмите кнопку 'Продолжаю оформление', если согласны с условиями оферты.",
                                  reply_markup=offerta_kb())
        else:
            await call.answer("Похоже, подписки ещё нет 🙈", show_alert=True)
    except Exception as e:
        log.warning(f"Ошибка проверки подписки: {e}")
        await call.answer("Не удалось проверить подписку, попробуйте ещё раз.", show_alert=True)

@dp.callback_query_handler(lambda c: c.data == "accept_offer_and_continue")
async def continue_registration(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(Form.waiting_date)
    await bot.send_message(call.from_user.id, "Введите вашу дату рождения (например: 05.11.1992) ⤵️")

@dp.message_handler(state=Form.waiting_date)
async def get_date(message: types.Message, state: FSMContext):
    date_text = (message.text or "").strip()
    if not re.fullmatch(r"(0?[1-9]|[12]\d|3[01])\.(0?[1-9]|1[0-2])\.(19\d{2}|20\d{2})", date_text):
        await message.answer("Формат даты: <b>ДД.ММ.ГГГГ</b> (например: 05.11.1992).")
        return
    await state.update_data(date=date_text)
    await state.set_state(Form.waiting_name)
    await message.answer("Отлично 🌿 Теперь введите ваше имя ⤵️")

@dp.message_handler(state=Form.waiting_name)
async def get_name(message: types.Message, state: FSMContext):
    name = (message.text or "").strip()
    if not (2 <= len(name) <= 40):
        await message.answer("Имя должно быть длиной 2–40 символов. Попробуйте ещё раз 🙂")
        return
    await state.update_data(name=name)
    data = await state.get_data()
    await state.set_state("confirm")  # фиктивное состояние подтверждения
    await message.answer(
        "Проверьте данные:\n"
        f"📅 Дата: <b>{data['date']}</b>\n"
        f"👤 Имя: <b>{data['name']}</b>\n\n"
        "Если всё верно — нажмите кнопку ниже 👇",
        reply_markup=InlineKeyboardMarkup().add(
            InlineKeyboardButton("Данные верны", callback_data="confirm_data")
        ),
    )

# Остальные части вашего существующего кода остаются без изменений...

# Запуск
if __name__ == "__main__":
    threading.Thread(target=keep_awake, daemon=True).start()
    executor.start_polling(dp, skip_updates=True)
