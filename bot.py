# bot.py — подписка → дата → имя → уведомление админа → ответы админа (текст/медиа)
import os
import re
import time
import logging
import threading
import requests

from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.dispatcher import FSMContext
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# === НАСТРОЙКИ (через Render → Environment) ===
API_TOKEN = os.getenv("BOT_TOKEN")                    # BOT_TOKEN
CHANNEL   = os.getenv("CHANNEL") or "@slavicruna"     # CHANNEL
ADMIN_ID  = int(os.getenv("ADMIN_ID") or 8218520444)  # ADMIN_ID
# ===============================================

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

if not API_TOKEN:
    raise RuntimeError("❌ Переменная окружения BOT_TOKEN не задана!")

bot = Bot(token=API_TOKEN, parse_mode=types.ParseMode.HTML)
dp  = Dispatcher(bot, storage=MemoryStorage())  # FSM в памяти процесса

# ===== Будильник: мягкий самопинг внешнего URL раз в 10 минут (для Web Service) =====
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
# =====================================================================================

# ===== FSM =====
class Form(StatesGroup):
    waiting_date = State()
    waiting_name = State()

# Анти-дребезг по «Подписался»
_last_click = {}  # user_id -> timestamp

# ===== Кнопки =====
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
    return InlineKeyboardMarkup(row_width=2).add(
        InlineKeyboardButton("Ответить", callback_data=f"admin_reply:{user_id}"),
        InlineKeyboardButton("Открыть чат", url=f"tg://user?id={user_id}"),
    )

# ===== Команды =====
@dp.message_handler(commands=["start"])
async def start_cmd(message: types.Message, state: FSMContext):
    # Полный сброс шага/данных, чтобы «/start» не попадало в имя
    await state.finish()
    await message.answer(
        "Привет! 🌿 Чтобы получить руну, подпишитесь на наш канал:\n"
        f"{'@' + CHANNEL.lstrip('@')}\n\n"
        "После подписки нажмите кнопку 👇 «Подписался».",
        reply_markup=gate_kb(),
    )

@dp.message_handler(commands=["reset"])
async def reset_cmd(message: types.Message, state: FSMContext):
    await state.finish()
    await message.answer("🔄 Сбросила состояние. Нажмите «Подписался» ещё раз.", reply_markup=gate_kb())

# ===== Подписка и шаги =====
@dp.callback_query_handler(lambda c: c.data == "check_sub")
async def check_sub(call: types.CallbackQuery, state: FSMContext):
    uid = call.from_user.id
    # анти-дребезг (2 сек)
    now = time.time()
    if now - _last_click.get(uid, 0) < 2:
        try:
            await call.answer("Минутку…", show_alert=False)
        except:  # noqa
            pass
        return
    _last_click[uid] = now

    try:
        member = await bot.get_chat_member(chat_id=CHANNEL, user_id=uid)
        if member.status in ("member", "administrator", "creator"):
            await Form.waiting_date.set()
            try:
                await call.message.edit_reply_markup()
            except:  # noqa
                pass
            await bot.send_message(uid, "Введите вашу дату рождения (например: 05.11.1992) ⤵️")
        else:
            await call.answer("Похоже, подписки ещё нет 🙈", show_alert=True)
    except Exception as e:
        log.warning(f"get_chat_member error: {e}")
        await call.answer("Не удалось проверить подписку, попробуйте ещё раз.", show_alert=True)

@dp.message_handler(state=Form.waiting_date, content_types=types.ContentTypes.TEXT)
async def get_date(message: types.Message, state: FSMContext):
    date_text = (message.text or "").strip()
    if not re.fullmatch(r"(0?[1-9]|[12]\d|3[01])\.(0?[1-9]|1[0-2])\.(19\d{2}|20\d{2})", date_text):
        await message.answer("Формат даты: <b>ДД.ММ.ГГГГ</b> (например: 05.11.1992).")
        return
    await state.update_data(date=date_text)
    await Form.waiting_name.set()
    await message.answer("Отлично 🌿 Теперь введите ваше имя ⤵️")

