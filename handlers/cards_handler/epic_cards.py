import random
import sqlite3
import json
import os
import asyncio
from datetime import datetime, timedelta

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramRetryAfter, TelegramBadRequest

from database.db import (
    connect, get_skill_cards, update_skill_cards, add_balance,
    load_roulette_data, save_roulette_data, get_all_user_ids,
    find_user_by_username, get_user_full_data, add_skill_card
)
from handlers.picture import find_image_file
from utils.helpers import safe_delete

router = Router()

# Пути для хранения состояний активных карт
EPIC_ACTIVE_PATH = "data/table/epic_active_cards.json"
EPIC_CHAIN_PATH = "data/table/epic_chain_cards.json"

DB_PATH = "database/users.db"

# Состояния активных процессов
active_epic_cards = {}  # {user_id: {"card_name": ..., "state": ...}}
epic_card_usage_lock = {}  # {user_id: timestamp} - блокировка от повторного использования
epic_cards_in_progress = {}  # {user_id: card_name} - карта, которая используется (для защиты от дублей)


def connect_db():
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def get_user_mention(user_id: int, first_name: str = None, username: str = None) -> str:
    """Формирует упоминание пользователя."""
    if username:
        return f"@{username}"
    elif first_name:
        return first_name
    else:
        return f"пользователь {user_id}"


async def broadcast_message(bot, message_template: str, exclude_user_id: int = None):
    """Отправляет сообщение всем пользователям бота."""
    user_ids = get_all_user_ids()
    sent_count = 0
    
    for uid in user_ids:
        if exclude_user_id and uid == exclude_user_id:
            continue
        try:
            # Получаем данные пользователя для подстановки в шаблон
            user_data = get_user_full_data(uid)
            if user_data:
                text = message_template.replace("%юзер1%", get_user_mention(
                    uid, 
                    user_data.get("first_name"), 
                    user_data.get("username")
                ))
                await bot.send_message(chat_id=uid, text=text, parse_mode="HTML")
                sent_count += 1
        except Exception as e:
            # Игнорируем ошибки отправки (бот заблокирован и т.д.)
            pass
    
    return sent_count


