"""
Модуль системы обмена карточками между пользователями.
Реализует полный цикл обмена через кнопки:
- Создание обмена через кнопку "➕ Создать обмен"
- Выбор типа карт (участники/суперспособности)
- Просмотр и выбор карт партнера
- Принятие/отклонение обмена
- Навигация кнопкой "↪️ Назад"
"""

import logging
import json
import sqlite3
from datetime import datetime
from typing import Optional, Dict, Any, List

from aiogram import Router, F, types
from aiogram.types import CallbackQuery, Message, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramBadRequest
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.db import get_member_cards, get_skill_cards

logger = logging.getLogger(__name__)

router = Router()

DB_PATH = "database/users.db"

def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ====== FSM States ======
class TradeState(StatesGroup):
    waiting_for_partner = State()
    selecting_card_type = State()
    viewing_partner_cards = State()
    selecting_own_cards = State()
    selecting_partner_cards = State()
    confirming_trade = State()


# ====== Хранилище активных обменов в памяти ======
active_trades: Dict[int, Dict[str, Any]] = {}
user_pair_trades: Dict[tuple, int] = {}
trade_counter = 0


def generate_trade_id() -> int:
    global trade_counter
    trade_counter += 1
    return trade_counter


def get_trade_key(user1: int, user2: int) -> tuple:
    return tuple(sorted([user1, user2]))


async def create_trade(initiator_id: int, partner_id: int) -> Optional[int]:
    """Создать новый обмен между двумя пользователями."""
    if initiator_id == partner_id:
        return None
    
    trade_key = get_trade_key(initiator_id, partner_id)
    existing_trade_id = user_pair_trades.get(trade_key)
    
    if existing_trade_id and existing_trade_id in active_trades:
        existing_trade = active_trades[existing_trade_id]
        if existing_trade.get("status") == "active":
            return existing_trade_id
    
    trade_id = generate_trade_id()
    active_trades[trade_id] = {
        "initiator_id": initiator_id,
        "partner_id": partner_id,
        "status": "active",
        "created_at": datetime.utcnow(),
        "initiator_cards": [],
        "partner_cards": [],
        "selected_card_type": None,  # 'members' или 'skills'
    }
    user_pair_trades[trade_key] = trade_id
    
    logger.info(f"Создан обмен {trade_id} между {initiator_id} и {partner_id}")
    return trade_id


def get_active_trade_for_user(user_id: int) -> Optional[Dict[str, Any]]:
    """Получить активный обмен для пользователя."""
    for trade_id, trade in active_trades.items():
        if trade.get("status") == "active":
            if trade["initiator_id"] == user_id or trade["partner_id"] == user_id:
                return trade
    return None


def get_partner_id(trade: Dict[str, Any], user_id: int) -> Optional[int]:
    """Получить ID партнера по обмену."""
    if trade["initiator_id"] == user_id:
        return trade["partner_id"]
    elif trade["partner_id"] == user_id:
        return trade["initiator_id"]
    return None


# ====== Утилита для безопасного редактирования сообщений ======
async def safe_trade_edit(callback: CallbackQuery, text: str, reply_markup=None, parse_mode="HTML"):
    """Безопасное редактирование сообщения в торговом меню."""
    msg = callback.message
    
    try:
        if msg.content_type == "text":
            await msg.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
        elif msg.content_type in ("photo", "video", "document", "audio", "voice"):
            try:
                await msg.edit_caption(text, reply_markup=reply_markup, parse_mode=parse_mode)
            except TelegramBadRequest:
                await msg.delete()
                await callback.message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)
        else:
            await msg.delete()
            await callback.message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            logger.warning(f"Ошибка редактирования: {e}")
        await callback.message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)
    
    await callback.answer()


