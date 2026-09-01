import os
import json
import logging
import html

from aiogram import Router, F, types
from aiogram.types import CallbackQuery, FSInputFile, Message
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest

from database.db import get_member_cards, get_user_timezone, connect, update_member_cards, add_balance
from ..keyboard import (
    get_member_card_navigation_keyboard,
    get_card_member_ui,
    get_back_menu_colletion_button,
    get_collection_list_keyboard,
)
from ..picture import find_image_file
from utils.helpers import (
    get_member_card_image_path,
    format_iso_utc_to_user_tz,
    safe_delete,
    safe_edit_message,
)

router = Router()

MEMBER_IMG_PATH = "data/images/members"

# Pricing for selling member cards
RARITY_PRICES_MEMBER = {
    "Обычная": 5,
    "Редкая": 10,
    "Эпическая": 20,
    "Легендарная": 50,
}

# Upgrade costs for member cards by rarity
UPGRADE_COSTS_MEMBER = {
    "Обычная": 50,
    "Редкая": 100,
    "Эпическая": 200,
    "Легендарная": 500,
}

# Rank multipliers used when calculating sell price (rank 1..4)
RANK_MULTIPLIERS = {1: 1.0, 2: 2.2, 3: 3.3, 4: 4.4}

RARITY_ORDER = {
    "Обычная": 1,
    "Редкая": 2,
    "Эпическая": 3,
    "Легендарная": 4,
}
RARITY_ICONS = {
    "Обычная": "⚪️",
    "Редкая": "🔵",
    "Эпическая": "🟣",
    "Легендарная": "🟡",
}
LIST_PAGE_SIZE = 20
SORT_LABELS = {
    "original": "без сортировки",
    "rarity_desc": "редкие сначала",
    "rarity_asc": "обычные сначала",
}

# Загружаем карточки участников из JSON
with open("data/cards/members.json", "r", encoding="utf-8") as f:
    MEMBER_CARDS = json.load(f)


def find_member_card(card_name: str) -> dict | None:
    normalized_name = card_name.strip().casefold()
    return next(
        (
            card
            for card in MEMBER_CARDS
            if str(card.get("name", "")).strip().casefold() == normalized_name
        ),
        None,
    )


def get_owned_member_card_names(user_cards: dict, sort_mode: str = "original") -> list[str]:
    names = [name for name in user_cards if not name.startswith("_")]
    if sort_mode not in {"rarity_desc", "rarity_asc"}:
        return names

    def sort_key(card_name: str):
        card_info = find_member_card(card_name) or {}
        rarity = card_info.get("rarity", "")
        rarity_value = RARITY_ORDER.get(rarity)
        unknown_rarity = rarity_value is None
        if rarity_value is None:
            rarity_value = 0
        direction_value = -rarity_value if sort_mode == "rarity_desc" else rarity_value
        return unknown_rarity, direction_value, card_name.casefold()

    return sorted(names, key=sort_key)


def parse_collection_list_callback(data: str) -> tuple[str, int]:
    parts = data.split(":")
    sort_mode = parts[1] if len(parts) > 1 else "original"
    if sort_mode not in SORT_LABELS:
        sort_mode = "original"
    try:
        page = max(0, int(parts[2]))
    except (IndexError, ValueError):
        page = 0
    return sort_mode, page


def format_member_list_line(
    position: int,
    card_name: str,
    card_data,
    card_info: dict | None,
) -> str:
    card_info = card_info or {}
    rarity = str(card_info.get("rarity", "Неизвестная"))
    icon = RARITY_ICONS.get(rarity, "❔")

    rank = 1
    count = 1
    if isinstance(card_data, dict):
        rank = card_data.get("rank", 1)
        count = card_data.get("count", 1)
    elif isinstance(card_data, int):
        count = card_data

    try:
        rank = max(1, int(rank))
    except (TypeError, ValueError):
        rank = 1
    try:
        count = max(1, int(count))
    except (TypeError, ValueError):
        count = 1

    count_text = f" · ×{count}" if count > 1 else ""
    return (
        f"{position}. {icon} <b>{html.escape(str(card_name))}</b> — "
        f"{html.escape(rarity)} · ранг {rank}{count_text}"
    )