def load_epic_active():
    """Загружает состояния активных эпических карт."""
    if not os.path.exists(EPIC_ACTIVE_PATH):
        return {}
    try:
        with open(EPIC_ACTIVE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_epic_active(data: dict):
    """Сохраняет состояния активных эпических карт."""
    os.makedirs(os.path.dirname(EPIC_ACTIVE_PATH), exist_ok=True)
    with open(EPIC_ACTIVE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_epic_chain():
    """Загружает состояния цепочки карт ХМММ."""
    if not os.path.exists(EPIC_CHAIN_PATH):
        return {}
    try:
        with open(EPIC_CHAIN_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_epic_chain(data: dict):
    """Сохраняет состояния цепочки карт ХМММ."""
    os.makedirs(os.path.dirname(EPIC_CHAIN_PATH), exist_ok=True)
    with open(EPIC_CHAIN_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# === КАРТА 1: БРАТАН ТЫ ЧОТКИЙ ===
async def use_bratan_chotkiy(callback: CallbackQuery, bot):
    """Карта хвалит случайного пользователя."""
    user_id = callback.from_user.id
    user_data = get_user_full_data(user_id)
    user_name = get_user_mention(user_id, user_data.get("first_name") if user_data else None, user_data.get("username") if user_data else None)
    
    # Выбираем случайного пользователя (кроме себя)
    all_users = get_all_user_ids()
    if len(all_users) <= 1:
        await callback.answer("Недостаточно пользователей для использования карты", show_alert=True)
        return
    
    target_id = random.choice([uid for uid in all_users if uid != user_id])
    target_data = get_user_full_data(target_id)
    target_name = get_user_mention(target_id, target_data.get("first_name") if target_data else None, target_data.get("username") if target_data else None)
    
    message = f"{user_name} использует карту \"БРАТАН ТЫ ЧОТКИЙ\" и хвалит {target_name}"
    
    # Отправляем сообщение всем
    await broadcast_message_with_template(bot, message, user_id, target_id)
    
    # Карта уже удалена в handle_use_epic_card
    await callback.answer("Карта использована! Все пользователи получили сообщение.", show_alert=True)


async def broadcast_message_with_template(bot, base_message: str, user_id: int, target_id: int = None):
    """Отправляет сообщение с подстановкой имен."""
    user_ids = get_all_user_ids()
    user_data = get_user_full_data(user_id)
    user_name = get_user_mention(user_id, user_data.get("first_name") if user_data else None, user_data.get("username") if user_data else None)
    
    if target_id:
        target_data = get_user_full_data(target_id)
        target_name = get_user_mention(target_id, target_data.get("first_name") if target_data else None, target_data.get("username") if target_data else None)
    
    for uid in user_ids:
        try:
            text = base_message.replace("%юзер1%", user_name)
            if target_id and "%юзер2%" in text:
                text = text.replace("%юзер2%", target_name)
            await bot.send_message(chat_id=uid, text=text, parse_mode="HTML")
        except Exception:
            pass


# === КАРТА 2: УРААА ===
async def use_uraaa(callback: CallbackQuery, bot):
    """Сброс таймера карты участника для себя или друга."""
    user_id = callback.from_user.id

    # Показываем выбор: использовать на себя или подарить другу
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🎯 Использовать на себя", callback_data="uraaa_self")
    )
    builder.row(
        InlineKeyboardButton(text="🎁 Подарить другу", callback_data="uraaa_gift")
    )
    builder.row(
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_epic_card")
    )

    await callback.message.answer(
        "Выберите действие для карты \"УРААА\":\n\n"
        "🎯 <b>Использовать на себя</b> — сбросить таймер карты участника\n"
        "🎁 <b>Подарить другу</b> — отправить карту другу по username",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )


# === ОБРАБОТЧИКИ ДЛЯ КАРТЫ УРААА ===
@router.callback_query(F.data == "uraaa_self")
async def handle_uraaa_self(callback: CallbackQuery, bot):
    """Использование карты УРААА на себя — сброс таймера карты участника"""
    user_id = callback.from_user.id

    # Удаляем карту у пользователя
    remove_skill_card(user_id, "УРААА")

    # Импортируем функцию сброса таймера участника
    from .members import TIMER_PATH as MEMBER_TIMER_PATH
    import json

    # Сбрасываем таймер карты участника
    timers = {}
    if os.path.exists(MEMBER_TIMER_PATH):
        with open(MEMBER_TIMER_PATH, "r", encoding="utf-8") as f:
            timers = json.load(f)

    # Устанавливаем, что можно открыть карту сейчас
    timers[str(user_id)] = {
        "last_open": None,
        "can_open_after": None,
        "check_enabled": True
    }

    with open(MEMBER_TIMER_PATH, "w", encoding="utf-8") as f:
        json.dump(timers, f, ensure_ascii=False, indent=2)

    await callback.message.edit_text(
        "🎉 Таймер карты участника сброшен! Теперь ты можешь открыть новую карту!",
        reply_markup=None
    )
    await callback.answer("✅ Карта УРААА использована!")


@router.callback_query(F.data == "uraaa_gift")
async def handle_uraaa_gift(callback: CallbackQuery, bot):
    """Подарить карту УРААА другу"""
    user_id = callback.from_user.id

    await callback.message.edit_text(
        "Введите @username пользователя, которому хотите подарить карту:",
        reply_markup=get_back_button()
    )

    # Сохраняем состояние ожидания
    active_epic_cards[user_id] = {"card": "УРААА", "step": "waiting_username"}


# === КАРТА 3: БАБКИ НЕ ПРОБЛЕМА ===
async def use_babki_ne_problema(callback: CallbackQuery, bot):
    """Дарит всем пользователям +1🔥"""
    user_id = callback.from_user.id
    user_data = get_user_full_data(user_id)
    user_name = get_user_mention(user_id, user_data.get("first_name") if user_data else None, user_data.get("username") if user_data else None)
    
    message = f"{user_name} использует карту \"БАБКИ НЕ ПРОБЛЕМА\" и дарит всем пользователям бота +1🔥"
    
    # Выдаем всем по 1 огню
    user_ids = get_all_user_ids()
    for uid in user_ids:
        add_balance(uid, 1)
    
    # Отправляем сообщение всем
    await broadcast_message_with_template(bot, message, user_id)
    
    # Карта уже удалена в handle_use_epic_card
    await callback.answer("💸 Раздаем баксы всем...", show_alert=False)


# === КАРТА 4: ВСЕ В АЖУРЕ ===
async def use_vse_v_azhure(callback: CallbackQuery, bot):
    """Раздает +2 крутки всем пользователям"""
    user_id = callback.from_user.id
    user_data = get_user_full_data(user_id)
    user_name = get_user_mention(user_id, user_data.get("first_name") if user_data else None, user_data.get("username") if user_data else None)
    
    message = f"{user_name} применяет карту \"ВСЕ В АЖУРЕ\" и раздает +2 крутки всем пользователям бота"
    
    # Выдаем всем по 2 крутки
    user_ids = get_all_user_ids()
    for uid in user_ids:
        data = load_roulette_data(uid)
        data["roulette_count"] = data.get("roulette_count", 0) + 2
        save_roulette_data(uid, data)
    
    # Отправляем сообщение всем
    await broadcast_message_with_template(bot, message, user_id)
    
    # Карта уже удалена в handle_use_epic_card
    await callback.answer("🎡 Раздаем крутки всем...", show_alert=False)


# === КАРТА 5: ХИХИКС ===
async def use_hihiks(callback: CallbackQuery, bot):
    """Выдает всем по поджопнику"""
    user_id = callback.from_user.id
    user_data = get_user_full_data(user_id)
    user_name = get_user_mention(user_id, user_data.get("first_name") if user_data else None, user_data.get("username") if user_data else None)
    
    message = f"{user_name} применяет карту \"ХИХИКС\" и выдает всем по поджопнику"
    
    # Выдаем всем поджопник (увеличиваем jopa_count)
    user_ids = get_all_user_ids()
    for uid in user_ids:
        data = load_roulette_data(uid)
        data["jopa_count"] = data.get("jopa_count", 0) + 1
        save_roulette_data(uid, data)
    
    # Отправляем сообщение всем
    await broadcast_message_with_template(bot, message, user_id)
    
    # Карта уже удалена в handle_use_epic_card
    await callback.answer("😄 Все получили поджопник!", show_alert=False)


# === КАРТА 6: ХМММ (цепочка) ===
async def use_hmmm(callback: CallbackQuery, bot):
    """Запускает цепочку выбора: 2 крутки себе или x2 другому"""
    user_id = callback.from_user.id
    
    # Создаем начальное состояние цепочки
    chain_state = {
        "current_user": user_id,
        "spins_amount": 2,
        "created_at": datetime.utcnow().isoformat(),
        "expires_at": (datetime.utcnow() + timedelta(hours=24)).isoformat()
    }
    
    epic_chain = load_epic_chain()
    epic_chain[str(user_id)] = chain_state
    save_epic_chain(epic_chain)
    
    # Показываем выбор пользователю
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🎁 {chain_state['spins_amount']} крутки тебе", callback_data=f"hmmm_take:{chain_state['spins_amount']}")],
        [InlineKeyboardButton(text="🔄 x2 другому", callback_data="hmmm_double_other")]
    ])
    
    await callback.message.answer(
        "🤔 Карта ХМММ\n\nВыбери:\n• Забрать крутки себе\n• Удвоить и передать следующему игроку",
        reply_markup=keyboard
    )
    
    # Карта уже удалена в handle_use_epic_card


async def hmmm_take_spins(callback: CallbackQuery, spins: int):
    """Пользователь забирает крутки себе"""
    user_id = callback.from_user.id
    
    # Начисляем крутки
    data = load_roulette_data(user_id)
    data["roulette_count"] = data.get("roulette_count", 0) + spins
    save_roulette_data(user_id, data)
    
    # Очищаем цепочку
    epic_chain = load_epic_chain()
    if str(user_id) in epic_chain:
        del epic_chain[str(user_id)]
        save_epic_chain(epic_chain)
    
    # Сообщение всем
    user_data = get_user_full_data(user_id)
    user_name = get_user_mention(user_id, user_data.get("first_name") if user_data else None, user_data.get("username") if user_data else None)
    
    message = f"{user_name} забирает себе {spins} круток"
    await broadcast_message_with_template(bot=None, base_message=message, user_id=user_id)
    
    await callback.answer(f"Ты получил {spins} круток!", show_alert=True)


async def hmmm_double_other(callback: CallbackQuery, bot):
    """Удваивает и передает следующему"""
    user_id = callback.from_user.id
    
    epic_chain = load_epic_chain()
    chain_key = str(user_id)
    
    if chain_key not in epic_chain:
        await callback.answer("Цепочка не найдена", show_alert=True)
        return
    
    current_spins = epic_chain[chain_key]["spins_amount"]
    new_spins = current_spins * 2
    
    # Выбираем случайного пользователя (кроме текущего)
    all_users = get_all_user_ids()
    other_users = [uid for uid in all_users if uid != user_id]
    
    if not other_users:
        # Если нет других игроков, забираем себе
        await hmmm_take_spins(callback, new_spins)
        return
    
    next_user = random.choice(other_users)
    
    # Обновляем цепочку для следующего пользователя
    epic_chain[str(next_user)] = {
        "current_user": next_user,
        "spins_amount": new_spins,
        "created_at": datetime.utcnow().isoformat(),
        "expires_at": (datetime.utcnow() + timedelta(hours=24)).isoformat()
    }
    
    # Удаляем старую запись
    if chain_key in epic_chain:
        del epic_chain[chain_key]
    
    save_epic_chain(epic_chain)
    
    # Отправляем сообщение следующему пользователю
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🎁 {new_spins} крутки тебе", callback_data=f"hmmm_take:{new_spins}")],
        [InlineKeyboardButton(text="🔄 x2 другому", callback_data="hmmm_double_other")]
    ])
    
    try:
        await bot.send_message(
            chat_id=next_user,
            text=f"🎲 Тебе передана карта ХМММ!\n\nТекущий приз: {new_spins} круток\n\nВыбери:\n• Забрать крутки себе\n• Удвоить и передать дальше",
            reply_markup=keyboard
        )
    except Exception:
        pass
    
    await callback.answer(f"Карта передана следующему игроку! Приз удвоен до {new_spins} круток", show_alert=True)