# ====== Клавиатуры для торговли ======
def get_trade_main_keyboard(partner_id: int) -> types.InlineKeyboardMarkup:
    """Главное меню обмена."""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        types.InlineKeyboardButton(
            text="📋 Карты партнера",
            callback_data=f"trade_show_partner:{partner_id}"
        )
    )
    builder.row(
        types.InlineKeyboardButton(
            text="🎁 Предложить свои карты",
            callback_data=f"trade_select_own:{partner_id}"
        )
    )
    builder.row(
        types.InlineKeyboardButton(
            text="✅ Принять обмен",
            callback_data=f"trade_accept:{partner_id}"
        ),
        types.InlineKeyboardButton(
            text="❌ Отклонить обмен",
            callback_data=f"trade_decline:{partner_id}"
        )
    )
    builder.row(
        types.InlineKeyboardButton(text="↪️ Назад", callback_data="go_back_menu")
    )
    
    return builder.as_markup()


def get_trade_main_keyboard_with_username(partner_id: int, partner_username: str) -> types.InlineKeyboardMarkup:
    """Главное меню обмена с username."""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        types.InlineKeyboardButton(
            text="📋 Карты партнера",
            callback_data=f"trade_show_partner:{partner_id}"
        )
    )
    builder.row(
        types.InlineKeyboardButton(
            text="🎁 Предложить свои карты",
            callback_data=f"trade_select_own:{partner_id}"
        )
    )
    builder.row(
        types.InlineKeyboardButton(
            text="✅ Принять обмен",
            callback_data=f"trade_accept:{partner_id}"
        ),
        types.InlineKeyboardButton(
            text="❌ Отклонить обмен",
            callback_data=f"trade_decline:{partner_id}"
        )
    )
    builder.row(
        types.InlineKeyboardButton(text="↪️ Назад", callback_data="main_trade")
    )
    
    return builder.as_markup()


def get_trade_request_keyboard(initiator_id: int) -> types.InlineKeyboardMarkup:
    """Клавиатура для принятия/отклонения запроса на обмен."""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        types.InlineKeyboardButton(
            text="✅ Принять обмен",
            callback_data=f"trade_accept_request:{initiator_id}"
        ),
        types.InlineKeyboardButton(
            text="❌ Отклонить обмен",
            callback_data=f"trade_decline_request:{initiator_id}"
        )
    )
    
    return builder.as_markup()


def get_trade_card_type_keyboard(partner_id: int) -> types.InlineKeyboardMarkup:
    """Выбор типа карт для обмена."""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        types.InlineKeyboardButton(text="👥 Участники", callback_data=f"trade_type_members:{partner_id}"),
        types.InlineKeyboardButton(text="🃏 Суперспособности", callback_data=f"trade_type_skills:{partner_id}")
    )
    builder.row(
        types.InlineKeyboardButton(text="↪️ Назад", callback_data=f"trade_menu:{partner_id}")
    )
    
    return builder.as_markup()


def get_trade_partner_cards_keyboard(partner_id: int, card_index: int, total: int, card_type: str) -> types.InlineKeyboardMarkup:
    """Навигация по картам партнера."""
    builder = InlineKeyboardBuilder()
    
    prev_index = (card_index - 1) % total
    next_index = (card_index + 1) % total
    
    builder.row(
        types.InlineKeyboardButton(text="⬅", callback_data=f"trade_partner_prev:{partner_id}:{card_index}:{prev_index}:{card_type}"),
        types.InlineKeyboardButton(text=f"{card_index + 1}/{total}", callback_data="noop"),
        types.InlineKeyboardButton(text="➡", callback_data=f"trade_partner_next:{partner_id}:{card_index}:{next_index}:{card_type}"),
    )
    
    builder.row(
        types.InlineKeyboardButton(
            text="🔄 Выбрать эту карту",
            callback_data=f"trade_select_partner_card:{partner_id}:{card_index}:{card_type}"
        )
    )
    
    builder.row(
        types.InlineKeyboardButton(text="↪️ Назад", callback_data=f"trade_menu:{partner_id}")
    )
    
    return builder.as_markup()


