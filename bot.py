# bot.py — подписка → дата → имя → уведомление админа → удобные ответы админа
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

# === НАСТРОЙКИ ===
API_TOKEN = os.getenv("BOT_TOKEN")               # BOT_TOKEN задать в Render → Environment
CHANNEL   = os.getenv("CHANNEL") or "@slavicruna"
ADMIN_ID  = int(os.getenv("ADMIN_ID") or 8218520444)
# ==================

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

if not API_TOKEN:
    raise RuntimeError("❌ Переменная окружения BOT_TOKEN не задана!")

bot = Bot(token=API_TOKEN, parse_mode=types.ParseMode.HTML)
dp  = Dispatcher(bot, storage=MemoryStorage())

# ---- Будильник: пингуем внешний URL (если задан) раз в 10 минут ----
def keep_awake():
    url = os.environ.get("RENDER_EXTERNAL_URL")
    if not url:
        log.info("RENDER_EXTERNAL_URL не задан — будильник пропускаем.")
        return
    while True:
        try:
            requests.get(url, timeout=10)
            log.info("Pinged self to stay awake.")
        except Exception as e:
            log.warning(f"Ping failed: {e}")
        time.sleep(600)
# --------------------------------------------------------------------

# FSM состояния
from aiogram.dispatcher.filters.state import State, StatesGroup

class Form(StatesGroup):
    waiting_date = State()
    waiting_name = State()

# ==== Кнопки ====
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

# ==== Хендлеры пользователя ====
@dp.message_handler(commands=["start"])
async def start_cmd(message: types.Message):
    await message.answer(
        "Привет! 🌿 Чтобы получить руну, подпишитесь на наш канал:\n"
        f"{'@' + CHANNEL.lstrip('@')}\n\n"
        "После подписки нажмите кнопку 👇 «Подписался».",
        reply_markup=gate_kb(),
    )

@dp.callback_query_handler(lambda c: c.data == "check_sub")
async def check_sub(call: types.CallbackQuery, state: FSMContext):
    uid = call.from_user.id
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL, user_id=uid)
        if member.status in ("member", "administrator", "creator"):
            await state.set_state(Form.waiting_date)
            try:
                await call.message.edit_reply_markup()
            except Exception:
                pass
            await bot.send_message(uid, "Введите вашу дату рождения (например: 05.11.1992) ⤵️")
        else:
            await call.answer("Похоже, подписки ещё нет 🙈", show_alert=True)
    except Exception as e:
        log.warning(f"get_chat_member error: {e}")
        await call.answer("Не удалось проверить подписку, попробуйте ещё раз.", show_alert=True)

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
        reply_markup=confirm_kb(),
    )

# ==== Фикс подтверждения ====
@dp.callback_query_handler(lambda c: c.data == "confirm_data", state="*")
async def confirm_data(call: types.CallbackQuery, state: FSMContext):
    uid = call.from_user.id
    data = await state.get_data()

    date = data.get("date")
    name = data.get("name")

    if not date or not name:
        await state.finish()
        await call.message.answer("Не нашла данные заявки 🙈 Нажмите /start и введите заново.")
        return

    try:
        await call.message.edit_reply_markup()
    except:
        pass

    await bot.send_message(
        uid,
        "Ваша заявка у меня! Спасибо-спасибо! 🤍😊\n"
        "Я всё проверяю лично и вручную (я одна, но очень стараюсь!), так что небольшая пауза неизбежна.\n"
        "Вы все очень важны! Я обязательно с вами свяжусь! Ожидайте! 💫",
    )

    if ADMIN_ID:
        u = call.from_user
        text = (
            "🆕 <b>Новая заявка</b>\n"
            f"👤 Пользователь: <b>{u.full_name}</b> (@{u.username})\n"
            f"🆔 ID: <code>{uid}</code>\n"
            f"📅 Дата: <b>{date}</b>\n"
            f"📛 Имя: <b>{name}</b>"
        )
        try:
            await bot.send_message(ADMIN_ID, text, reply_markup=admin_reply_kb(uid))
        except Exception as e:
            log.warning(f"Не смогла отправить админу: {e}")

    await state.finish()

# ====== Ответы админа (как у вас было) ======
admin_state = {}

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
        f"🔁 Режим ответа включён для ID <code>{target_id}</code>.\n"
        f"Отправляй сообщения (текст/фото/видео/док/голос/стикер) — я буду копировать их пользователю.\n"
        f"Завершить — /done"
    )

@dp.message_handler(
    lambda m: (
        m.from_user.id == ADMIN_ID
        and ADMIN_ID in admin_state
        and not (m.text and (m.text.startswith("/done")
                             or m.text.startswith("/cancel")
                             or m.text.startswith("/reply")
                             or m.text.startswith("/to")))),
    content_types=types.ContentTypes.ANY
)
async def admin_send_reply(message: types.Message):
    target = admin_state.get(ADMIN_ID, {}).get("reply_to")
    if not target:
        return
    try:
        await bot.copy_message(
            chat_id=target,
            from_chat_id=message.chat.id,
            message_id=message.message_id
        )
        await message.answer("✅ Отправлено пользователю.")
    except Exception as e:
        await message.answer(f"❌ Не удалось отправить: {e}")

@dp.message_handler(lambda m: m.from_user.id == ADMIN_ID and m.text and m.text.startswith("/done"))
async def admin_finish_reply(message: types.Message):
    admin_state.pop(ADMIN_ID, None)
    await message.answer("🚫 Режим ответа выключен.")

if __name__ == "__main__":
    threading.Thread(target=keep_awake, daemon=True).start()
    executor.start_polling(dp, skip_updates=True)