async def check_hmmm_expirations(bot):
    """Проверяет истекшие цепочки и передает их дальше"""
    epic_chain = load_epic_chain()
    now = datetime.utcnow()
    
    expired_keys = []
    
    for key, state in epic_chain.items():
        expires_at = datetime.fromisoformat(state["expires_at"])
        if now >= expires_at:
            expired_keys.append(key)
    
    for key in expired_keys:
        current_user = int(key)
        spins = epic_chain[key]["spins_amount"]
        
        # Выбираем нового случайного пользователя
        all_users = get_all_user_ids()
        other_users = [uid for uid in all_users if uid != current_user]
        
        if other_users:
            next_user = random.choice(other_users)
            
            epic_chain[str(next_user)] = {
                "current_user": next_user,
                "spins_amount": spins,  # То же количество
                "created_at": datetime.utcnow().isoformat(),
                "expires_at": (datetime.utcnow() + timedelta(hours=24)).isoformat()
            }
            
            # Отправляем уведомление
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=f"🎁 {spins} крутки тебе", callback_data=f"hmmm_take:{spins}")],
                [InlineKeyboardButton(text="🔄 x2 другому", callback_data="hmmm_double_other")]
            ])
            
            try:
                await bot.send_message(
                    chat_id=next_user,
                    text=f"⏰ Предыдущий игрок не ответил вовремя!\n\nТебе передана карта ХМММ с {spins} крутками",
                    reply_markup=keyboard
                )
            except Exception:
                pass
        
        # Удаляем старую запись
        del epic_chain[key]
    
    if expired_keys:
        save_epic_chain(epic_chain)


