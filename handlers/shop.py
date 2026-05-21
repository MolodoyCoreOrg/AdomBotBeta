import json
import random
import datetime
import re
import os
import sqlite3
import asyncio

from aiogram import Router, F, types, Bot
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database.db import connect, get_all_user_ids, get_user_full_data
from utils.config import DB_FILE, TOKEN
from utils.helpers import safe_edit_message
from handlers.keyboard import get_back_menu_button

router = Router()
bot = Bot(token=TOKEN)

KAZINO_FILE = os.path.join("data", "cards", "kazino_upgrades.json")


def broadcast_cancel_kb():
    """Клавиатура с кнопкой отмены для рассылки медиа."""
    kb = InlineKeyboardBuilder()
    kb.row(
        types.InlineKeyboardButton(text="↪️ Назад", callback_data="shop_menu"),
    )
    return kb.as_markup()


class MediaBroadcastState(StatesGroup):
    waiting_for_text = State()
    waiting_for_photo = State()
    waiting_for_gif = State()
    waiting_for_video = State()
    waiting_for_audio = State()


def shop_menu_kb():
    kb = InlineKeyboardBuilder()
    kb.row(
        types.InlineKeyboardButton(text="❇️ Улучшение казика. Цена: 100🔥", callback_data="shop_upgrade_kazino")
    )
    kb.row(
        types.InlineKeyboardButton(text="🎰 Покупка спинов. Цена: 10🔥 = 5🎰", callback_data="shop_buy_spins")
    )
    kb.row(
        types.InlineKeyboardButton(text="📢 Опубликовать сообщение. Цена: 50🔥", callback_data="shop_broadcast_text")
    )
    kb.row(
        types.InlineKeyboardButton(text="🖼️ Опубликовать фото. Цена: 75🔥", callback_data="shop_broadcast_photo")
    )
    kb.row(
        types.InlineKeyboardButton(text="🎬 Опубликовать GIF. Цена: 100🔥", callback_data="shop_broadcast_gif")
    )
    kb.row(
        types.InlineKeyboardButton(text="🎥 Опубликовать видео. Цена: 150🔥", callback_data="shop_broadcast_video")
    )
    kb.row(
        types.InlineKeyboardButton(text="🎙️ Опубликовать аудио. Цена: 50🔥", callback_data="shop_broadcast_audio")
    )
    kb.row(
        types.InlineKeyboardButton(text="↪️ Назад", callback_data="go_back_menu")
    )
    return kb.as_markup()

def kazino_upgrades_menu_kb():
    kb = InlineKeyboardBuilder()
    kb.row(
        types.InlineKeyboardButton(text="❇️ Улучшение казика. Цена: 100🔥", callback_data="shop_upgrade_kazino")
    )
    kb.row(
        types.InlineKeyboardButton(text="🎰 Покупка спинов. Цена: 10🔥 = 5🎰", callback_data="shop_buy_spins")
    )
    kb.row(
        types.InlineKeyboardButton(text="↪️ Назад", callback_data="main_profile")
    )
    return kb.as_markup()


def confirm_kb(confirm_cb: str, cancel_cb: str = "go_back_button"):
    kb = InlineKeyboardBuilder()
    kb.row(
        types.InlineKeyboardButton(text="Купить", callback_data=confirm_cb),
        types.InlineKeyboardButton(text="Отмена", callback_data=cancel_cb),
    )
    return kb.as_markup()


