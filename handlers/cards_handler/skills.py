import random, sqlite3, json, os, asyncio
from datetime import datetime, timedelta

from aiogram import Router, F
from aiogram.types import CallbackQuery, FSInputFile, Message
from aiogram.exceptions import TelegramRetryAfter, TelegramBadRequest

from ..keyboard import get_main_keyboard
from database.db import get_skill_cards, update_skill_cards, add_balance
from ..picture import find_image_file
from database.stats import increment_stat
from utils.config import RARITY_WEIGHTS

router = Router()

active_open_skills = {}

TIMER_PATH = "data/table/timer_skills_card.json"
LAST_AWARDED_PATH = "data/table/last_awarded_skills.json"
LAST_AWARDED_TTL = 30  # seconds; window to avoid giving same card to many users simultaneously
DB_PATH = "database/users.db"
RESET_HOUR_UTC = 19  # 22:00 по МСК = 19:00 UTC

with open("data/cards/skills.json", "r", encoding="utf-8") as f:
    SKILLS_CARDS = json.load(f)

def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_skill_bonuses(user_id: int) -> int:
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT skill_bonuses FROM users WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        return row["skill_bonuses"] if row else 0

def consume_bonus(user_id: int):
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE users SET skill_bonuses = skill_bonuses - 1 WHERE user_id = ? AND skill_bonuses > 0", (user_id,))
        conn.commit()

# === Таймеры ===
def get_next_reset_time(now: datetime) -> datetime:
    reset_time = now.replace(hour=RESET_HOUR_UTC, minute=0, second=0, microsecond=0)
    if now >= reset_time:
        reset_time += timedelta(days=1)
    return reset_time





# --- Работа с таймерами ---
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
        "last_open": last_open.date().isoformat(),
        "check_enabled": check_enabled
    }
    save_timers(timers)

def set_check_enabled(user_id: int, enabled: bool):
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
            bonuses = get_skill_bonuses(user_id)
            if bonuses > 0:
                return True, "", True
            diff = can_open_after - now
            return False, f"Ты уже открывал карточку. Попробуй через {diff.days} дн. {diff.seconds // 3600} ч. {(diff.seconds % 3600) // 60} мин.", False

    return True, "", False

def update_user_timer_after_open(user_id: int):
    now = datetime.utcnow()
    reset_time = get_next_reset_time(now)

    timers = load_timers()
    old_check_enabled = timers.get(str(user_id), {}).get("check_enabled", True)  # берем старое значение или True по умолчанию

    timers[str(user_id)] = {
        "last_open": now.isoformat(),
        "can_open_after": reset_time.isoformat(),
        "check_enabled": old_check_enabled  # сохраняем текущее состояние, не включаем принудительно True
    }
    save_timers(timers)


def set_check_skill_enabled(user_id: int, enabled: bool):
    timer = get_user_timer(user_id)
    try:
        last_open = datetime.fromisoformat(timer.get("last_open")) if timer.get("last_open") else datetime.utcnow()
        can_open_after = datetime.fromisoformat(timer.get("can_open_after")) if timer.get("can_open_after") else datetime.utcnow()
    except Exception:
        last_open = datetime.utcnow()
        can_open_after = datetime.utcnow()

    set_user_timer(user_id, last_open, check_enabled=enabled)

