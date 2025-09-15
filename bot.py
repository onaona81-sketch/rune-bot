# bot.py — подписка → дата → имя → уведомление админа → удобные ответы админа (много сообщений + медиа)
import os
import re
import logging
import threading
import time
import requests
from flask import Flask
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor

# === ТВОИ ДАННЫЕ ===
API_TOKEN = "8260960372:AAHmU3TNORYb4UaxrGQxLjCFsLFursPIRco"
CHANNEL   = os.getenv("CHANNEL") or "@slavicruna"          # можно и -100... (ID канала)
ADMIN_ID  = int(os.getenv("ADMIN_ID") or 8218520444)       # твой цифровой Telegram ID
# ====================

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN, parse_mode=types.ParseMode.HTML)
dp  = Dispatcher(bot)

# Память состояний
user_state: dict[int, dict | str] = {}   # user_id -> состояния
admin_state: dict[int, dict] = {}        # ADMIN_ID -> {"reply_to": user_id}

# ==== Мини-веб для Render (проверка живости) ====
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is alive!"

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
# ===============================================

# ==== Будильник (самопинг каждые 10 мин) ====
def keep_awake():
    url = os.environ.get("RENDER_EXTERNAL_URL") or "http://localhost:5000"
    while True:
        try:
            requests.get(url, timeout=10)
            logging.info("Pinged self to stay awake.")
        except Exception as e:
            logging.warning(f"Ping failed: {e}")
        time.sleep(600)  # 10 минут
# ============================================

def gate_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("Открыть канал", url=f"https://t.me/{CHANNEL.lstrip('@')}"),
        InlineKeyboardButton("Подписался", callback_data="check_sub"),
    )
    return kb

def confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup().add(
        InlineKeyboardButton("Данные верны", callback_data="confirm_data")
    )

def admin_reply_kb(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup().add(
        InlineKeyboardButton("Ответить", callback_data=f"admin_reply:{user_id}"),
        InlineKeyboardButton("Открыть чат", url=f"tg://user?id={user_id}"),
    )

@dp.message_handler(commands=["start"])
async def start_cmd(message: types.Message):
    await message.answer(
        "Привет! 🌿 Чтобы получить руну, подпишитесь на наш канал:\n"
        f"{'@' + CHANNEL.lstrip('@')}\n\n"
        "После подписки нажмите кнопку 👇 «Подписался».",
        reply_markup=gate_kb(),
    )

@dp.callback_query_handler(lambda c: c.data == "check_sub")
async def check_sub(call: types.CallbackQuery):
    uid = call.from_user.id
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL, user_id=uid)
        if member.status in ("member", "administrator", "creator"):
            user_state[uid] = "waiting_date"
            try:
                await call.message.edit_reply_markup()
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

@dp.message_handler(lambda m: isinstance(user_state.get(m.from_user.id), dict)
                    and user_state[m.from_user.id].get("step") == "waiting_name")
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
        reply_markup=confirm_kb(),
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

    await bot.send_message(
        uid,
        "Спасибо 🌿 Мы приняли вашу дату рождения и имя.\n"
        "Так как всё обрабатывается вручную, нужно немного подождать 🙌",
    )

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

# ===== УДОБНЫЕ ОТВЕТЫ АДМИНА: сессия (много сообщений) + быстрые команды =====

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
    await bot.send_message(
        ADMIN_ID,
        "🔁 Режим ответа включён для ID <code>{}</code>.\n"
        "Отправляй СООБЩЕНИЯ (текст/фото/видео/док/голос/стикер) — я буду пересылать их пользователю.\n"
        "Когда закончишь — напиши /done (или /cancel), чтобы выйти из режима.".format(target_id)
    )

# ✅ ФИКС: разрешаем ЛЮБОЙ тип контента в режиме ответа (раньше ловился только текст)
@dp.message_handler(
    content_types=types.ContentTypes.ANY,
    func=lambda m: (
        m.from_user.id == ADMIN_ID
        and ADMIN_ID in admin_state
        and not (
            m.text and (
                m.text.startswith("/done")
                or m.text.startswith("/cancel")
                or m.text.startswith("/reply")
                or m.text.startswith("/to")
            )
        )
    )
)
async def admin_send_reply(message: types.Message):
    target = admin_state.get(ADMIN_ID, {}).get("reply_to")
    if not target:
        return
    try:
        # copy_message сохраняет и сам медиа-файл, и подпись (если была)
        await bot.copy_message(
            chat_id=target,
            from_chat_id=message.chat.id,
            message_id=message.message_id
        )
        await message.answer("✅ Отправлено пользователю.")
    except Exception as e:
        await message.answer(f"❌ Не удалось отправить: {e}")

@dp.message_handler(lambda m: m.from_user.id == ADMIN_ID and m.text and (m.text.startswith("/done") or m.text.startswith("/cancel")))
async def admin_finish_reply(message: types.Message):
    admin_state.pop(ADMIN_ID, None)
    await message.answer("🚫 Режим ответа выключен.")

@dp.message_handler(lambda m: m.from_user.id == ADMIN_ID and m.text and m.text.startswith("/reply"))
async def admin_direct_reply(message: types.Message):
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("Формат: /reply <user_id> <текст>")
        return
    try:
        target_id = int(parts[1])
    except ValueError:
        await message.answer("user_id должен быть числом.")
        return
    text = parts[2]
    try:
        await bot.send_message(target_id, f"Сообщение от администратора:\n\n{text}")
        await message.answer("✅ Отправлено пользователю.")
    except Exception as e:
        await message.answer(f"❌ Ошибка при отправке: {e}")

@dp.message_handler(lambda m: m.from_user.id == ADMIN_ID and m.text and m.text.startswith("/to"))
async def admin_set_target(message: types.Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Формат: /to <user_id>")
        return
    try:
        target_id = int(parts[1])
    except ValueError:
        await message.answer("user_id должен быть числом.")
        return
    admin_state[ADMIN_ID] = {"reply_to": target_id}
    await message.answer(
        "🔁 Режим ответа включён для ID <code>{}</code>.\n"
        "Отправляй сообщения (любой тип) — я буду пересылать их пользователю.\n"
        "Завершить — /done".format(target_id)
    )

if __name__ == "__main__":
    # поднимаем мини-веб и будильник, затем запускаем бота
    threading.Thread(target=run_flask, daemon=True).start()
    threading.Thread(target=keep_awake, daemon=True).start()
    executor.start_polling(dp, skip_updates=True)
ue)