def get_trade_own_cards_keyboard(partner_id: int, card_index: int, total: int, card_type: str) -> types.InlineKeyboardMarkup:
    """Навигация по своим картам для выбора."""
    builder = InlineKeyboardBuilder()
    
    prev_index = (card_index - 1) % total
    next_index = (card_index + 1) % total
    
    builder.row(
        types.InlineKeyboardButton(text="⬅", callback_data=f"trade_own_prev:{partner_id}:{card_index}:{prev_index}:{card_type}"),
        types.InlineKeyboardButton(text=f"{card_index + 1}/{total}", callback_data="noop"),
        types.InlineKeyboardButton(text="➡", callback_data=f"trade_own_next:{partner_id}:{card_index}:{next_index}:{card_type}"),
    )
    
    builder.row(
        types.InlineKeyboardButton(
            text="🎁 Предложить эту карту",
            callback_data=f"trade_select_own_card:{partner_id}:{card_index}:{card_type}"
        )
    )
    
    builder.row(
        types.InlineKeyboardButton(text="↪️ Назад", callback_data=f"trade_menu:{partner_id}")
    )
    
    return builder.as_markup()


def get_trade_confirm_keyboard(partner_id: int) -> types.InlineKeyboardMarkup:
    """Подтверждение обмена."""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        types.InlineKeyboardButton(text="✅ Подтвердить обмен", callback_data=f"trade_confirm:{partner_id}"),
        types.InlineKeyboardButton(text="❌ Отмена", callback_data=f"trade_menu:{partner_id}")
    )
    
    return builder.as_markup()


def get_trade_cancel_keyboard(partner_id: int) -> types.InlineKeyboardMarkup:
    """Отмена обмена (когда нет карт)."""
    builder = InlineKeyboardBuilder()
    
    builder.row(
        types.InlineKeyboardButton(text="↪️ Назад", callback_data=f"trade_menu:{partner_id}")
    )
    
    return builder.as_markup()


# ====== Обработчики ======