# === Выбор карточки ===
def weighted_random_choice(user_cards, skills_path="data/cards/skills.json"):
    if not isinstance(skills_path, (str, bytes, type(None))):
        raise TypeError(f"Неверный тип пути: {type(skills_path)}")
    
    with open(skills_path, "r", encoding="utf-8") as f:
        all_cards = json.load(f)

    # Load last awarded timestamps and exclude recently awarded cards
    try:
        if os.path.exists(LAST_AWARDED_PATH):
            with open(LAST_AWARDED_PATH, "r", encoding="utf-8") as la:
                last_awarded = json.load(la)
        else:
            last_awarded = {}
    except Exception:
        last_awarded = {}

    now_ts = datetime.utcnow().timestamp()

    # Карточки могут повторяться - не фильтруем owned_names
    # Exclude only cards awarded to anyone in the recent TTL to reduce collisions
    available_cards = []
    for card in all_cards:
        name = card.get("name")
        last_ts = last_awarded.get(name)
        if last_ts and (now_ts - float(last_ts) < LAST_AWARDED_TTL):
            # skip recently awarded card to reduce collisions
            continue
        available_cards.append(card)

    if not available_cards:
        return None

    # Группируем карточки по редкости
    cards_by_rarity = {}
    for card in available_cards:
        rarity = card.get("rarity", "Обычная")
        if rarity not in cards_by_rarity:
            cards_by_rarity[rarity] = []
        cards_by_rarity[rarity].append(card)

    # Выбираем редкость на основе весов из конфигурации
    available_rarities = list(cards_by_rarity.keys())
    if not available_rarities:
        return None

    # Создаем список весов для доступных редкостей
    weights = []
    for rarity in available_rarities:
        weight = RARITY_WEIGHTS.get(rarity, 1)  # По умолчанию вес 1
        weights.append(weight)

    # Выбираем редкость с учетом весов
    chosen_rarity = random.choices(available_rarities, weights=weights, k=1)[0]
    
    # Выбираем случайную карточку из выбранной редкости
    chosen_card = random.choice(cards_by_rarity[chosen_rarity])
    
    return chosen_card