# === КАРТА 7: МЕГАЛУДИК ===
async def use_megaludik(callback: CallbackQuery):
    """Прокручивает все доступные крутки и выводит статистику"""
    user_id = callback.from_user.id
    
    # Получаем количество круток
    data = load_roulette_data(user_id)
    spins = data.get("roulette_count", 0)
    
    if spins <= 0:
        await callback.answer("У тебя нет круток для использования этой карты", show_alert=True)
        return
    
    # Симулируем прокрутку
    empty_count = 0
    podzhopnik_count = 0
    card_count = 0
    
    for _ in range(spins):
        rand = random.random()
        if rand < 0.7:  # 70% пустышек
            empty_count += 1
        elif rand < 0.95:  # 25% поджопников
            podzhopnik_count += 1
        else:  # 5% карт
            card_count += 1
    
    # Списываем крутки
    data["roulette_count"] = 0
    save_roulette_data(user_id, data)
    
    result_text = (
        f"🎰 Ты прокрутил {spins} круток из них:\n"
        f"🗑️ {empty_count} пустышек\n"
        f"🍑 {podzhopnik_count} поджопник(ов)\n"
        f"🎴 {card_count} карта(ы) способности"
    )
    
    await callback.message.answer(result_text)
    
    # Карта уже удалена в handle_use_epic_card


