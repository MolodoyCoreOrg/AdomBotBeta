import random
import json
import os
import sqlite3
import asyncio
from datetime import datetime, timedelta

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, FSInputFile
from aiogram.exceptions import TelegramRetryAfter, TelegramBadRequest

from database.db import get_member_cards, update_member_cards, increment_stat, get_card_drop_counts, add_balance
from ..keyboard import get_main_keyboard
from ..picture import find_image_file
from utils.config import RARITY_WEIGHTS
from database.stats import increment_stat

router = Router()

active_open_members = {}

DB_PATH = "database/users.db"
TIMER_PATH = "data/table/timer_members_card.json"
MSK_OFFSET = timedelta(hours=3)
RESET_HOUR_UTC = 19  # 22:00 по МСК = 19:00 UTC

with open("data/cards/members.json", "r", encoding="utf-8") as f:
    MEMBER_CARDS = json.load(f)

def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_user_bonuses(user_id: int) -> int:
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT bonuses FROM users WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        return row["bonuses"] if row else 0

def consume_bonus(user_id: int):
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE users SET bonuses = bonuses - 1 WHERE user_id = ? AND bonuses > 0", (user_id,))
        conn.commit()







# --- Работа с таймерами ---
def get_last_sunday_22_msk(now_utc: datetime = None) -> datetime:
    now_utc = now_utc or datetime.utcnow()
    now_msk = now_utc + MSK_OFFSET
    days_since_sunday = (now_msk.weekday() + 1) % 7  # 0 = понедельник, 6 = воскресенье
    last_sunday = now_msk - timedelta(days=days_since_sunday)
    sunday_22_msk = last_sunday.replace(hour=22, minute=0, second=0, microsecond=0)
    return sunday_22_msk - MSK_OFFSET  # вернуть в UTC