# === Основная логика ===
async def draw_skill(event: CallbackQuery | Message):
    user_id = event.from_user.id
    can_open, msg, _ = await can_open_card(user_id)
    used_skill_bonus = get_skill_bonuses(user_id) > 0

    if not can_open and not used_skill_bonus:
        if isinstance(event, CallbackQuery):
            await event.answer(msg, show_alert=True)
        else:
            await event.answer(msg)
        return
    
    if active_open_skills.get(user_id):
        await event.answer("⏳ Подожди, карта уже открывается.", show_alert=True)
        return
    active_open_skills[user_id] = True


    try:
        user_cards = get_skill_cards(user_id)
        # Передаем все карточки пользователя, функция weighted_random_choice теперь игнорирует owned_names
        card = weighted_random_choice(user_cards=user_cards)
        if not card:
            try:
                await event.message.answer("Ты уже собрал все карточки!")
            except TelegramRetryAfter as e:
                print(f"Flood control: ждем {e.retry_after} секунд.")
            except Exception as e:
                print(f"Ошибка при отправке сообщения: {e}")
            return

        name = card["name"]
        rarity = card.get("rarity", "Неизвестно")
        image_name = card.get('image')
        image_path = None
        if image_name:
            image_path = find_image_file(image_name.split('.')[0], "data/images/skills")

        if not image_path or not os.path.exists(image_path):
            await event.message.answer("❌ Изображение не найдено.")
            return

        # Награда за сжигание повторной карточки в зависимости от редкости
        burn_rewards = {
            "Обычная": 1,
            "Редкая": 5,
            "Эпическая": 9,
            "Легендарная": 10
        }

        # Проверяем, есть ли уже эта карточка у пользователя
        owned = set(user_cards.keys()) - {"_last_draw"}
        if name in owned:
            # Повторная карточка - сжигаем и даем валюту
            reward_amount = burn_rewards.get(rarity, 1)
            new_balance = add_balance(user_id, reward_amount)
            text = (
                f"🔁 Тебе выпала повторная карточка: <b>{name}</b>\n"
                f"⭐ Редкость: <i>{rarity}</i>\n\n"
                f"🔥 Она автоматически сожглась, и ты получил <b>{reward_amount}🔥</b> на свой счёт!\n"
                f"💰 Твой баланс: {new_balance}🔥"
            )
        else:
            # Новая карточка
            rank = 1
            user_cards[name] = {"rank": 1, "received_at": datetime.utcnow().isoformat()}
            text = f"🎉 Ты получил карточку умения!\n<b>{name}</b>\n⭐ Редкость: <i>{rarity}</i>"

        # persist last-awarded timestamp to reduce duplicate drops across users
        try:
            if os.path.exists(LAST_AWARDED_PATH):
                with open(LAST_AWARDED_PATH, "r", encoding="utf-8") as la:
                    last_awarded = json.load(la)
            else:
                last_awarded = {}
        except Exception:
            last_awarded = {}

        try:
            last_awarded[name] = datetime.utcnow().timestamp()
            os.makedirs(os.path.dirname(LAST_AWARDED_PATH), exist_ok=True)
            with open(LAST_AWARDED_PATH, "w", encoding="utf-8") as la:
                json.dump(last_awarded, la)
        except Exception:
            # non-fatal: just log
            print(f"Failed to persist last_awarded for {name}")


        if used_skill_bonus:
            consume_bonus(user_id)
        elif can_open:
            update_user_timer_after_open(user_id)

        update_skill_cards(user_id, user_cards)
        increment_stat("cards_opened", "skills")

        from database.db import load_roulette_data
        data = load_roulette_data(str(user_id))
        spins = data.get("roulette_count", 0)  

        reply_markup = await get_main_keyboard(spins, user_id)

        photo = FSInputFile(image_path)
        # Send result with robust error handling and fallbacks
        try:
            if isinstance(event, CallbackQuery):
                # Acknowledge callback to remove 'loading' state
                try:
                    await event.answer()
                except Exception:
                    pass

                # Try to delete the original message (ignore failures)
                try:
                    from utils.helpers import safe_delete
                    await safe_delete(event)
                except Exception:
                    pass

                # Primary send: reply in the same chat
                try:
                    await event.message.answer_photo(photo=photo, caption=text, parse_mode="HTML", reply_markup=reply_markup)
                except TelegramRetryAfter as e:
                    await asyncio.sleep(e.retry_after)
                    await event.bot.send_photo(chat_id=event.from_user.id, photo=photo, caption=text, parse_mode="HTML", reply_markup=reply_markup)
                except TelegramBadRequest:
                    # Fallback to send_photo directly
                    await event.bot.send_photo(chat_id=event.from_user.id, photo=photo, caption=text, parse_mode="HTML", reply_markup=reply_markup)
                except Exception as e:
                    # Last-resort: send text-only message
                    try:
                        await event.bot.send_message(chat_id=event.from_user.id, text=text, parse_mode="HTML")
                    except Exception:
                        # give up silently but log
                        print(f"Failed to send skill card to {event.from_user.id}: {e}")

            else:
                # Message-based handler
                try:
                    from utils.helpers import safe_delete
                    await safe_delete(event)
                except Exception:
                    pass

                try:
                    await event.answer_photo(photo=photo, caption=text, parse_mode="HTML", reply_markup=reply_markup)
                except TelegramRetryAfter as e:
                    await asyncio.sleep(e.retry_after)
                    await event.bot.send_photo(chat_id=event.chat.id, photo=photo, caption=text, parse_mode="HTML", reply_markup=reply_markup)
                except TelegramBadRequest:
                    await event.bot.send_photo(chat_id=event.chat.id, photo=photo, caption=text, parse_mode="HTML", reply_markup=reply_markup)
                except Exception as e:
                    try:
                        await event.bot.send_message(chat_id=event.chat.id, text=text, parse_mode="HTML")
                    except Exception:
                        print(f"Failed to send skill card (message) to {event.chat.id}: {e}")

        finally:
            # ensure no leftover state; nothing to do but keep function stable
            pass
    finally:
        active_open_skills.pop(user_id, None)

# === Хендлеры ===
@router.callback_query(F.data == "draw_skill")
async def handle_draw_skill_button(callback: CallbackQuery):
    await draw_skill(callback)

@router.message(F.text == "🎴 Карточка способностей")
async def handle_draw_skill_command(message: Message):
    await draw_skill(message)
def award_specific_skill(user_id: int, card_name: str) -> bool:
    """
    Выдаёт пользователю конкретную карту суперспособности по имени.
    Возвращает True, если карта успешно добавлена (или уже есть), иначе False.
    """
    # Загружаем список всех карт
    with open("data/cards/skills.json", "r", encoding="utf-8") as f:
        all_cards = json.load(f)

    # Ищем карту с таким именем
    target_card = None
    for card in all_cards:
        if card["name"].lower() == card_name.lower():
            target_card = card
            break

    if not target_card:
        return False

    # Получаем текущие карты пользователя
    user_cards = get_skill_cards(user_id)
    if card_name in user_cards:
        # Карта уже есть, ничего не делаем, но возвращаем True
        return True

    # Добавляем карту
    user_cards[card_name] = {"rank": 1, "received_at": datetime.utcnow().isoformat()}
    update_skill_cards(user_id, user_cards)
    return True