def load_kazino_upgrades():
    if not os.path.exists(KAZINO_FILE):
        return []
    try:
        with open(KAZINO_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def pick_upgrade(upgrades: list, user_upgrades: dict = None):
    """Выбирает случайное улучшение с учётом весов и ограничений max_count"""
    if user_upgrades is None:
        user_upgrades = {}
    
    # Фильтруем улучшения, которые уже достигли максимума
    available = []
    for u in upgrades:
        upgrade_id = u.get("id")
        max_count = u.get("max_count")
        current_count = user_upgrades.get(upgrade_id, 0) if upgrade_id else 0
        
        # Если есть ограничение и оно достигнуто - пропускаем
        if max_count is not None and current_count >= max_count:
            continue
        
        available.append(u)
    
    if not available:
        return None
    
    # Используем веса из JSON или дефолтные
    weights = []
    for u in available:
        w = u.get("weight", 1.0)
        weights.append(max(0.0, float(w)))
    
    try:
        return random.choices(available, weights=weights, k=1)[0]
    except Exception:
        return random.choice(available)


def ensure_purchase_log_table():
    with connect() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS purchase_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                item TEXT,
                detail TEXT,
                date TEXT
            )
            """
        )
        conn.commit()

# Create purchase_log table on module import to avoid creating it during request handling
try:
    ensure_purchase_log_table()
except Exception:
    # ignore failures at import time; handlers will still function and table can be created later
    pass


@router.callback_query(F.data == "shop_menu")
async def shop_menu(callback: CallbackQuery):
    user_id = int(callback.from_user.id)
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        if not row:
            await callback.answer("❌ Профиль не найден.", show_alert=True)
            return
        balance = row[0]
    await safe_edit_message(callback.message, f"🛒 Добро пожаловать в магазин! Здесь вы можете приобрести различные улучшения для казика и бонусные крутки.\n Выберите интересующую вас категорию:\n\n"
                                     f"Ваш баланс: {balance}🔥", reply_markup=shop_menu_kb())


# --- Улучшение казика: показываем подтверждение ---
@router.callback_query(F.data == "shop_upgrade_kazino")
async def shop_upgrade_kazino(callback: CallbackQuery):
    text = (
        "После покупки вы получите случайное улучшение для казино.\n"
        "Вы точно хотите купить?\n\nЦена: 100🔥"
    )
    await safe_edit_message(callback.message, text, reply_markup=confirm_kb("shop_confirm_buy_upgrade", "shop_menu"))

@router.callback_query(F.data == "shop_confirm_buy_upgrade")
async def shop_confirm_buy_upgrade(callback: CallbackQuery):
    user_id = int(callback.from_user.id)
    username = callback.from_user.username or ""

    # check balance
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        if not row:
            await callback.answer("❌ Профиль не найден.", show_alert=True)
            return
        balance = row[0]

        if balance < 100:
            await callback.answer("❌ Недостаточно средств (нужно 100).", show_alert=True)
            return

        # debit
        cur.execute("UPDATE users SET balance = balance - 100 WHERE user_id = ?", (user_id,))

        # ensure roulette_user exists
        cur.execute("SELECT user_id, kazino_upgrades, roulette_count FROM roulette_user WHERE user_id = ?", (user_id,))
        ru = cur.fetchone()
        now_iso = datetime.datetime.utcnow().isoformat()
        if not ru:
            # create with defaults
            cur.execute("INSERT INTO roulette_user (user_id, last_increment, kazino_upgrades) VALUES (?, ?, ?)", (user_id, now_iso, json.dumps([])))
            kazino_list = []
            roulette_count = 0
        else:
            kazino_list = json.loads(ru[1]) if ru[1] else []
            # Ensure kazino_list is a list, not a dict
            if isinstance(kazino_list, dict):
                kazino_list = []
            roulette_count = ru[2] or 0

        # pick upgrade с учётом уже купленных улучшений
        upgrades = load_kazino_upgrades()
        # Преобразуем список купленных улучшений в словарь {id: count}
        user_upgrades_dict = {}
        for item in kazino_list:
            item_id = item.get("id")
            if item_id:
                user_upgrades_dict[item_id] = user_upgrades_dict.get(item_id, 0) + 1
        
        chosen = pick_upgrade(upgrades, user_upgrades_dict)
        if not chosen:
            await callback.answer("❌ В магазине пока нет улучшений.", show_alert=True)
            conn.commit()
            return

        # append chosen (store name/effect/rarity/id and timestamp)
        entry = {
            "id": chosen.get("id"),
            "name": chosen.get("name"),
            "effect": chosen.get("effect"),
            "rarity": chosen.get("rarity"),
            "ts": now_iso
        }
        kazino_list.append(entry)

        cur.execute("UPDATE roulette_user SET kazino_upgrades = ? WHERE user_id = ?", (json.dumps(kazino_list, ensure_ascii=False), user_id))

        # log purchase
        cur.execute(
            "INSERT INTO purchase_log (user_id, username, item, detail, date) VALUES (?, ?, ?, ?, ?)",
            (user_id, username, "kazino_upgrade", entry["name"], now_iso)
        )

        conn.commit()

    await safe_edit_message(callback.message, f"🎉 Куплено: {entry['name']} ({entry['effect']}).\nСтоимость: 100🔥", reply_markup=shop_menu_kb())


@router.callback_query(F.data == "shop_buy_spins")
async def shop_buy_spins(callback: CallbackQuery):
    # Show confirmation message for buying spins
    text = (
        "Покупка пакета круток: +5 круток за 10🔥.\n"
        "Вы точно хотите купить?"
    )
    await safe_edit_message(callback.message, text, reply_markup=confirm_kb("shop_confirm_buy_spins", "shop_menu"))


@router.callback_query(F.data == "shop_confirm_buy_spins")
async def shop_confirm_buy_spins(callback: CallbackQuery):
    user_id = int(callback.from_user.id)
    username = callback.from_user.username or ""

    with connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        if not row:
            await callback.answer("❌ Профиль не найден.", show_alert=True)
            return
        balance = row[0]
        if balance < 10:
            await callback.answer("❌ Недостаточно средств (нужно 10).", show_alert=True)
            return

        # debit
        cur.execute("UPDATE users SET balance = balance - 10 WHERE user_id = ?", (user_id,))

        # ensure roulette_user exists and add spins (roulette_count)
        cur.execute("SELECT roulette_count FROM roulette_user WHERE user_id = ?", (user_id,))
        ru = cur.fetchone()
        if not ru:
            cur.execute("INSERT INTO roulette_user (user_id, last_increment, roulette_count) VALUES (?, ?, ?)", (user_id, datetime.datetime.utcnow().isoformat(), 5 + 5))
            new_count = 5 + 5
        else:
            cur.execute("UPDATE roulette_user SET roulette_count = roulette_count + 5 WHERE user_id = ?", (user_id,))
            cur.execute("SELECT roulette_count FROM roulette_user WHERE user_id = ?", (user_id,))
            new_count = cur.fetchone()[0]

        # log purchase
        cur.execute(
            "INSERT INTO purchase_log (user_id, username, item, detail, date) VALUES (?, ?, ?, ?, ?)",
            (user_id, username, "spins", "+5 spins", datetime.datetime.utcnow().isoformat())
        )

        conn.commit()

    await safe_edit_message(callback.message, f"✅ Куплено: +5 круток. Сейчас у тебя {new_count} круток.", reply_markup=shop_menu_kb())


@router.callback_query(F.data == "shop_my_upgrades")
async def shop_my_upgrades(callback: CallbackQuery):
    user_id = int(callback.from_user.id)

    with connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT kazino_upgrades FROM roulette_user WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        if not row or not row[0]:
            await callback.answer()
            await callback.message.edit_text("У тебя пока нет улучшений.", reply_markup=kazino_upgrades_menu_kb())
            return

        try:
            upgrades = json.loads(row[0])
        except Exception:
            upgrades = []

    # aggregate by name
    agg = {}
    for u in upgrades:
        name = u.get("name") or str(u.get("effect") or "unknown")
        effect = u.get("effect") or ""
        # attempt to extract numeric value from effect
        m = re.search(r"([+-]?\d+)", effect)
        num = int(m.group(1)) if m else None
        key = (name, effect)
        if key not in agg:
            agg[key] = {"count": 0, "num_total": 0, "effect": effect}
        agg[key]["count"] += 1
        if num is not None:
            agg[key]["num_total"] += num

    lines = ["🏬 Мои улучшения:\n"]
    for (name, effect), data in agg.items():
        if data["num_total"] != 0:
            # show aggregated numeric effect
            lines.append(f"{name}: {data['num_total']}")
        else:
            if data["count"] > 1:
                lines.append(f"{name}: {data['count']}× {effect}")
            else:
                lines.append(f"{name}: {effect}")

    try:
        await callback.message.edit_text("\n".join(lines), reply_markup=shop_menu_kb())
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            pass
        else:
            raise


# ====== ФУНКЦИИ ДЛЯ ОТПРАВКИ МЕДИА ВСЕМ ПОЛЬЗОВАТЕЛЯМ ======

async def broadcast_media_to_all_users(media_type: str, file_id: str = None, text: str = None, sender_id: int = None):
    """Отправляет медиа или текст всем пользователям бота (не более 30 сообщений в минуту)."""
    user_ids = get_all_user_ids()
    sent_count = 0
    
    sender_data = get_user_full_data(sender_id) if sender_id else None
    sender_name = ""
    if sender_data:
        username = sender_data.get("username")
        first_name = sender_data.get("first_name")
        if username:
            sender_name = f"@{username}"
        elif first_name:
            sender_name = first_name
        else:
            sender_name = f"пользователь {sender_id}"
    
    for uid in user_ids:
        try:
            if media_type == "text":
                message_text = f"📢 <b>Публичное сообщение от {sender_name}</b>:\n\n{text}"
                await bot.send_message(chat_id=uid, text=message_text, parse_mode="HTML")
            elif media_type == "photo":
                caption = f"🖼️ <b>Фото от {sender_name}</b>"
                await bot.send_photo(chat_id=uid, photo=file_id, caption=caption, parse_mode="HTML")
            elif media_type == "gif":
                caption = f"🎬 <b>GIF от {sender_name}</b>"
                await bot.send_animation(chat_id=uid, animation=file_id, caption=caption, parse_mode="HTML")
            elif media_type == "video":
                caption = f"🎥 <b>Видео от {sender_name}</b>"
                await bot.send_video(chat_id=uid, video=file_id, caption=caption, parse_mode="HTML")
            elif media_type == "audio":
                caption = f"🎙️ <b>Аудио от {sender_name}</b>"
                await bot.send_audio(chat_id=uid, audio=file_id, caption=caption, parse_mode="HTML")
            sent_count += 1
        except Exception as e:
            # Игнорируем ошибки отправки (бот заблокирован и т.д.)
            pass
        # Задержка 2 секунды между сообщениями = 30 сообщений в минуту
        await asyncio.sleep(2)
    
    return sent_count


# ====== ОБРАБОТЧИКИ ДЛЯ ОТПРАВКИ СООБЩЕНИЯ ======

@router.callback_query(F.data == "shop_broadcast_text")
async def shop_broadcast_text(callback: CallbackQuery, state: FSMContext):
    user_id = int(callback.from_user.id)
    
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        if not row:
            await callback.answer("❌ Профиль не найден.", show_alert=True)
            return
        balance = row[0]
    
    if balance < 50:
        await callback.answer("❌ Недостаточно средств (нужно 50🔥).", show_alert=True)
        return
    
    await state.set_state(MediaBroadcastState.waiting_for_text)
    await safe_edit_message(callback.message, "💬 Введите текст сообщения, которое вы хотите отправить всем пользователям бота:\n\nЦена: 50🔥\n\nИспользуйте /cancel для отмены или кнопку \"Назад\".", reply_markup=broadcast_cancel_kb())


@router.message(MediaBroadcastState.waiting_for_text)
async def process_broadcast_text(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    # Проверяем, что это текст, а не медиа
    if message.photo or message.animation or message.video or message.audio or message.voice:
        await message.answer("❌ Вы отправили медиафайл вместо текста. Для отправки фото/видео/GIF/аудио выберите соответствующий товар в магазине (от 75🔥).")
        return
    
    text = message.text
    
    if text == "/cancel":
        await state.clear()
        await message.answer("❌ Отменено.")
        return
    
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        if not row or row[0] < 50:
            await message.answer("❌ Недостаточно средств (нужно 50🔥).")
            await state.clear()
            return
        
        cur.execute("UPDATE users SET balance = balance - 50 WHERE user_id = ?", (user_id,))
        conn.commit()
    
    await state.clear()
    
    # Сразу отвечаем пользователю
    await message.answer("⏱ Ваше сообщение будет разослано в течении нескольких минут.")
    
    # Запускаем рассылку в фоновом режиме
    async def run_broadcast():
        sent_count = await broadcast_media_to_all_users("text", text=text, sender_id=user_id)
        await message.answer(f"✅ Сообщение отправлено всем пользователям! Получателей: {sent_count}\nСписано: 50🔥")
    
    asyncio.create_task(run_broadcast())


# ====== ОБРАБОТЧИКИ ДЛЯ ОТПРАВКИ ФОТО ======

@router.callback_query(F.data == "shop_broadcast_photo")
async def shop_broadcast_photo(callback: CallbackQuery, state: FSMContext):
    user_id = int(callback.from_user.id)
    
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        if not row:
            await callback.answer("❌ Профиль не найден.", show_alert=True)
            return
        balance = row[0]
    
    if balance < 75:
        await callback.answer("❌ Недостаточно средств (нужно 75🔥).", show_alert=True)
        return
    
    await state.set_state(MediaBroadcastState.waiting_for_photo)
    await safe_edit_message(callback.message, "🖼️ Отправьте фото, которое вы хотите показать всем пользователям бота:\n\nЦена: 75🔥\n\nИспользуйте /cancel для отмены или кнопку «Назад».", reply_markup=broadcast_cancel_kb())


@router.message(MediaBroadcastState.waiting_for_photo, F.photo)
async def process_broadcast_photo(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    # Проверяем, что это именно фото, а не видео или GIF
    if message.animation:
        await message.answer("❌ Вы отправили GIF. Для отправки GIF выберите соответствующий товар в магазине (100🔥).")
        return
    if message.video:
        await message.answer("❌ Вы отправили видео. Для отправки видео выберите соответствующий товар в магазине (150🔥).")
        return
    
    photo_file_id = message.photo[-1].file_id
    
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        if not row or row[0] < 75:
            await message.answer("❌ Недостаточно средств (нужно 75🔥).")
            await state.clear()
            return
        
        cur.execute("UPDATE users SET balance = balance - 75 WHERE user_id = ?", (user_id,))
        conn.commit()
    
    await state.clear()
    
    # Сразу отвечаем пользователю
    await message.answer("⏱ Ваше сообщение будет разослано в течении нескольких минут.")
    
    # Запускаем рассылку в фоновом режиме
    async def run_broadcast():
        sent_count = await broadcast_media_to_all_users("photo", file_id=photo_file_id, sender_id=user_id)
        await message.answer(f"✅ Фото отправлено всем пользователям! Получателей: {sent_count}\nСписано: 75🔥")
    
    asyncio.create_task(run_broadcast())


# ====== ОБРАБОТЧИКИ ДЛЯ ОТПРАВКИ GIF ======

@router.callback_query(F.data == "shop_broadcast_gif")
async def shop_broadcast_gif(callback: CallbackQuery, state: FSMContext):
    user_id = int(callback.from_user.id)
    
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        if not row:
            await callback.answer("❌ Профиль не найден.", show_alert=True)
            return
        balance = row[0]
    
    if balance < 100:
        await callback.answer("❌ Недостаточно средств (нужно 100🔥).", show_alert=True)
        return
    
    await safe_edit_message(callback.message, "🎬 Отправьте GIF, который вы хотите показать всем пользователям бота:\n\nЦена: 100🔥\n\nИспользуйте /cancel для отмены или кнопку «Назад».", reply_markup=broadcast_cancel_kb())
    await safe_edit_message(callback.message, "🎬 Отправьте GIF, который вы хотите показать всем пользователям бота:\n\nЦена: 100🔥\n\nИспользуйте /cancel для отмены.")


@router.message(MediaBroadcastState.waiting_for_gif, F.animation)
async def process_broadcast_gif(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    # Проверяем, что это именно GIF, а не видео или фото
    if message.video:
        await message.answer("❌ Вы отправили видео. Для отправки видео выберите соответствующий товар в магазине (150🔥).")
        return
    if message.photo:
        await message.answer("❌ Вы отправили фото. Для отправки фото выберите соответствующий товар в магазине (75🔥).")
        return
    
    gif_file_id = message.animation.file_id
    
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        if not row or row[0] < 100:
            await message.answer("❌ Недостаточно средств (нужно 100🔥).")
            await state.clear()
            return
        
        cur.execute("UPDATE users SET balance = balance - 100 WHERE user_id = ?", (user_id,))
        conn.commit()
    
    await state.clear()
    
    # Сразу отвечаем пользователю
    await message.answer("⏱ Ваше сообщение будет разослано в течении нескольких минут.")
    
    # Запускаем рассылку в фоновом режиме
    async def run_broadcast():
        sent_count = await broadcast_media_to_all_users("gif", file_id=gif_file_id, sender_id=user_id)
        await message.answer(f"✅ GIF отправлен всем пользователям! Получателей: {sent_count}\nСписано: 100🔥")
    
    asyncio.create_task(run_broadcast())


# ====== ОБРАБОТЧИКИ ДЛЯ ОТПРАВКИ ВИДЕО ======

@router.callback_query(F.data == "shop_broadcast_video")
async def shop_broadcast_video(callback: CallbackQuery, state: FSMContext):
    user_id = int(callback.from_user.id)
    
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        if not row:
            await callback.answer("❌ Профиль не найден.", show_alert=True)
            return
        balance = row[0]
    
    if balance < 150:
        await callback.answer("❌ Недостаточно средств (нужно 150🔥).", show_alert=True)
        return
    
    await safe_edit_message(callback.message, "🎥 Отправьте видео, которое вы хотите показать всем пользователям бота:\n\nЦена: 150🔥\n\nИспользуйте /cancel для отмены или кнопку «Назад».", reply_markup=broadcast_cancel_kb())
    await safe_edit_message(callback.message, "🎥 Отправьте видео, которое вы хотите показать всем пользователям бота:\n\nЦена: 150🔥\n\nИспользуйте /cancel для отмены.")


@router.message(MediaBroadcastState.waiting_for_video, F.video)
async def process_broadcast_video(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    # Проверяем, что это именно видео, а не GIF или фото
    if message.animation:
        await message.answer("❌ Вы отправили GIF. Для отправки GIF выберите соответствующий товар в магазине (100🔥).")
        return
    if message.photo:
        await message.answer("❌ Вы отправили фото. Для отправки фото выберите соответствующий товар в магазине (75🔥).")
        return
    
    video_file_id = message.video.file_id
    
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        if not row or row[0] < 150:
            await message.answer("❌ Недостаточно средств (нужно 150🔥).")
            await state.clear()
            return
        
        cur.execute("UPDATE users SET balance = balance - 150 WHERE user_id = ?", (user_id,))
        conn.commit()
    
    await state.clear()
    
    # Сразу отвечаем пользователю
    await message.answer("⏱ Ваше сообщение будет разослано в течении нескольких минут.")
    
    # Запускаем рассылку в фоновом режиме
    async def run_broadcast():
        sent_count = await broadcast_media_to_all_users("video", file_id=video_file_id, sender_id=user_id)
        await message.answer(f"✅ Видео отправлено всем пользователям! Получателей: {sent_count}\nСписано: 150🔥")
    
    asyncio.create_task(run_broadcast())


# ====== ОБРАБОТЧИКИ ДЛЯ ОТПРАВКИ АУДИО ======

@router.callback_query(F.data == "shop_broadcast_audio")
async def shop_broadcast_audio(callback: CallbackQuery, state: FSMContext):
    user_id = int(callback.from_user.id)
    
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        if not row:
            await callback.answer("❌ Профиль не найден.", show_alert=True)
            return
        balance = row[0]
    
    if balance < 50:
        await callback.answer("❌ Недостаточно средств (нужно 50🔥).", show_alert=True)
        return
    
    await safe_edit_message(callback.message, "🎙️ Отправьте аудиосообщение, которое вы хотите показать всем пользователям бота:\n\nЦена: 50🔥\n\nИспользуйте /cancel для отмены или кнопку «Назад».", reply_markup=broadcast_cancel_kb())
    await safe_edit_message(callback.message, "🎙️ Отправьте аудиосообщение, которое вы хотите показать всем пользователям бота:\n\nЦена: 50🔥\n\nИспользуйте /cancel для отмены.")


@router.message(MediaBroadcastState.waiting_for_audio, F.audio | F.voice)
async def process_broadcast_audio(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    # Определяем тип аудиофайла
    if message.audio:
        audio_file_id = message.audio.file_id
    elif message.voice:
        audio_file_id = message.voice.file_id
    else:
        await message.answer("❌ Это не аудиосообщение. Пожалуйста, отправьте аудио или голосовое сообщение.")
        return
    
    # Проверяем, что это не другой тип медиа
    if message.photo:
        await message.answer("❌ Вы отправили фото. Для отправки фото выберите соответствующий товар в магазине (75🔥).")
        return
    if message.animation:
        await message.answer("❌ Вы отправили GIF. Для отправки GIF выберите соответствующий товар в магазине (100🔥).")
        return
    if message.video:
        await message.answer("❌ Вы отправили видео. Для отправки видео выберите соответствующий товар в магазине (150🔥).")
        return
    
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        if not row or row[0] < 50:
            await message.answer("❌ Недостаточно средств (нужно 50🔥).")
            await state.clear()
            return
        
        cur.execute("UPDATE users SET balance = balance - 50 WHERE user_id = ?", (user_id,))
        conn.commit()
    
    await state.clear()
    
    # Сразу отвечаем пользователю
    await message.answer("⏱ Ваше сообщение будет разослано в течении нескольких минут.")
    
    # Запускаем рассылку в фоновом режиме
    async def run_broadcast():
        sent_count = await broadcast_media_to_all_users("audio", file_id=audio_file_id, sender_id=user_id)
        await message.answer(f"✅ Аудио отправлено всем пользователям! Получателей: {sent_count}\nСписано: 50🔥")
    
    asyncio.create_task(run_broadcast())


# ====== ОТМЕНА ======

@router.message(F.text == "/cancel")
async def cancel_handler(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state:
        await state.clear()
        await message.answer("❌ Действие отменено.")


# Обработчик кнопки "Назад" во время ожидания медиа
@router.callback_query(F.data == "shop_menu")
async def cancel_broadcast_via_button(callback: CallbackQuery, state: FSMContext):
    """Отмена рассылки через кнопку Назад."""
    current_state = await state.get_state()
    if current_state not in [
        MediaBroadcastState.waiting_for_text.state,
        MediaBroadcastState.waiting_for_photo.state,
        MediaBroadcastState.waiting_for_gif.state,
        MediaBroadcastState.waiting_for_video.state,
        MediaBroadcastState.waiting_for_audio.state,
    ]:
        return
    await state.clear()
    await shop_menu(callback)