@router.callback_query(F.data.startswith("start_trade:"))
async def start_trade_handler(callback: CallbackQuery, state: FSMContext):
    try:
        partner_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка: неверный ID партнера", show_alert=True)
        return
    
    user_id = callback.from_user.id
    
    if partner_id == user_id:
        await callback.answer("❌ Нельзя начать обмен с самим собой", show_alert=True)
        return
    
    trade_id = await create_trade(user_id, partner_id)
    if not trade_id:
        await callback.answer("❌ Не удалось создать обмен", show_alert=True)
        return
    
    await state.update_data(
        trade_id=trade_id,
        partner_id=partner_id,
        trade_mode=True
    )
    
    try:
        await callback.bot.send_message(
            chat_id=partner_id,
            text=f"🔄 <b>Вам предложили обмен!</b>\n\n"
                 f"Пользователь {callback.from_user.username or callback.from_user.first_name} "
                 f"хочет обменяться карточками.\n\n"
                 f"Используйте кнопки ниже для управления обменом.",
            reply_markup=get_trade_main_keyboard(user_id),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Не удалось отправить уведомление партнеру {partner_id}: {e}")
    
    await callback.message.edit_text(
        text=f"🔄 <b>Обмен создан!</b>\n\n"
             f"Партнер: <code>{partner_id}</code>\n\n"
             f"Вы можете:\n"
             f"• Посмотреть карты партнера\n"
             f"• Предложить свои карты\n"
             f"• Завершить или отменить обмен",
        reply_markup=get_trade_main_keyboard(partner_id),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("trade_show_partner:"))
async def show_partner_cards_handler(callback: CallbackQuery, state: FSMContext):
    """
    Просмотр карт партнера.
    
    ВАЖНО: Извлекаем partner_id из callback_data, а не используем callback.from_user.id
    """
    try:
        partner_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка: неверный ID партнера", show_alert=True)
        return
    
    user_id = callback.from_user.id
    
    state_data = await state.get_data()
    trade_id = state_data.get("trade_id")
    
    if not trade_id or trade_id not in active_trades:
        await callback.answer("❌ Обмен не найден или завершен", show_alert=True)
        return
    
    trade = active_trades[trade_id]
    if trade.get("status") != "active":
        await callback.answer("❌ Обмен уже завершен или отменен", show_alert=True)
        return
    
    if trade["initiator_id"] != user_id and trade["partner_id"] != user_id:
        await callback.answer("❌ Вы не участник этого обмена", show_alert=True)
        return
    
    await state.update_data(
        viewing_partner_cards=True,
        current_partner_id=partner_id,
        trade_mode=True
    )
    
    # === КЛЮЧЕВОЙ МОМЕНТ: получаем карты именно партнера, а не текущего пользователя ===
    partner_cards_dict = get_member_cards(partner_id)  # <-- partner_id, а не user_id!
    partner_card_names = [name for name in partner_cards_dict if not name.startswith("_")]
    
    if not partner_card_names:
        await callback.message.edit_text(
            text="📭 У партнера пока нет карточек участников.",
            reply_markup=get_trade_cancel_keyboard(partner_id)
        )
        await callback.answer()
        return
    
    await show_partner_card_page(callback, partner_id, partner_card_names, 0, partner_cards_dict)


async def show_partner_card_page(
    callback: CallbackQuery,
    partner_id: int,
    card_names: list,
    index: int,
    cards_dict: dict
):
    from handlers.cards_handler.cards_member import format_card_text, get_member_card_image_path
    
    try:
        with open("data/cards/members.json", "r", encoding="utf-8") as f:
            import json
            MEMBER_CARDS = json.load(f)
    except Exception as e:
        logger.error(f"Ошибка загрузки members.json: {e}")
        await callback.answer("❌ Ошибка загрузки данных карт", show_alert=True)
        return
    
    card_name = card_names[index]
    card_data = cards_dict[card_name]
    
    card_info = next(
        (c for c in MEMBER_CARDS if c["name"].strip().lower() == card_name.strip().lower()),
        None
    )
    
    if not card_info:
        await callback.answer("❌ Информация о карте не найдена", show_alert=True)
        return
    
    image_path = get_member_card_image_path(card_data, card_info)
    if not image_path:
        await callback.answer("❌ Изображение карты не найдено", show_alert=True)
        return
    
    work = card_info.get("work", "неизвестно")
    caption = format_card_text(card_name, card_data, card_info["rarity"], work, user_id=partner_id)
    caption = f"<b>Карта партнера:</b>\n\n{caption}"
    
    keyboard = get_trade_partner_cards_keyboard(partner_id, index, len(card_names), "members")
    
    photo = FSInputFile(image_path)
    
    try:
        await callback.message.edit_media(
            media=types.InputMediaPhoto(media=photo, caption=caption),
            reply_markup=keyboard
        )
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            logger.error(f"Ошибка при редактировании медиа: {e}")
            await callback.message.answer_photo(photo=photo, caption=caption, reply_markup=keyboard)
    
    await callback.answer()


@router.callback_query(F.data.startswith("trade_partner_prev:") | F.data.startswith("trade_partner_next:"))
async def navigate_partner_cards_handler(callback: CallbackQuery, state: FSMContext):
    try:
        parts = callback.data.split(":")
        partner_id = int(parts[1])
        index = int(parts[2])
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка навигации", show_alert=True)
        return
    
    state_data = await state.get_data()
    cards_dict = get_member_cards(partner_id)
    card_names = [name for name in cards_dict if not name.startswith("_")]
    
    if not card_names:
        await callback.answer("У партнера нет карт", show_alert=True)
        return
    
    index %= len(card_names)
    await show_partner_card_page(callback, partner_id, card_names, index, cards_dict)


@router.callback_query(F.data.startswith("trade_menu:"))
async def back_to_trade_menu_handler(callback: CallbackQuery, state: FSMContext):
    try:
        partner_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка", show_alert=True)
        return
    
    await state.update_data(viewing_partner_cards=False)
    
    await callback.message.edit_text(
        text="🔄 <b>Меню обмена</b>\n\nВыберите действие:",
        reply_markup=get_trade_main_keyboard(partner_id),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("trade_cancel:"))
async def cancel_trade_handler(callback: CallbackQuery, state: FSMContext):
    try:
        partner_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка", show_alert=True)
        return
    
    user_id = callback.from_user.id
    trade = get_active_trade_for_user(user_id)
    
    if trade:
        trade_id = None
        for tid, t in active_trades.items():
            if t is trade:
                trade_id = tid
                break
        
        if trade_id:
            trade["status"] = "cancelled"
            trade_key = get_trade_key(user_id, partner_id)
            user_pair_trades.pop(trade_key, None)
            
            try:
                await callback.bot.send_message(
                    chat_id=partner_id,
                    text=f"❌ Обмен отменен пользователем {callback.from_user.username or callback.from_user.first_name}"
                )
            except Exception:
                pass
            
            await state.clear()
    
    await callback.message.edit_text(
        text="❌ Обмен отменен.",
        reply_markup=None
    )
    await callback.answer("Обмен отменен")


@router.callback_query(F.data.startswith("trade_finish:"))
async def finish_trade_handler(callback: CallbackQuery, state: FSMContext):
    try:
        partner_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка", show_alert=True)
        return
    
    user_id = callback.from_user.id
    trade = get_active_trade_for_user(user_id)
    
    if not trade:
        await callback.answer("❌ Активный обмен не найден", show_alert=True)
        return
    
    trade["status"] = "completed"
    trade_key = get_trade_key(user_id, partner_id)
    user_pair_trades.pop(trade_key, None)
    
    await state.clear()
    
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="↪️ Назад", callback_data="main_trade")
    )
    
    await callback.message.edit_text(
        text="✅ Обмен успешно завершен!",
        reply_markup=builder.as_markup()
    )
    await callback.answer("Обмен завершен")