def format_card_text(card_name: str, card_data: dict, rarity: str, work: str, user_id: int | None = None) -> str:
    rank = card_data.get("rank", 1)
    if rank == 1:
        skills_text = "\n\n<b>Навык: Появится при достижении 2 ранга.</b>\n"
    else:
        # Экранируем каждый навык перед формированием текста
        skills = "\n".join(f"— {html.escape(skill)}" for skill in card_data.get("skills", []))
        skills_text = f"\n\n<b>Навык:</b>\n{skills}" if skills else ""

    # Экранируем специальные символы в названиях и текстах для HTML
    safe_card_name = html.escape(card_name)
    safe_work = html.escape(work)
    safe_rarity = html.escape(rarity)

    base = (
        f"<b>{safe_card_name}</b>\n"
        f"⭐ Редкость: <i>{safe_rarity}</i>\n"
        f"🥇 Звание: <i>{safe_work}</i>\n"
        f"🔰 Ранг: <b>{rank}</b>"
        f"{skills_text}"
    )

    # Добавим информацию о дате получения, если она есть
    received_at = card_data.get("received_at")
    if received_at:
        # prefer explicit user_id passed to formatter; fallback to owner_id in card_data
        user_tz = None
        try:
            if user_id:
                user_tz = get_user_timezone(int(user_id))
            else:
                owner_id = card_data.get("owner_id")
                if owner_id:
                    user_tz = get_user_timezone(int(owner_id))
        except Exception:
            user_tz = None

        date_str = format_iso_utc_to_user_tz(received_at, user_tz)
        # calculate expected sell amount based on rarity and rank
        try:
            rank_val = int(card_data.get("rank", 1))
        except Exception:
            rank_val = 1
        base_price = RARITY_PRICES_MEMBER.get(rarity, 5)
        multiplier = RANK_MULTIPLIERS.get(rank_val, 1.0)
        sell_amount = int(round(base_price * multiplier))

        return base + f"\n\nДата получения: <b>{date_str}</b>" + f"\n\nПри продаже вы получите: <b>{sell_amount} 🔥</b>"

    # Старые карточки — показываем, что дата неизвестна
    # calculate expected sell amount based on rarity and rank
    try:
        rank_val = int(card_data.get("rank", 1))
    except Exception:
        rank_val = 1

    base_price = RARITY_PRICES_MEMBER.get(rarity, 5)
    multiplier = RANK_MULTIPLIERS.get(rank_val, 1.0)
    sell_amount = int(round(base_price * multiplier))

    return base + f"\n\nДата получения: <b>неизвестна (до обновления)</b>" + f"\n\nПри продаже вы получите: <b>{sell_amount} 🔥</b>"

async def show_my_cards(event: CallbackQuery | Message):
    user_id = event.from_user.id
    user_cards = get_member_cards(user_id)
    owned_card_names = [name for name in user_cards if not name.startswith("_")]

    if not owned_card_names:
        message = "У тебя пока нет карточек 🙁"
        from utils.helpers import safe_edit_message
        await safe_edit_message(event.message, message, reply_markup=get_back_menu_colletion_button())
        return

    index = 0
    card_name = owned_card_names[index]
    card_data = user_cards[card_name]

    card_info = next(
        (c for c in MEMBER_CARDS if c["name"].strip().lower() == card_name.strip().lower()),
        None
    )

    if card_info is None:
        msg = "❌ Ошибка: карточка не найдена."
        if isinstance(event, CallbackQuery):
            await event.message.answer(msg)
            await event.answer()
        else:
            await event.answer(msg)
        return

    image_path = get_member_card_image_path(card_data, card_info)

    if not image_path:
        await event.message.answer("❌ Ошибка: изображение карточки не найдено.")
        return

    photo = FSInputFile(image_path)
    work = card_info.get("work", "неизвестно")
    rarity = card_info.get("rarity", "Обычная")
    caption = format_card_text(card_name, card_data, rarity, work, user_id=event.from_user.id if hasattr(event, 'from_user') else None)
    keyboard = get_member_card_navigation_keyboard(index, len(owned_card_names), prefix="my_member_cards", card_name=card_name)

    if isinstance(event, CallbackQuery):
        try:
            await event.message.edit_media(
                media=types.InputMediaPhoto(media=photo, caption=caption),
                reply_markup=keyboard
            )
        except TelegramBadRequest as e:
            msg = str(e)
            if "message is not modified" in msg:
                pass
            elif "IMAGE_PROCESS_FAILED" in msg or "image process failed" in msg.lower():
                # try to fallback to sending as document
                try:
                    await event.message.answer_document(document=photo, caption=caption, reply_markup=keyboard)
                except Exception:
                    await event.message.answer(text=caption, reply_markup=keyboard)
            else:
                logging.warning(f"Не удалось заменить сообщение карточкой участника: {e}")
                await safe_delete(event)
                try:
                    await event.message.answer_photo(
                        photo=photo,
                        caption=caption,
                        reply_markup=keyboard,
                    )
                except TelegramBadRequest as fallback_error:
                    fallback_message = str(fallback_error)
                    if "IMAGE_PROCESS_FAILED" in fallback_message or "image process failed" in fallback_message.lower():
                        try:
                            await event.message.answer_document(
                                document=photo,
                                caption=caption,
                                reply_markup=keyboard,
                            )
                        except Exception:
                            await event.message.answer(text=caption, reply_markup=keyboard)
                    else:
                        raise
        await event.answer()
    else:
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