@dp.message_handler(state=Form.waiting_name, content_types=types.ContentTypes.TEXT)
async def get_name(message: types.Message, state: FSMContext):
    name = (message.text or "").strip()

    # 1) Не позволяем использовать команды как имя
    if name.startswith("/"):
        await message.answer("Пожалуйста, напишите имя обычным текстом, без команд 🙂")
        return

    # 2) Простая проверка имени (буквы/пробел/дефис, 2–40 символов)
    if not (2 <= len(name) <= 40):
        await message.answer("Имя должно быть длиной 2–40 символов. Попробуйте ещё раз 🙂")
        return
    if not re.fullmatch(r"[A-Za-zА-Яа-яЁёІіЇїЄєҐґ\- ]{2,40}", name):
        await message.answer("Имя должно содержать только буквы, пробелы и дефис. Попробуйте ещё раз 🙂")
        return

    await state.update_data(name=name)
    data = await state.get_data()
    await message.answer(
        "Проверьте данные:\n"
        f"📅 Дата: <b>{data['date']}</b>\n"
        f"👤 Имя: <b>{data['name']}</b>\n\n"
        "Если всё верно — нажмите кнопку ниже 👇",
        reply_markup=confirm_kb(),
    )

# подтверждение БЕЗ привязки к текущему state: берём то, что накопили в FSM
@dp.callback_query_handler(lambda c: c.data == "confirm_data")
async def confirm_data(call: types.CallbackQuery, state: FSMContext):
    uid = call.from_user.id
    data = await state.get_data()

    date = data.get("date")
    name = data.get("name")

    if not date or not name:
        # Данные потерялись — просим начать заново
        try:
            await call.message.edit_reply_markup()
        except:  # noqa
            pass
        await state.finish()
        await bot.send_message(uid, "Не нашла данные заявки. Нажмите /start и пройдите шаги заново 🙏")
        return

    try:
        await call.message.edit_reply_markup()
    except:  # noqa
        pass

    # Сообщение пользователю
    await bot.send_message(
        uid,
        "Спасибо 🌿 Мы приняли вашу дату рождения и имя.\n"
        "Так как всё обрабатывается вручную, нужно немного подождать 🙌",
    )

    # Уведомление админу
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
            log.warning(f"Cannot send to admin: {e}")

    # Чистим состояние
    await state.finish()

# ===== РЕЖИМ ОТВЕТА АДМИНА (копируем любой контент пользователю) =====
admin_mode = {}  # admin_id -> {"reply_to": user_id}

@dp.callback_query_handler(lambda c: c.data.startswith("admin_reply:"))
async def admin_reply_start(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("Нет прав.", show_alert=True)
        return
    target_id = int(call.data.split(":")[1])
    admin_mode[ADMIN_ID] = {"reply_to": target_id}
    try:
        await call.message.edit_reply_markup()
    except:  # noqa
        pass
    await bot.send_message(
        ADMIN_ID,
        f"🔁 Режим ответа включён для ID <code>{target_id}</code>.\n"
        f"Отправляй сообщения (текст/фото/видео/док/голос/стикер) — я буду копировать их пользователю.\n"
        f"Завершить — /done (или /cancel)."
    )

@dp.message_handler(
    lambda m: (
        m.from_user.id == ADMIN_ID
        and ADMIN_ID in admin_mode
        and not (m.text and (m.text.startswith("/done")
                             or m.text.startswith("/cancel")
                             or m.text.startswith("/reply")
                             or m.text.startswith("/to")))
    ),
    content_types=types.ContentTypes.ANY
)
async def admin_send_reply(message: types.Message):
    target = admin_mode.get(ADMIN_ID, {}).get("reply_to")
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

@dp.message_handler(lambda m: m.from_user.id == ADMIN_ID and m.text and (m.text.startswith("/done") or m.text.startswith("/cancel")))
async def admin_finish_reply(message: types.Message):
    admin_mode.pop(ADMIN_ID, None)
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
    admin_mode[ADMIN_ID] = {"reply_to": target_id}
    await message.answer(
        f"🔁 Режим ответа включён для ID <code>{target_id}</code>.\n"
        f"Отправляй сообщения (любой тип) — я буду копировать их пользователю.\n"
        f"Завершить — /done"
    )

if __name__ == "__main__":
    # Будильник не мешает, можно оставить
    threading.Thread(target=keep_awake, daemon=True).start()
    executor.start_polling(dp, skip_updates=True)

