import os
import json
import logging

from aiogram import Router, F, types
from aiogram.types import CallbackQuery, FSInputFile, Message, InputMediaPhoto
from aiogram.exceptions import TelegramBadRequest

from database.db import get_skill_cards, get_user_timezone
from ..keyboard import get_skill_card_navigation_keyboard, get_back_menu_colletion_button, get_card_skill_ui
from ..picture import find_image_file
from utils.helpers import format_iso_utc_to_user_tz

router = Router()

# Pricing for selling skill cards (rarity base prices)
RARITY_PRICES_SKILL = {
    "Обычная": 1,
    "Редкая": 3,
    "Эпическая": 6,
    "Легендарная": 10,
}

# Reuse member rank multipliers for uniformity (skill cards usually rank 1)
RANK_MULTIPLIERS = {1: 1.0, 2: 2.2, 3: 3.3, 4: 4.4}

def load_skill_catalog():
    """Load skill cards catalog from disk each time so changes are picked up without restart."""
    try:
        with open("data/cards/skills.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        logging.exception("Не удалось загрузить data/cards/skills.json")
        return []

def format_card_text(card_name: str, card_data: dict, rarity: str, user_id: int | None = None) -> str:
    base = (
        f"<b>{card_name}</b>\n"
        f"⭐ Редкость: <i>{rarity}</i>\n"
    )
    received_at = card_data.get("received_at") if isinstance(card_data, dict) else None
    if received_at:
        user_tz = None
        try:
            if user_id:
                user_tz = get_user_timezone(user_id)
        except Exception:
            user_tz = None
        date_str = format_iso_utc_to_user_tz(received_at, user_tz)
        try:
            rank_val = int(card_data.get("rank", 1)) if isinstance(card_data, dict) else 1
        except Exception:
            rank_val = 1
        base_price = RARITY_PRICES_SKILL.get(rarity, 1)
        multiplier = RANK_MULTIPLIERS.get(rank_val, 1.0)
        sell_amount = int(round(base_price * multiplier))
        return base + f"\nДата получения: <b>{date_str}</b>" + f"\n\nПри продаже вы получите: <b>{sell_amount} 🔥</b>"

    # calculate sell amount (skill cards typically have rank 1, but card_data may include rank)
    try:
        rank_val = int(card_data.get("rank", 1)) if isinstance(card_data, dict) else 1
    except Exception:
        rank_val = 1

    base_price = RARITY_PRICES_SKILL.get(rarity, 1)
    multiplier = RANK_MULTIPLIERS.get(rank_val, 1.0)
    sell_amount = int(round(base_price * multiplier))

    return base + f"\nДата получения: <b>неизвестна (до обновления)</b>" + f"\n\nПри продаже вы получите: <b>{sell_amount} 🔥</b>"

async def show_my_cards(event: CallbackQuery | Message):
    user_id = event.from_user.id
    user_cards = get_skill_cards(user_id)
    owned_card_names = [name for name in user_cards if not name.startswith("_")]

    if not owned_card_names:
        message = "У тебя пока нет карточек 🙁"
        await event.message.edit_text(message, reply_markup=get_back_menu_colletion_button())
        return

    index = 0
    await send_card(event, index, user_cards, owned_card_names)

async def send_card(event: CallbackQuery | Message, index: int, user_cards: dict, owned_card_names: list[str]):
    card_name = owned_card_names[index]
    card_data = user_cards[card_name]
    card_info = next((c for c in load_skill_catalog() if c["name"] == card_name), None)

    if not card_info:
        return await event.message.answer("Ошибка: карточка не найдена.")

    image_name = card_info["image"].split(".")[0]
    image_path = find_image_file(image_name, "data/images/skills")
    if not image_path or not os.path.exists(image_path):
        return await event.message.answer("Ошибка: изображение карточки не найдено.")

    # format caption using the requesting user's timezone
    caption = format_card_text(card_name, card_data, card_info["rarity"], user_id=event.from_user.id if hasattr(event, 'from_user') else None)
    keyboard = get_skill_card_navigation_keyboard(index, len(owned_card_names), prefix="my_skill_cards", card_name=card_name)
    photo = FSInputFile(image_path)

    if isinstance(event, CallbackQuery):
        try:
            from utils.helpers import safe_delete
            await safe_delete(event)
        except Exception:
            pass

        # try to send photo; fallback on IMAGE_PROCESS_FAILED
        try:
            await event.message.answer_photo(photo=photo, caption=caption, reply_markup=keyboard)
        except TelegramBadRequest as e:
            # If Telegram fails to process image, try sending as document or fallback to text
            msg = str(e)
            if "IMAGE_PROCESS_FAILED" in msg or "image process failed" in msg.lower():
                try:
                    await event.message.answer_document(document=photo, caption=caption, reply_markup=keyboard)
                except Exception:
                    # last resort: send text with keyboard
                    await event.message.answer(text=caption, reply_markup=keyboard)
            else:
                raise
        await event.answer()
    else:
        try:
            from utils.helpers import safe_delete
            await safe_delete(event)
        except Exception:
            pass

        try:
            await event.answer_photo(photo=photo, caption=caption, reply_markup=keyboard)
        except TelegramBadRequest as e:
            msg = str(e)
            if "IMAGE_PROCESS_FAILED" in msg or "image process failed" in msg.lower():
                try:
                    await event.answer_document(document=photo, caption=caption, reply_markup=keyboard)
                except Exception:
                    await event.bot.send_message(chat_id=event.chat.id, text=caption, reply_markup=keyboard)
            else:
                raise

async def navigate_my_skill_cards(event: CallbackQuery):
    user_id = event.from_user.id
    user_cards = get_skill_cards(user_id)
    owned_card_names = [name for name in user_cards if not name.startswith("_")]

    if not owned_card_names:
        message = "У тебя пока нет карточек 🙁"
        await event.message.edit_text(message, reply_markup=get_back_menu_colletion_button())
        return

    try:
        index = int(event.data.split(":")[1]) % len(owned_card_names)
    except (ValueError, IndexError):
        index = 0

    card_name = owned_card_names[index]
    card_data = user_cards[card_name]
    card_info = next((c for c in load_skill_catalog() if c["name"] == card_name), None)

    if not card_info:
        return await event.message.answer("Ошибка: карточка не найдена.")

    image_name = card_info["image"].split(".")[0]
    image_path = find_image_file(image_name, "data/images/skills")
    if not image_path or not os.path.exists(image_path):
        return await event.message.answer("Ошибка: изображение карточки не найдено.")

    caption = format_card_text(card_name, card_data, card_info["rarity"])
    keyboard = get_skill_card_navigation_keyboard(index, len(owned_card_names), prefix="my_skill_cards", card_name=card_name)
    photo = FSInputFile(image_path)

    try:
        await event.message.edit_media(
            media=InputMediaPhoto(media=photo, caption=caption, parse_mode="HTML"),
            reply_markup=keyboard
        )
    except TelegramBadRequest as e:
        error_msg = str(e)
        if "message is not modified" in error_msg or "canceled by new editMessageMedia request" in error_msg or "message to edit not found" in error_msg:
            pass  # Ignore these common race condition errors
        else:
            raise
    await event.answer()

async def sell_skill_card(event: CallbackQuery | Message):
    user_id = event.from_user.id
    user_cards = get_skill_cards(user_id)
    owned_card_names = [name for name in user_cards if not name.startswith("_")]

    if not owned_card_names:
        msg = "У тебя нет карточек"
        if isinstance(event, CallbackQuery):
            await event.answer(msg, show_alert=True)
        else:
            await event.answer(msg)
        return

    # determine which card to sell: if CallbackQuery and contains index, use it; otherwise default to 0
    index = 0
    if isinstance(event, CallbackQuery) and event.data and event.data.startswith("sell_skill_card:"):
        try:
            index = int(event.data.split(":")[1]) % len(owned_card_names)
        except Exception:
            index = 0

    card_name = owned_card_names[index]
    card_data = user_cards[card_name]

    card_info = next((c for c in load_skill_catalog() if c["name"].strip().lower() == card_name.strip().lower()), None)
    if not card_info:
        msg = "❌ Ошибка: карточка не найдена."
        if isinstance(event, CallbackQuery):
            await event.message.answer(msg)
            await event.answer()
        else:
            await event.answer(msg)
        return

    try:
        # Стоимости по редкости (пользователь указал: обычная 1 🔥, легендарная 10 🔥)
        # Для промежуточных редкостей поставлены разумные значения; при необходимости их можно скорректировать.
        rarity = card_info.get("rarity", "Обычная")
        rarity_prices = {
            "Обычная": 1,
            "Редкая": 5,
            "Эпическая": 8,
            "Легендарная": 10
        }
        amount = int(rarity_prices.get(rarity, 1))

        # Удаляем карту из коллекции пользователя
        del user_cards[card_name]

        # Обновляем БД и баланс
        from database.db import update_skill_cards, add_balance
        update_skill_cards(user_id, user_cards)
        new_balance = add_balance(user_id, amount)

        # Уведомляем пользователя
        text = f"✅ Суперспособность '{card_name}' продана за {amount} 🔥.\n Твой новый баланс: {new_balance} 🔥"
        try:
            # Prefer editing the existing message. If the message is a media message
            # Telegram may return 'there is no text in the message to edit'. In that
            # case delete the old message and send a fresh text message with keyboard.
            await event.message.edit_text(text, reply_markup=get_card_skill_ui())
        except TelegramBadRequest as e:
            msg = str(e)
            if "there is no text in the message to edit" in msg:
                try:
                    from utils.helpers import safe_delete
                    await safe_delete(event)
                except Exception:
                    pass
                await event.message.answer(text, reply_markup=get_card_skill_ui())
            else:
                raise
    except Exception:
        logging.exception("Ошибка при продаже суперспособности")
        if isinstance(event, CallbackQuery):
            await event.message.answer("❌ Ошибка при продаже карты. Попробуйте позже.")
            await event.answer()
        else:
            await event.answer("❌ Ошибка при продаже карты. Попробуйте позже.")



# 📥 Обработка кнопки
@router.callback_query(F.data.startswith("sell_skill_card"))
async def handle_draw_member_button(callback: CallbackQuery):
    await sell_skill_card(callback)

# Обработка кнопки "📦 Мои суперспособности"
@router.callback_query(F.data == "my_skill_cards")
async def handle_my_skill_cards_button(callback: CallbackQuery):
    await show_my_cards(callback)

# Обработка команды
@router.message(F.text == "📦 Мои суперспособности")
async def handle_my_skill_cards_command(message: Message):
    await show_my_cards(message)

# Обработка навигации
@router.callback_query(F.data.startswith("my_skill_cards:"))
async def handle_card_navigation(callback: CallbackQuery):
    await navigate_my_skill_cards(callback)
