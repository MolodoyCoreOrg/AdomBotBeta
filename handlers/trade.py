"""
Модуль системы обмена карточками между пользователями.
Реализует:
- Создание заявки на обмен
- Просмотр карт партнера (исправлена ошибка с user_id)
- Выбор карт для обмена
- Подтверждение обмена
- Отмену обмена
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any

from aiogram import Router, F, types
from aiogram.types import CallbackQuery, Message, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramBadRequest
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.db import get_member_cards, get_skill_cards, update_member_cards, update_skill_cards

logger = logging.getLogger(__name__)

router = Router()


# ====== FSM States ======
class TradeState(StatesGroup):
    waiting_for_partner = State()
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
        "viewing_user": None,
    }
    user_pair_trades[trade_key] = trade_id
    
    logger.info(f"Создан обмен {trade_id} между {initiator_id} и {partner_id}")
    return trade_id


def get_active_trade_for_user(user_id: int) -> Optional[Dict[str, Any]]:
    for trade_id, trade in active_trades.items():
        if trade.get("status") == "active":
            if trade["initiator_id"] == user_id or trade["partner_id"] == user_id:
                return trade
    return None


def get_partner_id(trade: Dict[str, Any], user_id: int) -> Optional[int]:
    if trade["initiator_id"] == user_id:
        return trade["partner_id"]
    elif trade["partner_id"] == user_id:
        return trade["initiator_id"]
    return None


# ====== Клавиатуры для торговли ======
def get_trade_main_keyboard(partner_id: int) -> types.InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    # ВАЖНО: передаем именно partner_id, а не свой!
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
            text="✅ Завершить обмен",
            callback_data=f"trade_finish:{partner_id}"
        )
    )
    builder.row(
        types.InlineKeyboardButton(
            text="❌ Отменить обмен",
            callback_data=f"trade_cancel:{partner_id}"
        )
    )
    
    return builder.as_markup()


def get_trade_partner_cards_keyboard(partner_id: int, card_index: int, total: int) -> types.InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    prev_index = (card_index - 1) % total
    next_index = (card_index + 1) % total
    
    builder.row(
        types.InlineKeyboardButton(text="⬅", callback_data=f"trade_partner_prev:{partner_id}:{prev_index}"),
        types.InlineKeyboardButton(text=f"{card_index + 1}/{total}", callback_data="noop"),
        types.InlineKeyboardButton(text="➡", callback_data=f"trade_partner_next:{partner_id}:{next_index}"),
    )
    
    builder.row(
        types.InlineKeyboardButton(
            text="🔄 Выбрать для обмена",
            callback_data=f"trade_select_partner_card:{partner_id}:{card_index}"
        )
    )
    
    builder.row(
        types.InlineKeyboardButton(text="↩️ Назад к обмену", callback_data=f"trade_menu:{partner_id}")
    )
    
    return builder.as_markup()


def get_trade_cancel_keyboard(partner_id: int) -> types.InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="↩️ Назад к обмену", callback_data=f"trade_menu:{partner_id}")
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
    
    keyboard = get_trade_partner_cards_keyboard(partner_id, index, len(card_names))
    
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
    
    await callback.message.edit_text(
        text="✅ Обмен успешно завершен!",
        reply_markup=None
    )
    await callback.answer("Обмен завершен")


__all__ = [
    "TradeState",
    "router",
    "create_trade",
    "get_active_trade_for_user",
]
