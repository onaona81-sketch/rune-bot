import logging
import os
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor

# === ДАННЫЕ БОТА И КАНАЛА ===
API_TOKEN = os.getenv("BOT_TOKEN")  # Токен берём из Render → Environment → BOT_TOKEN
CHANNEL_ID = -1002556294616         # ID твоего канала (оставляем как есть)

# === НАСТРОЙКА ЛОГОВ ===
logging.basicConfig(level=logging.INFO)

# === СОЗДАЕМ ОБЪЕКТЫ БОТА И ДИСПЕТЧЕРА ===
bot = Bot(token=API_TOKEN, parse_mode=types.ParseMode.HTML)
dp = Dispatcher(bot)

# === СОСТОЯНИЕ ПОЛЬЗОВАТЕЛЕЙ ===
user_state = {}

# === СТАРТ ===
@dp.message_handler(commands=["start"])
async def send_welcome(message: types.Message):
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("Открыть канал", url="https://t.me/slavicruna"),
        InlineKeyboardButton("Подписался", callback_data="check_sub")
    )
    await message.answer(
        "Привет! 🌿 Чтобы получить руну, подпишитесь на наш канал:\n"
        "https://t.me/slavicruna\n\n"
        "После подписки нажмите кнопку 👇 «Подписался».",
        reply_markup=keyboard
    )

# === ПРОВЕРКА ПОДПИСКИ ===
@dp.callback_query_handler(lambda c: c.data == "check_sub")
async def check_sub(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    try:
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        if member.status in ["member", "administrator", "creator"]:
            user_state[user_id] = "waiting_date"
            await bot.send_message(user_id, "Введите вашу дату рождения (например: 05.11.1992):")
        else:
            await bot.send_message(user_id, "Похоже, подписки ещё нет 🙏")
    except Exception as e:
        logging.error(f"Ошибка проверки подписки: {e}")
        await bot.send_message(user_id, "Ошибка при проверке подписки. Попробуйте позже.")

# === ПОЛУЧАЕМ ДАТУ ===
@dp.message_handler(lambda msg: user_state.get(msg.from_user.id) == "waiting_date")
async def process_date(message: types.Message):
    user_id = message.from_user.id
    user_state[user_id] = {"date": message.text, "step": "waiting_name"}
    await message.answer("Дата сохранена ✅\nТеперь введите ваше имя:")

# === ПОЛУЧАЕМ ИМЯ ===
@dp.message_handler(lambda msg: isinstance(user_state.get(msg.from_user.id), dict) and user_state[msg.from_user.id].get("step") == "waiting_name")
async def process_name(message: types.Message):
    user_id = message.from_user.id
    user_data = user_state.get(user_id, {})
    user_data["name"] = message.text
    user_state[user_id] = user_data

    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(InlineKeyboardButton("Данные верны", callback_data="confirm_data"))

    await message.answer(
        f"Спасибо! ✨\n\nПроверьте ваши данные:\n"
        f"📅 Дата: {user_data['date']}\n"
        f"👤 Имя: {user_data['name']}\n\n"
        "Если всё правильно — нажмите кнопку ниже 👇",
        reply_markup=keyboard
    )

# === ПОДТВЕРЖДЕНИЕ ===
@dp.callback_query_handler(lambda c: c.data == "confirm_data")
async def confirm_data(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    user_data = user_state.get(user_id, {})
    await bot.send_message(
        user_id,
        f"🎉 Отлично, {user_data.get('name', 'друг')}!\n"
        f"Твоя дата рождения: {user_data.get('date')}\n\n"
        "🔮 Руна уже готовится для тебя..."
    )
    user_state.pop(user_id, None)

# === СТАРТ ПОЛЛИНГА ===
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