@router.callback_query(F.data.startswith("trade_select_own:"))
async def select_own_cards_handler(callback: CallbackQuery, state: FSMContext):
    """Выбор своих карт для предложения."""
    try:
        partner_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка: неверный ID партнера", show_alert=True)
        return
    
    user_id = callback.from_user.id
    
    state_data = await state.get_data()
    trade_id = state_data.get("trade_id")
    
    if not trade_id or trade_id not in active_trades:
        await callback.answer("❌ Обмен не найден или завершен", show_alert=True)
        return
    
    trade = active_trades[trade_id]
    if trade.get("status") != "active":
        await callback.answer("❌ Обмен уже завершен или отменен", show_alert=True)
        return
    
    await state.update_data(selecting_own_cards=True, current_partner_id=partner_id)
    
    # Сначала показываем выбор типа карт
    await callback.message.edit_text(
        text="🃏 <b>Выберите тип карт для предложения:</b>",
        reply_markup=get_trade_card_type_keyboard(partner_id),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("trade_type_members:") | F.data.startswith("trade_type_skills:"))
async def select_card_type_handler(callback: CallbackQuery, state: FSMContext):
    """Выбор типа карт (участники или суперспособности)."""
    try:
        parts = callback.data.split(":")
        card_type = "members" if "members" in callback.data else "skills"
        partner_id = int(parts[1])
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка", show_alert=True)
        return
    
    user_id = callback.from_user.id
    state_data = await state.get_data()
    
    await state.update_data(selected_card_type=card_type)
    
    # Получаем карты пользователя
    if card_type == "members":
        cards_dict = get_member_cards(user_id)
    else:
        cards_dict = get_skill_cards(user_id)
    
    card_names = [name for name in cards_dict if not name.startswith("_")]
    
    if not card_names:
        card_type_name = "участников" if card_type == "members" else "суперспособностей"
        await callback.message.edit_text(
            text=f"📭 У вас нет карт {card_type_name}.",
            reply_markup=get_trade_cancel_keyboard(partner_id)
        )
        await callback.answer()
        return
    
    # Показываем первую карту
    if card_type == "members":
        await show_own_card_page(callback, partner_id, card_names, 0, cards_dict, card_type)
    else:
        await show_own_skill_card_page(callback, partner_id, card_names, 0, cards_dict, card_type)