# === КАРТА 8: КРУТАЧКИ ===
async def use_krutachki(callback: CallbackQuery):
    """Выдает 15 круток"""
    user_id = callback.from_user.id

    # Даем 15 круток
    spins = 15

    data = load_roulette_data(user_id)
    data["roulette_count"] = data.get("roulette_count", 0) + spins
    save_roulette_data(user_id, data)

    await callback.answer(f"Ты получил {spins} круток!", show_alert=True)

    # Карта уже удалена в handle_use_epic_card


# === КАРТА 9: ОУ ДА БЕБИ ===
async def use_ou_da_bebi(callback: CallbackQuery):
    """Выдает рандомное бесплатное улучшение казика"""
    user_id = callback.from_user.id
    
    upgrades = [
        ("has_double_casino", "Двойное казино"),
        ("has_fast_spin", "Быстрый спин"),
        ("upgrade_timer_reduce", "Сокращение таймера")
    ]
    
    chosen_upgrade = random.choice(upgrades)
    
    data = load_roulette_data(user_id)
    
    if chosen_upgrade[0] in ["has_double_casino", "has_fast_spin"]:
        data[chosen_upgrade[0]] = 1
    else:
        data[chosen_upgrade[0]] = data.get(chosen_upgrade[0], 0) + 1
    
    save_roulette_data(user_id, data)
    
    await callback.answer(f"Ты получил улучшение: {chosen_upgrade[1]}!", show_alert=True)
    
    # Карта уже удалена в handle_use_epic_card


# === КАРТА 10: ВЫГОДНАЯ СДЕЛКА ===
async def use_vygodnaya_sdelka(callback: CallbackQuery):
    """Делает x2 к продаже следующей карты"""
    user_id = callback.from_user.id
    
    # Сохраняем состояние
    active = load_epic_active()
    active[str(user_id)] = {
        "card": "ВЫГОДНАЯ СДЕЛКА",
        "active": True,
        "activated_at": datetime.utcnow().isoformat()
    }
    save_epic_active(active)
    
    await callback.answer("Следующая продажа карты будет x2!", show_alert=True)
    
    # Карта уже удалена в handle_use_epic_card


def check_vygodnaya_sdelka(user_id: int, base_price: int) -> int:
    """Проверяет активен ли множитель x2 для продажи"""
    active = load_epic_active()
    user_state = active.get(str(user_id))
    
    if user_state and user_state.get("card") == "ВЫГОДНАЯ СДЕЛКА" and user_state.get("active"):
        # Удаляем состояние
        del active[str(user_id)]
        save_epic_active(active)
        return base_price * 2
    
    return base_price


# === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===
def remove_skill_card(user_id: int, card_name: str):
    """Удаляет карту суперспособности у пользователя"""
    cards = get_skill_cards(user_id)
    if card_name in cards:
        del cards[card_name]
        update_skill_cards(user_id, cards)