async def show_member_cards_list(event: CallbackQuery):
    user_cards = get_member_cards(event.from_user.id)
    if not any(not name.startswith("_") for name in user_cards):
        await safe_edit_message(
            event.message,
            "У тебя пока нет карточек 🙁",
            reply_markup=get_back_menu_colletion_button(),
        )
        await event.answer()
        return

    sort_mode, page = parse_collection_list_callback(event.data or "")
    owned_card_names = get_owned_member_card_names(user_cards, sort_mode)
    total_pages = max(1, (len(owned_card_names) + LIST_PAGE_SIZE - 1) // LIST_PAGE_SIZE)
    page = min(page, total_pages - 1)
    start = page * LIST_PAGE_SIZE
    page_card_names = owned_card_names[start:start + LIST_PAGE_SIZE]

    lines = [
        format_member_list_line(
            start + offset + 1,
            card_name,
            user_cards.get(card_name, {}),
            find_member_card(card_name),
        )
        for offset, card_name in enumerate(page_card_names)
    ]
    text = (
        "👥 <b>Мои участники</b>\n\n"
        + "\n".join(lines)
        + (
            f"\n\nВсего карточек: <b>{len(owned_card_names)}</b>"
            f"\nСтраница: <b>{page + 1}/{total_pages}</b>"
            f"\nСортировка: <b>{SORT_LABELS[sort_mode]}</b>"
        )
    )
    keyboard = get_collection_list_keyboard(
        list_prefix="member_cards_list",
        cards_callback="my_member_cards",
        page=page,
        total_pages=total_pages,
        sort_mode=sort_mode,
    )
    await safe_edit_message(event.message, text, reply_markup=keyboard)
    await event.answer()


async def navigate_my_member_cards(event: CallbackQuery):
    user_id = event.from_user.id
    user_cards = get_member_cards(user_id)
    owned_card_names = [name for name in user_cards if not name.startswith("_")]

    if not owned_card_names:
        message = "У тебя пока нет карточек 🙁"
        from utils.helpers import safe_edit_message
        await safe_edit_message(event.message, message, reply_markup=get_back_menu_colletion_button())
        return

    try:
        index = int(event.data.split(":")[1])
    except (ValueError, IndexError):
        index = 0

    index %= len(owned_card_names)
    card_name = owned_card_names[index]
    card_data = user_cards[card_name]

    card_info = next(
        (c for c in MEMBER_CARDS if c["name"].strip().lower() == card_name.strip().lower()),
        None
    )

    if card_info is None:
        await event.message.answer("❌ Ошибка: карточка не найдена.")
        await event.answer()
        return

    image_path = get_member_card_image_path(card_data, card_info)
    if not image_path or not os.path.exists(image_path):
        await event.message.answer("❌ Ошибка: изображение карточки не найдено.")
        return

    photo = FSInputFile(image_path)
    work = card_info.get("work", "неизвестно")
    rarity = card_info.get("rarity", "Обычная")
    caption = format_card_text(card_name, card_data, rarity, work, user_id=event.from_user.id if hasattr(event, 'from_user') else None)
    keyboard = get_member_card_navigation_keyboard(index, len(owned_card_names), prefix="my_member_cards", card_name=card_name)

    try:
        await event.message.edit_media(
            media=types.InputMediaPhoto(media=photo, caption=caption),
            reply_markup=keyboard
        )
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            logging.warning(f"TelegramBadRequest при навигации по картам участников: {e}")
            # Пробуем отправить как новое сообщение, если edit не удался
            try:
                await event.message.answer_photo(photo=photo, caption=caption, reply_markup=keyboard)
            except Exception as fallback_error:
                logging.exception(f"Ошибка при отправке фото участника: {fallback_error}")
                await event.message.answer(text=caption, reply_markup=keyboard)
    await event.answer()

async def sell_member_card(event: CallbackQuery):
    user_id = event.from_user.id
    user_cards = get_member_cards(user_id)
    owned_card_names = [name for name in user_cards if not name.startswith("_")]

    if not owned_card_names:
        await event.answer("У тебя нет карточек", show_alert=True)
        return

    # Determine which card to sell: if CallbackQuery contains index, use it; otherwise default to 0
    index = 0
    if event.data and event.data.startswith("sell_member_card:"):
        try:
            index = int(event.data.split(":")[1]) % len(owned_card_names)
        except Exception:
            index = 0

    card_name = owned_card_names[index]
    
    # Проверяем, не является ли карта эксклюзивной (за пресейв) - такие карты нельзя продавать
    if card_name in ["Я люблю жизнь", "Яйцо"]:
        await event.answer("❌ Эксклюзивные карты за пресейв нельзя продавать!", show_alert=True)
        return
    
    card_data = user_cards[card_name]

    card_info = next(
        (c for c in MEMBER_CARDS if c["name"].strip().lower() == card_name.strip().lower()),
        None
    )

    if card_info is None:
        msg = "❌ Ошибка: карточка не найдена."
        await event.message.answer(msg)
        await event.answer()
        return

    image_path = get_member_card_image_path(card_data, card_info)

    if not image_path:
        await event.message.answer("❌ Ошибка: изображение карточки не найдено.")
        return

    photo = FSInputFile(image_path)
    work = card_info.get("work", "неизвестно")
    rarity = card_info.get("rarity", "Обычная")
    caption = format_card_text(card_name, card_data, rarity, work, user_id=event.from_user.id if hasattr(event, 'from_user') else None)
    keyboard = get_member_card_navigation_keyboard(index, len(owned_card_names), prefix="my_member_cards", card_name=card_name)

    try:
        await event.message.edit_media(
            media=types.InputMediaPhoto(media=photo, caption=caption),
            reply_markup=keyboard
        )
    except TelegramBadRequest as e:
        msg = str(e)
        if "message is not modified" in msg:
            pass
        elif "IMAGE_PROCESS_FAILED" in msg or "image process failed" in msg.lower():
            # try to fallback to sending as document
            try:
                await event.message.answer_document(document=photo, caption=caption, reply_markup=keyboard)
            except Exception:
                await event.message.answer(text=caption, reply_markup=keyboard)
        else:
            raise
    await event.answer()
    
    # --- Выплата при продаже карты ---
    try:
        # Базовая цена по редкости
        rarity = card_info.get("rarity", "Обычная")
        rarity_prices = {
            "Обычная": 5,
            "Редкая": 10,
            "Эпическая": 20,
            "Легендарная": 50
        }
        base_price = rarity_prices.get(rarity, 5)

        # Множитель по рангу (rank 1..4)
        rank = int(card_data.get("rank", 1))
        rank_multipliers = {1: 1.0, 2: 2.2, 3: 3.3, 4: 4.4}
        multiplier = rank_multipliers.get(rank, 1.0)

        amount = int(round(base_price * multiplier))

        # --- ИСПРАВЛЕНИЕ: Проверяем бонус от карты "ВЫГОДНАЯ СДЕЛКА" ---
        from .epic_cards import check_vygodnaya_sdelka
        amount = check_vygodnaya_sdelka(user_id, amount)
        # ---------------------------------------------------------------

        # Удаляем карту из коллекции пользователя
        del user_cards[card_name]
        update_member_cards(user_id, user_cards)

        # Добавляем баланс
        new_balance = add_balance(user_id, amount)

        # Экранируем название карты для текста
        safe_card_name = html.escape(card_name)
        text = (
        f"✅ Карточка '{safe_card_name}' продана за {amount} 🔥.\n Твой новый баланс: {new_balance} 🔥"
        )

        try:
             await event.message.edit_text(text,reply_markup=get_card_member_ui())
        except TelegramBadRequest:
            # Если нет текста в сообщении (например, карточка с фото)
            await event.message.delete()
            await event.message.answer(text, reply_markup=get_card_member_ui())
    except Exception as e:
        logging.exception("Ошибка при продаже карты:")
        await event.message.answer("❌ Ошибка при продаже карты. Попробуйте позже.")

# 📥 Обработка кнопки продажи карты
@router.callback_query(F.data.startswith("sell_member_card"))
async def handle_sell_member_card(callback: CallbackQuery):
    await sell_member_card(callback)

# 📥 Обработка кнопки "Мои участники"
@router.callback_query(F.data == "my_member_cards")
async def handle_my_member_cards(callback: CallbackQuery):
    await show_my_cards(callback)


@router.callback_query(F.data.startswith("member_cards_list:"))
async def handle_member_cards_list(callback: CallbackQuery):
    await show_member_cards_list(callback)


# 📥 Обработка команды
@router.message(lambda message: message.text == "📦 Мои участники")
async def handle_draw_member_command(message: Message):
    await show_my_cards(message)

# 📥 Обработка навигации
@router.callback_query(F.data.startswith("my_member_cards:"))
async def handle_card_navigation(callback: CallbackQuery):
    await navigate_my_member_cards(callback)

# 📥 Обработка кнопки апгрейда карты
@router.callback_query(F.data.startswith("upgrade_member_card:"))
async def handle_upgrade_member_card(callback: CallbackQuery):
    await upgrade_member_card(callback)

async def upgrade_member_card(event: CallbackQuery):
    user_id = event.from_user.id
    user_cards = get_member_cards(user_id)
    owned_card_names = [name for name in user_cards if not name.startswith("_")]

    if not owned_card_names:
        await event.answer("У тебя нет карточек", show_alert=True)
        return

    # Determine which card to upgrade
    index = 0
    if event.data and event.data.startswith("upgrade_member_card:"):
        try:
            index = int(event.data.split(":")[1]) % len(owned_card_names)
        except Exception:
            index = 0

    card_name = owned_card_names[index]
    
    # Проверяем, не является ли карта эксклюзивной (за пресейв) - такие карты нельзя улучшать
    if card_name in ["Я люблю жизнь", "Яйцо"]:
        await event.answer("❌ Эксклюзивные карты за пресейв нельзя улучшать!", show_alert=True)
        return
    
    card_data = user_cards[card_name]

    card_info = next(
        (c for c in MEMBER_CARDS if c["name"].strip().lower() == card_name.strip().lower()),
        None
    )

    if card_info is None:
        msg = "❌ Ошибка: карточка не найдена."
        await event.message.answer(msg)
        await event.answer()
        return

    # Получаем текущий ранг и редкость
    current_rank = int(card_data.get("rank", 1))
    rarity = card_info.get("rarity", "Обычная")

    # Максимальный ранг - 4
    if current_rank >= 4:
        await event.answer("⛔ Этот ранг максимальный!", show_alert=True)
        return

    # Получаем стоимость апгрейда
    upgrade_cost = UPGRADE_COSTS_MEMBER.get(rarity, 50)

    # Проверяем баланс пользователя
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    user_balance = int(row[0]) if row and row[0] is not None else 0
    conn.close()

    if user_balance < upgrade_cost:
        await event.answer(f"❌ Недостаточно 🔥! Нужно {upgrade_cost} 🔥", show_alert=True)
        return

    # Списываем баланс
    new_balance = add_balance(user_id, -upgrade_cost)

    # Повышаем ранг карты
    user_cards[card_name]["rank"] = current_rank + 1
    update_member_cards(user_id, user_cards)

    # Экранируем название карты для текста
    safe_card_name = html.escape(card_name)
    text = (
        f"✅ Карточка '{safe_card_name}' улучшена до ранга {current_rank + 1}!\n"
        f"Списано: {upgrade_cost} 🔥\n"
        f"Твой новый баланс: {new_balance} 🔥"
    )

    try:
        await event.message.edit_text(text, reply_markup=get_card_member_ui())
    except TelegramBadRequest:
        await event.message.delete()
        await event.message.answer(text, reply_markup=get_card_member_ui())

    await event.answer()