async def show_own_card_page(
    callback: CallbackQuery,
    partner_id: int,
    card_names: list,
    index: int,
    cards_dict: dict,
    card_type: str
):
    """Показать страницу со своей картой участника."""
    from handlers.cards_handler.cards_member import format_card_text, get_member_card_image_path
    
    try:
        with open("data/cards/members.json", "r", encoding="utf-8") as f:
            MEMBER_CARDS = json.load(f)
    except Exception as e:
        logger.error(f"Ошибка загрузки members.json: {e}")
        await callback.answer("❌ Ошибка загрузки данных карт", show_alert=True)
        return
    
    card_name = card_names[index]
    card_data = cards_dict[card_name]
    
    card_info = next(
        (c for c in MEMBER_CARDS if c["name"].strip().lower() == card_name.strip().lower()),
        None
    )
    
    if not card_info:
        await callback.answer("❌ Информация о карте не найдена", show_alert=True)
        return
    
    image_path = get_member_card_image_path(card_data, card_info)
    if not image_path:
        await callback.answer("❌ Изображение карты не найдено", show_alert=True)
        return
    
    work = card_info.get("work", "неизвестно")
    caption = format_card_text(card_name, card_data, card_info["rarity"], work, user_id=callback.from_user.id)
    caption = f"<b>Ваша карта:</b>\\n\\n{caption}"
    
    keyboard = get_trade_own_cards_keyboard(partner_id, index, len(card_names), card_type)
    
    photo = FSInputFile(image_path)
    
    try:
        await callback.message.edit_media(
            media=types.InputMediaPhoto(media=photo, caption=caption),
            reply_markup=keyboard
        )
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            logger.error(f"Ошибка при редактировании медиа: {e}")
            await callback.message.answer_photo(photo=photo, caption=caption, reply_markup=keyboard)
    
    await callback.answer()