def load_timers():
    if not os.path.exists(TIMER_PATH):
        return {}
    with open(TIMER_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_timers(timers: dict):
    with open(TIMER_PATH, "w", encoding="utf-8") as f:
        json.dump(timers, f, ensure_ascii=False, indent=2)

def get_user_timer(user_id: int):
    timers = load_timers()
    return timers.get(str(user_id), {
        "last_open": None,
        "can_open_after": None,
        "check_enabled": True
    })

def set_user_timer(user_id: int, last_open: datetime, check_enabled: bool = True):
    timers = load_timers()
    timers[str(user_id)] = {
        "last_open": last_open.isoformat(),
        "check_enabled": check_enabled
    }
    save_timers(timers)

def set_check_member_enabled(user_id: int, enabled: bool):
    timer = get_user_timer(user_id)
    last_open_str = timer.get("last_open")
    try:
        last_open = datetime.fromisoformat(last_open_str).date() if last_open_str else datetime.utcnow().date()
    except:
        last_open = datetime.utcnow().date()
    set_user_timer(user_id, datetime.combine(last_open, datetime.min.time()), check_enabled=enabled)

def is_reset_time_passed(dt: datetime) -> datetime:
    reset_dt = dt.replace(hour=RESET_HOUR_UTC, minute=0, second=0, microsecond=0)
    if dt < reset_dt:
        return reset_dt - timedelta(days=1)
    return reset_dt

async def can_open_card(user_id: int):
    timer = get_user_timer(user_id)
    if not timer.get("check_enabled", True):
        return True, "", False

    now = datetime.utcnow()
    if timer.get("can_open_after"):
        can_open_after = datetime.fromisoformat(timer["can_open_after"])
        if now < can_open_after:
            bonuses = get_user_bonuses(user_id)
            if bonuses > 0:
                return True, "", True
            diff = can_open_after - now
            return False, f"Ты уже открывал карточку. Попробуй через {diff.days} дн. {diff.seconds // 3600} ч. {(diff.seconds % 3600) // 60} мин.", False

    return True, "", False

def update_user_timer_after_open(user_id: int):
    now = datetime.utcnow()
    reset_time = get_last_sunday_22_msk(now) + timedelta(weeks=1)  # следующее воскресенье 22:00 МСК

    timers = load_timers()
    old_check_enabled = timers.get(str(user_id), {}).get("check_enabled", True)  # берем старое значение или True по умолчанию

    timers[str(user_id)] = {
        "last_open": now.isoformat(),
        "can_open_after": reset_time.isoformat(),
        "check_enabled": old_check_enabled  # сохраняем текущее состояние, не включаем принудительно True
    }
    save_timers(timers)









def weighted_random_choice(cards, user_id: int, user_cards=None,
                           duplicate_penalty=1.0, count_penalty_factor=1.0, noise_level=0.3):
    if user_cards is None:
        user_cards = []

    card_drop_counts = get_card_drop_counts(user_id)

    weighted = []
    for card in cards:
        base_weight = RARITY_WEIGHTS.get(card["rarity"], 0)

        # Карточки могут повторяться - не снижаем вес за дубликаты
        weight = base_weight

        drops = card_drop_counts.get(card["name"], 0)
        # Не снижаем вес за количество выпадений
        weight *= count_penalty_factor ** drops

        noise = random.uniform(1 - noise_level, 1 + noise_level)
        weight *= noise

        weighted.append((card, weight))

    total = sum(w for _, w in weighted)
    if total == 0:
        return random.choice(cards)

    r = random.uniform(0, total)
    upto = 0
    for card, weight in weighted:
        upto += weight
        if upto >= r:
            return card

    return cards[-1]











async def draw_member(event: CallbackQuery | Message):
    user_id = event.from_user.id
    can_open, msg, used_bonus = await can_open_card(user_id)
    if not can_open:
        await event.answer(msg, show_alert=True)
        return
    

    if active_open_members.get(user_id):
        await event.answer("⏳ Подожди, карта уже открывается.", show_alert=True)
        return
    active_open_members[user_id] = True


    try:
        user_cards = get_member_cards(user_id)
        card = weighted_random_choice(MEMBER_CARDS, user_id, user_cards.keys())

        name = card["name"]
        skill = card["skill"]
        rarity = card["rarity"]
        work = card["work"]
        image_filename = card["image"]

        if name in user_cards:
            # При получении повторки карты участника - просто повышаем ранг (без сжигания и без огоньков)
            user_cards[name]["rank"] += 1
            rank = user_cards[name]["rank"]
            text = (
                f"🔁 Тебе выпала повторная карточка: <b>{name}</b>\n"
                f"⭐ Редкость: <i>{rarity}</i>\n"
                f"🥇 Звание: <i>{work}</i>\n\n"
                f"🔼 Ранг карты повышен: <b>{rank}</b>\n"
                f"🧠 Получена суперспособность: <i>{skill}</i>"
            )
        else:
            rank = 1
            # mark receipt time for newly granted cards
            user_cards[name] = {"rank": rank, "skills": [skill], "received_at": datetime.utcnow().isoformat()}
            text = (
                f"🎉 Ты получил карточку участника: <b>{name}</b>\n"
                f"⭐ Редкость: <i>{rarity}</i>\n"
                f"🥇 Звание: <i>{work}</i>\n"
                f"🔰 Ранг: <b>{rank}</b>"
            )

        # Получаем путь к изображению по рангу
        image_path = f"data/images/members/rank_{rank}/{image_filename}"

        # Списываем бонус или обновляем таймер
        if used_bonus:
            consume_bonus(user_id)
        else:
            update_user_timer_after_open(user_id)

        update_member_cards(user_id, user_cards)
        increment_stat("cards_opened", "members")

        from database.db import load_roulette_data
        data = load_roulette_data(str(user_id))
        spins = data.get("roulette_count", 0)

        reply_markup = await get_main_keyboard(spins, user_id)

        if os.path.exists(image_path):
            photo = FSInputFile(image_path)
            try:
                if isinstance(event, CallbackQuery):
                    try:
                        await event.answer()
                    except Exception:
                        pass
                    try:
                        await event.message.delete()
                    except Exception:
                        pass
                    try:
                        await event.message.answer_photo(photo=photo, caption=text, reply_markup=reply_markup)
                    except TelegramRetryAfter as e:
                        await asyncio.sleep(e.retry_after)
                        await event.bot.send_photo(chat_id=event.from_user.id, photo=photo, caption=text, reply_markup=reply_markup)
                    except TelegramBadRequest:
                        await event.bot.send_photo(chat_id=event.from_user.id, photo=photo, caption=text, reply_markup=reply_markup)
                    except Exception as e:
                        try:
                            await event.bot.send_message(chat_id=event.from_user.id, text=text)
                        except Exception:
                            print(f"Failed to send member card to {event.from_user.id}: {e}")
                else:
                    try:
                        await event.delete()
                    except Exception:
                        pass
                    try:
                        await event.answer_photo(photo=photo, caption=text, reply_markup=reply_markup)
                    except TelegramRetryAfter as e:
                        await asyncio.sleep(e.retry_after)
                        await event.bot.send_photo(chat_id=event.chat.id, photo=photo, caption=text, reply_markup=reply_markup)
                    except TelegramBadRequest:
                        await event.bot.send_photo(chat_id=event.chat.id, photo=photo, caption=text, reply_markup=reply_markup)
                    except Exception as e:
                        try:
                            await event.bot.send_message(chat_id=event.chat.id, text=text)
                        except Exception:
                            print(f"Failed to send member card (message) to {event.chat.id}: {e}")
            finally:
                pass
        else:
            # Изображение отсутствует, но ранг все равно повышен
            try:
                if isinstance(event, CallbackQuery):
                    try:
                        await event.answer()
                    except Exception:
                        pass
                    try:
                        await event.message.delete()
                    except Exception:
                        pass
                    try:
                        await event.message.answer(f"{text}\n\n⚠️ Изображение карточки не найдено.", reply_markup=reply_markup)
                    except Exception:
                        await event.bot.send_message(chat_id=event.from_user.id, text=f"{text}\n\n⚠️ Изображение карточки не найдено.")
                else:
                    try:
                        await event.delete()
                    except Exception:
                        pass
                    try:
                        await event.answer(f"{text}\n\n⚠️ Изображение карточки не найдено.", reply_markup=reply_markup)
                    except Exception:
                        await event.bot.send_message(chat_id=event.chat.id, text=f"{text}\n\n⚠️ Изображение карточки не найдено.")
            finally:
                pass

    finally:
        active_open_members.pop(user_id, None)

@router.callback_query(F.data == "draw_member")
async def handle_draw_member_button(callback: CallbackQuery):
    await draw_member(callback)

@router.message(F.text == "👥 Карточка участника")
async def handle_draw_member_command(message: Message):
    await draw_member(message)