def get_back_button() -> InlineKeyboardMarkup:
    """Клавиатура с кнопкой назад"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_epic_card")]
    ])


# === ОБРАБОТЧИКИ CALLBACK ===
@router.callback_query(F.data.startswith("use_epic_card:"))
async def handle_use_epic_card(callback: CallbackQuery, bot):
    """Обработчик использования эпической карты"""
    import time
    card_name = callback.data.split(":", 1)[1]
    user_id = callback.from_user.id

    # Проверяем, не используется ли карта уже (защита от мультикликов)
    if user_id in epic_cards_in_progress:
        await callback.answer("⏳ Карта уже используется, дождитесь завершения эффекта!", show_alert=True)
        return

    # Проверяем наличие карты у пользователя
    cards = get_skill_cards(user_id)
    if card_name not in cards:
        await callback.answer("У тебя нет этой карты", show_alert=True)
        return

    # Помечаем карту как используемую (блокировка)
    epic_cards_in_progress[user_id] = card_name

    # Карты, которые требуют отложенного удаления (показывают выбор пользователю)
    deferred_removal_cards = ["УРААА"]

    # Удаляем карту сразу для всех, кроме тех, что требуют отложенного удаления
    if card_name not in deferred_removal_cards:
        remove_skill_card(user_id, card_name)

    # Вызываем соответствующую функцию
    card_handlers = {
        "БРАТАН ТЫ ЧОТКИЙ": lambda: use_bratan_chotkiy(callback, bot),
        "УРААА": lambda: use_uraaa(callback, bot),
        "БАБКИ НЕ ПРОБЛЕМА": lambda: use_babki_ne_problema(callback, bot),
        "ВСЕ В АЖУРЕ": lambda: use_vse_v_azhure(callback, bot),
        "ХИХИКС": lambda: use_hihiks(callback, bot),
        "ХМММ": lambda: use_hmmm(callback, bot),
        "МЕГАЛУДИК": lambda: use_megaludik(callback),
        "КРУТАЧКИ": lambda: use_krutachki(callback),
        "ОУ ДА БЕБИ": lambda: use_ou_da_bebi(callback),
        "ВЫГОДНАЯ СДЕЛКА": lambda: use_vygodnaya_sdelka(callback)
    }

    handler = card_handlers.get(card_name)
    if handler:
        try:
            await handler()
        finally:
            # Снимаем блокировку после выполнения (независимо от результата)
            if user_id in epic_cards_in_progress:
                del epic_cards_in_progress[user_id]
    else:
        # Снимаем блокировку при ошибке
        if user_id in epic_cards_in_progress:
            del epic_cards_in_progress[user_id]
        await callback.answer("Неизвестная карта", show_alert=True)


@router.callback_query(F.data.startswith("hmmm_take:"))
async def handle_hmmm_take(callback: CallbackQuery):
    """Обработчик забирания круток из цепочки ХМММ"""
    spins = int(callback.data.split(":")[1])
    await hmmm_take_spins(callback, spins)


@router.callback_query(F.data == "hmmm_double_other")
async def handle_hmmm_double(callback: CallbackQuery, bot):
    """Обработчик удвоения и передачи в цепочке ХМММ"""
    await hmmm_double_other(callback, bot)


@router.callback_query(F.data == "cancel_epic_card")
async def handle_cancel_epic(callback: CallbackQuery):
    """Отмена действия с эпической картой"""
    user_id = callback.from_user.id
    if user_id in active_epic_cards:
        del active_epic_cards[user_id]
    await callback.answer("Действие отменено", show_alert=True)


# === ОБРАБОТЧИК СООБЩЕНИЙ ДЛЯ КАРТЫ УРААА ===
@router.message(F.text.startswith("@"))
async def process_username_for_uraaa(message: Message, bot):
    """Обработка username для карты УРААА"""
    user_id = message.from_user.id

    if user_id not in active_epic_cards or active_epic_cards[user_id].get("card") != "УРААА":
        return

    username = message.text.strip().lstrip("@")
    target_user = find_user_by_username(username)

    if not target_user:
        await message.answer("Пользователь не найден. Попробуйте еще раз:")
        return

    target_user_id = target_user["user_id"]

    # Проверяем, не пытается ли пользователь подарить карту самому себе
    if target_user_id == user_id:
        await message.answer("Нельзя подарить карту самому себе! Используй кнопку 'Использовать на себя'.")
        return

    # Удаляем карту у отправителя
    remove_skill_card(user_id, "УРААА")

    # Добавляем карту другу
    add_skill_card(target_user_id, "УРААА")

    # Очищаем состояние
    del active_epic_cards[user_id]

    # Уведомляем отправителя
    await message.answer(f"🎁 Ты подарил карту УРААА пользователю @{username}!")

    # Уведомляем получателя
    try:
        sender_data = get_user_full_data(user_id)
        sender_name = get_user_mention(user_id, sender_data.get("first_name") if sender_data else None, sender_data.get("username") if sender_data else None)

        await bot.send_message(
            chat_id=target_user_id,
            text=f"🎁 {sender_name} подарил тебе карту УРААА!\n\n"
                 f"Карта добавлена в твою коллекцию. Используй её, чтобы сбросить таймер карты участника!",
            parse_mode="HTML"
        )
    except Exception:
        # Если не удалось отправить сообщение (бот заблокирован и т.д.), игнорируем
        pass


# === ПЕРИОДИЧЕСКАЯ ПРОВЕРКА ИСТЕЧЕНИЙ ===
async def start_epic_card_scheduler(bot):
    """Запускает периодическую проверку истечений цепочек"""
    while True:
        await asyncio.sleep(3600)  # Проверка каждый час
        await check_hmmm_expirations(bot)