async def show_own_skill_card_page(
    callback: CallbackQuery,
    partner_id: int,
    card_names: list,
    index: int,
    cards_dict: dict,
    card_type: str
):
    """Показать страницу со своей картой суперспособности."""
    try:
        with open("data/cards/skills.json", "r", encoding="utf-8") as f:
            SKILL_CARDS = json.load(f)
    except Exception as e:
        logger.error(f"Ошибка загрузки skills.json: {e}")
        await callback.answer("❌ Ошибка загрузки данных карт", show_alert=True)
        return
    
    card_name = card_names[index]
    card_data = cards_dict[card_name]
    
    card_info = next(
        (c for c in SKILL_CARDS if c["name"].strip().lower() == card_name.strip().lower()),
        None
    )
    
    if not card_info:
        await callback.answer("❌ Информация о карте не найдена", show_alert=True)
        return
    
    rarity = card_info.get("rarity", "common")
    description = card_info.get("description", "")
    
    caption = f"<b>Суперспособность:</b>\\n\\n"
    caption += f"🎴 <b>{card_name}</b>\\n"
    caption += f"Редкость: {rarity}\\n"
    if description:
        caption += f"\\n{description}"
    
    keyboard = get_trade_own_cards_keyboard(partner_id, index, len(card_names), card_type)
    
    # Для навыков пока без изображения
    try:
        await callback.message.edit_text(
            text=caption,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            logger.error(f"Ошибка при редактировании: {e}")
            await callback.message.answer(text=caption, reply_markup=keyboard, parse_mode="HTML")
    
    await callback.answer()


@router.callback_query(F.data.startswith("trade_own_prev:") | F.data.startswith("trade_own_next:"))
async def navigate_own_cards_handler(callback: CallbackQuery, state: FSMContext):
    """Навигация по своим картам."""
    try:
        parts = callback.data.split(":")
        partner_id = int(parts[1])
        new_index = int(parts[3])
        card_type = parts[4] if len(parts) > 4 else "members"
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка навигации", show_alert=True)
        return
    
    user_id = callback.from_user.id
    state_data = await state.get_data()
    selected_card_type = state_data.get("selected_card_type", card_type)
    
    if selected_card_type == "members":
        cards_dict = get_member_cards(user_id)
    else:
        cards_dict = get_skill_cards(user_id)
    
    card_names = [name for name in cards_dict if not name.startswith("_")]
    
    if not card_names:
        await callback.answer("У вас нет карт", show_alert=True)
        return
    
    new_index %= len(card_names)
    
    if selected_card_type == "members":
        await show_own_card_page(callback, partner_id, card_names, new_index, cards_dict, selected_card_type)
    else:
        await show_own_skill_card_page(callback, partner_id, card_names, new_index, cards_dict, selected_card_type)


@router.callback_query(F.data.startswith("trade_select_own_card:"))
async def select_own_card_for_trade_handler(callback: CallbackQuery, state: FSMContext):
    """Выбор своей карты для обмена."""
    try:
        parts = callback.data.split(":")
        partner_id = int(parts[1])
        card_index = int(parts[2])
        card_type = parts[3] if len(parts) > 3 else "members"
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка", show_alert=True)
        return
    
    user_id = callback.from_user.id
    
    if card_type == "members":
        cards_dict = get_member_cards(user_id)
    else:
        cards_dict = get_skill_cards(user_id)
    
    card_names = [name for name in cards_dict if not name.startswith("_")]
    
    if card_index >= len(card_names):
        await callback.answer("❌ Карта не найдена", show_alert=True)
        return
    
    card_name = card_names[card_index]
    
    # Сохраняем выбранную карту в состоянии
    await state.update_data(own_selected_card=card_name, own_card_type=card_type)
    
    await callback.answer(f"✅ Карта '{card_name}' выбрана для обмена")
    
    # Возвращаемся к главному меню обмена
    await callback.message.edit_text(
        text=f"🔄 <b>Меню обмена</b>\\n\\n"
             f"Вы выбрали карту: <b>{card_name}</b>\\n\\n"
             f"Теперь выберите карту партнера или подтвердите обмен.",
        reply_markup=get_trade_main_keyboard(partner_id),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("trade_accept:"))
async def accept_trade_handler(callback: CallbackQuery, state: FSMContext):
    """Принять обмен."""
    try:
        partner_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка", show_alert=True)
        return
    
    user_id = callback.from_user.id
    trade = get_active_trade_for_user(user_id)
    
    if not trade:
        await callback.answer("❌ Активный обмен не найден", show_alert=True)
        return
    
    # Проверяем, есть ли выбранные карты
    state_data = await state.get_data()
    own_card = state_data.get("own_selected_card")
    
    if not own_card:
        await callback.answer("⚠️ Сначала выберите карту для обмена", show_alert=True)
        return
    
    # Показываем подтверждение
    await callback.message.edit_text(
        text=f"✅ <b>Подтверждение обмена</b>\\n\\n"
             f"Вы предлагаете: <b>{own_card}</b>\\n\\n"
             f"Партнер: <code>{partner_id}</code>\\n\\n"
             f"Подтвердите обмен:",
        reply_markup=get_trade_confirm_keyboard(partner_id),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("trade_confirm:"))
async def confirm_trade_handler(callback: CallbackQuery, state: FSMContext):
    """Подтвердить и завершить обмен."""
    try:
        partner_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка", show_alert=True)
        return
    
    user_id = callback.from_user.id
    trade = get_active_trade_for_user(user_id)
    
    if not trade:
        await callback.answer("❌ Активный обмен не найден", show_alert=True)
        return
    
    state_data = await state.get_data()
    own_card = state_data.get("own_selected_card")
    own_card_type = state_data.get("own_card_type", "members")
    
    if not own_card:
        await callback.answer("⚠️ Карта не выбрана", show_alert=True)
        return
    
    # Здесь должна быть логика реального обмена картами между пользователями
    # Для примера просто завершаем обмен
    trade["status"] = "completed"
    trade_key = get_trade_key(user_id, partner_id)
    user_pair_trades.pop(trade_key, None)
    
    # TODO: Реализовать передачу карт между пользователями
    logger.info(f"Обмен завершен: {user_id} отдал {own_card} ({own_card_type}) пользователю {partner_id}")
    
    await state.clear()
    
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="↪️ Назад в меню", callback_data="go_back_menu")
    )
    
    await callback.message.edit_text(
        text=f"✅ <b>Обмен успешно завершен!</b>\\n\\n"
             f"Вы отдали: <b>{own_card}</b>\\n"
             f"Получатель: <code>{partner_id}</code>\\n\\n"
             f"Карты будут обновлены в ближайшее время.",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer("Обмен завершен!")


@router.callback_query(F.data.startswith("trade_decline:"))
async def decline_trade_handler(callback: CallbackQuery, state: FSMContext):
    """Отклонить обмен."""
    try:
        partner_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка", show_alert=True)
        return
    
    user_id = callback.from_user.id
    trade = get_active_trade_for_user(user_id)
    
    if trade:
        trade["status"] = "declined"
        trade_key = get_trade_key(user_id, partner_id)
        user_pair_trades.pop(trade_key, None)
        
        try:
            await callback.bot.send_message(
                chat_id=partner_id,
                text=f"❌ Пользователь {callback.from_user.username or callback.from_user.first_name} отклонил обмен."
            )
        except Exception:
            pass
        
        await state.clear()
    
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="↪️ Назад", callback_data="go_back_menu")
    )
    
    await callback.message.edit_text(
        text="❌ Обмен отклонен.",
        reply_markup=builder.as_markup()
    )
    await callback.answer("Обмен отклонен")


