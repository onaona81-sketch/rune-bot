# bot.py — подписка → дата → имя → уведомление админа → ответ админа пользователю
import os
import re
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor

# === ТВОИ ДАННЫЕ ===
API_TOKEN = os.getenv("BOT_TOKEN") or "8260960372:AAFMrTN7DUrYhD_E-D1hF1l5ZTPuu679zP8"
CHANNEL   = os.getenv("CHANNEL")   or "@slavicruna"   # можно и -100... (ID канала)
ADMIN_ID  = int(os.getenv("ADMIN_ID") or 8218520444)          # твой цифровой Telegram ID
# ====================

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN, parse_mode=types.ParseMode.HTML)
dp  = Dispatcher(bot)

# простая "память" состояний в RAM
user_state = {}     # user_id -> "waiting_date" | {"date": "...", "step": "waiting_name", "name": "..."}
admin_state = {}    # ADMIN_ID -> {"reply_to": user_id}

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

def admin_reply_kb(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup().add(
        InlineKeyboardButton("Ответить", callback_data=f"admin_reply:{user_id}"),
        InlineKeyboardButton("Открыть чат", url=f"tg://user?id={user_id}")
    )

@dp.message_handler(commands=["start"])
async def start_cmd(message: types.Message):
    await message.answer(
        "Привет! 🌿 Чтобы получить руну, подпишитесь на наш канал:\n"
        f"{'@' + CHANNEL.lstrip('@')}\n\n"
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
                await call.message.edit_reply_markup()  # убираем старые кнопки
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
        "Проверьте данные:\n"
        f"📅 Дата: <b>{data['date']}</b>\n"
        f"👤 Имя: <b>{data['name']}</b>\n\n"
        "Если всё верно — нажмите кнопку ниже 👇",
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

    # Сообщение пользователю
    await bot.send_message(
        uid,
        "Спасибо 🌿 Мы приняли вашу дату рождения и имя.\n"
        "Так как всё обрабатывается вручную, нужно немного подождать 🙌"
    )

    # Уведомление админу
    if ADMIN_ID:
        u = call.from_user
        text = (
            "🆕 <b>Новая заявка</b>\n"
            f"👤 Пользователь: <b>{u.full_name}</b> (@{u.username})\n"
            f"🆔 ID: <code>{uid}</code>\n"
            f"📅 Дата: <b>{data['date']}</b>\n"
            f"📛 Имя: <b>{data['name']}</b>"
        )
        try:
            await bot.send_message(ADMIN_ID, text, reply_markup=admin_reply_kb(uid))
        except Exception as e:
            logging.warning(f"Cannot send to admin: {e}")

    user_state.pop(uid, None)

# ===== Ответ админа пользователю =====
@dp.callback_query_handler(lambda c: c.data.startswith("admin_reply:"))
async def admin_reply_start(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("Нет прав.", show_alert=True)
        return
    target_id = int(call.data.split(":")[1])
    admin_state[ADMIN_ID] = {"reply_to": target_id}
    try:
        await call.message.edit_reply_markup()
    except Exception:
        pass
    await bot.send_message(ADMIN_ID, f"Напишите ответ для пользователя ID <code>{target_id}</code> (одно сообщение).")

@dp.message_handler(lambda m: m.from_user.id == ADMIN_ID and ADMIN_ID in admin_state)
async def admin_send_reply(message: types.Message):
    target = admin_state.get(ADMIN_ID, {}).get("reply_to")
    if not target:
        return
    text = message.text or ""
    try:
        await bot.send_message(target, f"Сообщение от администратора:\n\n{text}")
        await message.answer("✅ Отправлено.")
    except Exception as e:
        await message.answer(f"❌ Не удалось отправить: {e}")
    finally:
        admin_state.pop(ADMIN_ID, None)

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
