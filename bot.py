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

# Настроечные константы
API_TOKEN = os.getenv("BOT_TOKEN")              # Токен бота
CHANNEL   = os.getenv("CHANNEL") or "@yourchannel"
ADMIN_ID  = int(os.getenv("ADMIN_ID") or 1234567890)
OFFERTA_LINK = "https://drive.google.com/file/d/1td5YQZLRFUPdrKd9b5MTsDyjerOMXEXe/preview"

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

if not API_TOKEN:
    raise RuntimeError("❌ Переменная окружения BOT_TOKEN не задана!")

bot = Bot(token=API_TOKEN, parse_mode=types.ParseMode.HTML)
dp  = Dispatcher(bot, storage=MemoryStorage())

# Функционал "будильника" для поддержки активности
def keep_awake():
    url = os.environ.get("RENDER_EXTERNAL_URL")
    if not url:
        log.info("RENDER_EXTERNAL_URL не указан — будильник не запущен.")
        return
    while True:
        try:
            requests.get(url, timeout=10)
            log.info("Сервер успешно пропингован.")
        except Exception as e:
            log.warning(f"Проблема с ping-ом: {e}")
        time.sleep(600)

# Классы FSM (Finite State Machine)
from aiogram.dispatcher.filters.state import State, StatesGroup

class Form(StatesGroup):
    waiting_date = State()       # Ждем дату рождения
    waiting_name = State()       # Ждем имя пользователя

# Вспомогательные клавиатуры
def gate_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("Открыть канал", url=f"https://t.me/{CHANNEL.lstrip('@')}"),
        InlineKeyboardButton("Подписался", callback_data="check_sub"),
    )
    return kb

# Начало работы бота
@dp.message_handler(commands=["start"])
async def start_cmd(message: types.Message):
    await message.answer(
        "Привет! 🌿 Чтобы получить руну, подпишись на наш канал:\n"
        f"{CHANNEL}\n\n"
        "После подписки нажми кнопку 👇 «Подписался».",
        reply_markup=gate_kb(),
    )

# Проверяем факт подписки на канал
@dp.callback_query_handler(lambda c: c.data == "check_sub")
async def check_sub(call: types.CallbackQuery, state: FSMContext):
    uid = call.from_user.id
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL, user_id=uid)
        if member.status in ("member", "administrator", "creator"):
            await state.set_state(Form.waiting_date)  # Переходим к ожиданию даты
            await bot.send_message(uid, "Введи свою дату рождения (например: 05.11.1992) ⤵️")
        else:
            await call.answer("Похоже, подписки ещё нет 🙈", show_alert=True)
    except Exception as e:
        log.warning(f"Ошибка проверки подписки: {e}")
        await call.answer("Не получилось проверить подписку, попробуй ещё раз.", show_alert=True)

# Получаем дату рождения
@dp.message_handler(state=Form.waiting_date)
async def get_date(message: types.Message, state: FSMContext):
    date_text = (message.text or "").strip()
    if not re.fullmatch(r"(0?[1-9]|[12]\d|3[01])\.(0?[1-9]|1[0-2])\.(19\d{2}|20\d{2})", date_text):
        await message.answer("Формат даты: ДД.ММ.ГГГГ (пример: 05.11.1992)")
        return
    await state.update_data(date=date_text)
    await state.set_state(Form.waiting_name)
    await message.answer("Введи своё имя ⤵️")

# Получаем имя пользователя
@dp.message_handler(state=Form.waiting_name)
async def get_name(message: types.Message, state: FSMContext):
    name = (message.text or "").strip()
    if not (2 <= len(name) <= 40):
        await message.answer("Имя должно быть длиной 2–40 символов. Попробуй ещё раз :)")
        return
    await state.update_data(name=name)
    data = await state.get_data()
    await state.finish()
    await message.answer(
        "Спасибо! Ваша заявка принята!\n"
        "Мы скоро рассмотрим вашу заявку и свяжемся с вами!",
    )

# Основная точка старта программы
if __name__ == "__main__":
    threading.Thread(target=keep_awake, daemon=True).start()
    executor.start_polling(dp, skip_updates=True)