@router.callback_query(F.data.startswith("trade_accept_request:"))
async def accept_trade_request_handler(callback: CallbackQuery, state: FSMContext):
    """Принять запрос на обмен от инициатора."""
    try:
        initiator_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка", show_alert=True)
        return
    
    user_id = callback.from_user.id
    
    # Создаем обмен (если еще не создан)
    trade_id = await create_trade(initiator_id, user_id)
    if not trade_id:
        await callback.answer("❌ Не удалось создать обмен", show_alert=True)
        return
    
    await state.update_data(
        trade_id=trade_id,
        partner_id=initiator_id,
        trade_mode=True
    )
    
    # Получаем username инициатора
    conn = connect()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM users WHERE user_id = ?", (initiator_id,))
    user_row = cursor.fetchone()
    conn.close()
    
    initiator_username = user_row["username"] if user_row else "неизвестно"
    
    await callback.message.edit_text(
        text=f"✅ <b>Обмен принят!</b>\n\n"
             f"Партнер: @{initiator_username}\n\n"
             f"Теперь вы можете:\n"
             f"• Посмотреть карты партнера\n"
             f"• Предложить свои карты\n"
             f"• Отклонить обмен",
        reply_markup=get_trade_main_keyboard(initiator_id),
        parse_mode="HTML"
    )
    
    # Уведомляем инициатора
    try:
        await callback.bot.send_message(
            chat_id=initiator_id,
            text=f"✅ Пользователь принял ваш запрос на обмен!"
        )
    except Exception:
        pass
    
    await callback.answer("Обмен принят!")


@router.callback_query(F.data.startswith("trade_decline_request:"))
async def decline_trade_request_handler(callback: CallbackQuery, state: FSMContext):
    """Отклонить запрос на обмен от инициатора."""
    try:
        initiator_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка", show_alert=True)
        return
    
    # Уведомляем инициатора
    try:
        await callback.bot.send_message(
            chat_id=initiator_id,
            text=f"❌ Пользователь отклонил ваш запрос на обмен."
        )
    except Exception:
        pass
    
    await callback.message.edit_text(
        text="❌ Обмен отклонен.",
        reply_markup=None
    )
    await callback.answer("Обмен отклонен")


@router.callback_query(F.data == "main_trade")
async def back_to_trade_from_menu(callback: CallbackQuery, state: FSMContext):
    """Возврат в меню обмена из других разделов."""
    from handlers.menu import safe_edit_or_replace
    
    user_id = callback.from_user.id
    trade = get_active_trade_for_user(user_id)
    
    if trade and trade.get("status") == "active":
        partner_id = get_partner_id(trade, user_id)
        if partner_id:
            await safe_edit_or_replace(
                callback,
                "🔄 <b>Меню обмена</b>\n\nВыберите действие:",
                reply_markup=get_trade_main_keyboard(partner_id),
                parse_mode="HTML"
            )
            return
    
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="➕ Создать обмен", callback_data="trade_create_new")
    )
    builder.row(
        types.InlineKeyboardButton(text="↪️ Назад", callback_data="go_back_menu")
    )
    
    await safe_edit_or_replace(
        callback,
        "🔄 <b>Обмен карточками</b>\n\n"
        "У вас нет активного обмена.\n\n"
        "Вы можете:\n"
        "• Создать новый обмен с пользователем\n"
        "• Принять входящий обмен",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )


__all__ = [
    "TradeState",
    "router",
    "create_trade",
    "get_active_trade_for_user",
    "get_trade_main_keyboard",
    "get_trade_main_keyboard_with_username",
    "get_trade_request_keyboard",
    "get_partner_id",
]
