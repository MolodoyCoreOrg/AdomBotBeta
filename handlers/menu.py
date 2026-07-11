import sqlite3, json
from datetime import datetime, timezone

from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, ContentType, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder


from .keyboard import get_main_keyboard, get_card_open_ui_keyboard, get_card_collection_ui_keyboard, profile_ui, support_ui, donate_ui, top_menu_ui, get_persistent_bottom_keyboard, shop_ui
from database.db import add_user, user_exists, add_bonus, update_referral_bonuses, get_referral_message, update_user_info
from utils.helpers import get_timer_status


# Состояния FSM для системы обмена (должны быть определены до использования)
class TradeState(StatesGroup):
    waiting_for_partner_username = State()
    selecting_card_to_trade = State()
    viewing_partner_cards = State()


DB_PATH = "database/users.db"
def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

router = Router()

@router.callback_query(F.data == "main_trade")
async def handle_trade_button(callback: CallbackQuery, state: FSMContext):
    """Показать главное меню обмена с кнопками."""
    user_id = callback.from_user.id
    
    # Проверяем есть ли активные предложения
    from database.db import get_pending_offers_to_user, get_pending_offers_from_user
    incoming = get_pending_offers_to_user(user_id)
    outgoing = get_pending_offers_from_user(user_id)
    
    builder = InlineKeyboardBuilder()
    
    if incoming:
        builder.row(
            InlineKeyboardButton(text=f"📥 Входящие предложения ({len(incoming)})", callback_data="view_incoming_offers")
        )
    if outgoing:
        builder.row(
            InlineKeyboardButton(text=f"📤 Исходящие предложения ({len(outgoing)})", callback_data="view_my_offers")
        )
    
    builder.row(
        InlineKeyboardButton(text="➕ Создать новый обмен", callback_data="create_exchange")
    )
    builder.row(
        InlineKeyboardButton(text="↪️ Назад", callback_data="go_back_menu")
    )
    
    text = (
        "🔄 <b>Обмен карточками</b>\n\n"
        "Здесь вы можете обмениваться карточками с другими игроками.\n\n"
        "Процесс обмена:\n"
        "1️⃣ Выберите карту, которую хотите отдать\n"
        "2️⃣ Введите @username партнера\n"
        "3️⃣ Выберите карту, которую хотите получить\n"
        "4️⃣ Отправьте предложение\n\n"
        "Партнер получит сообщение с кнопками \"Принять\" или \"Отклонить\"."
    )
    
    await safe_edit_or_replace(
        callback,
        text,
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "trade_create_new")
async def handle_trade_create_new(callback: CallbackQuery, state: FSMContext):
    """Начать создание нового обмена - запрос username партнера."""
    # Перенаправляем на create_exchange в handlers/exchange.py
    await callback.message.edit_text(
        text="🔄 <b>Создание обмена</b>\n\n"
             "Выберите тип карты, которую хотите предложить для обмена:",
        reply_markup=None,
        parse_mode="HTML"
    )
    await callback.answer()
    # Вызываем функцию из exchange.py
    from handlers.exchange import create_exchange
    await create_exchange(callback, state)


@router.message(TradeState.waiting_for_partner_username)
async def process_partner_input(message: Message, state: FSMContext):
    """Обработка ввода username партнера для создания обмена."""
    user_id = message.from_user.id
    text = message.text.strip()
    
    if not text:
        await message.answer("❌ Введите корректный username.")
        return
    
    # Проверяем формат username
    if not text.startswith("@"):
        await message.answer("❌ Username должен начинаться с @. Пример: @username")
        return
    
    username = text[1:]  # убираем @
    
    # Ищем пользователя в базе по username
    conn = connect()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username FROM users WHERE username = ?", (username,))
    user_row = cursor.fetchone()
    conn.close()
    
    if not user_row:
        await message.answer(f"❌ Пользователь @{username} не найден.")
        return
    
    partner_id = user_row["user_id"]
    partner_username = user_row["username"]
    
    if partner_id == user_id:
        await message.answer("❌ Нельзя начать обмен с самим собой.")
        await state.clear()
        return
    
    # Импортируем create_trade из handlers.exchange
    from handlers.exchange import create_trade as trade_create, get_trade_main_keyboard_with_username
    
    # Создаем обмен
    trade_id = await trade_create(user_id, partner_id)
    if not trade_id:
        await message.answer("❌ Не удалось создать обмен.")
        await state.clear()
        return
    
    await state.update_data(
        trade_id=trade_id,
        partner_id=partner_id,
        trade_mode=True
    )
    # НЕ очищаем состояние здесь, оно нужно для работы с обменом
    
    # Отправляем уведомление партнеру с кнопками принятия/отклонения
    try:
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="✅ Принять обмен", callback_data=f"accept_exchange:{user_id}"),
            InlineKeyboardButton(text="❌ Отклонить обмен", callback_data=f"reject_exchange:{user_id}")
        )
        
        initiator_username = message.from_user.username or "не указан"
        await message.bot.send_message(
            chat_id=partner_id,
            text=f"🔄 <b>Вам предложили обмен!</b>\n\n"
                 f"Пользователь: @{initiator_username}\n"
                 f"хочет обменяться карточками.\n\n"
                 f"Выберите действие:",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
    except Exception as e:
        print(f"Не удалось отправить уведомление партнеру {partner_id}: {e}")
    
    # Показываем меню обмена инициатору
    await message.answer(
        text=f"✅ <b>Обмен создан!</b>\n\n"
             f"Партнер: @{partner_username}\n\n"
             f"Ожидаете ответа партнера...",
        reply_markup=get_trade_main_keyboard_with_username(partner_id, partner_username),
        parse_mode="HTML"
    )

@router.message(Command("menu"))
@router.message(Command("start"))
async def start_handler(message: Message):

    user_id = message.from_user.id

    update_user_info(
        user_id,
        message.from_user.username or "",
        message.from_user.first_name or "",
        message.from_user.last_name or ""
    )

    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT roulette_count FROM roulette_user WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()

    from database.db import load_roulette_data
    data = load_roulette_data(str(user_id))
    spins = data.get("roulette_count", 0)

    member_card_status = get_timer_status(user_id, "data/table/timer_members_card.json", "👥Карта участника")
    skill_card_status = get_timer_status(user_id, "data/table/timer_skills_card.json", "🃏Суперспособность")

    text_msg1 = (
        f"Привет, <b>{message.from_user.first_name}</b>!\n"
        "Добро пожаловать в СИСЬКИ.\n Ну что, готов вытягивать новые карточки?\n\n"
        f"{member_card_status}\n"
        f"{skill_card_status}"
    )

    text_msg2 = (
        f"Привет, <b>{message.from_user.first_name}</b>!\n"
        "Добро пожаловать в СИСЬКИ. Здесь ты можешь вытягивать карточки с умениями и участниками ГУЧИГЕНГОВО! Раз в сутки ты можешь вытягигивать карточку с умением и раз в неделю карточку с участником. \n\n"
        "Пора начинать, вытягивай свои первые карты 🔮\n\n"
        f"{member_card_status}\n"
        f"{skill_card_status}"
    )

    reply_markup = await get_main_keyboard(spins, user_id)

    # Вытаскиваем аргументы вручную
    text = message.text or ""
    args = text.split(maxsplit=1)[1] if len(text.split()) > 1 else ""
    referrer_id = None

    if args:
        try:
            possible_referrer = int(args)
            if possible_referrer != user_id and user_exists(possible_referrer):
                referrer_id = possible_referrer
        except ValueError:
            pass

    if user_exists(user_id):
        print(f"User {user_id} уже есть в базе данных")
        await message.answer( text_msg1, reply_markup = reply_markup)

    else:
        print(f"Добавляю нового пользователя {user_id} с реферером {referrer_id}")
        add_user(
            user_id,
            username=message.from_user.username or "",
            first_name=message.from_user.first_name or "",
            last_name=message.from_user.last_name or "",
            referrer_id=referrer_id
        )
        if referrer_id:
            try:
                with connect() as conn:
                    cur = conn.cursor()
                    cur.execute("SELECT referral_bonuses FROM users WHERE user_id = ?", (referrer_id,))
                    row = cur.fetchone()
                    if row:
                        before_given = row["referral_bonuses"]

                # Обновляем бонусы
                update_referral_bonuses(referrer_id)

                # Получаем текст и клавиатуру
                text, markup = get_referral_message(referrer_id, before_given)

                await message.bot.send_message(referrer_id, text, reply_markup=markup)
            except Exception as e:
                print(f"Не удалось отправить сообщение рефереру {referrer_id}: {e}")

        await message.answer(text_msg2, reply_markup = reply_markup)









# === Профиль ===
def get_user_data(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

def get_referrals_count(user_id: int) -> int:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users WHERE referrer_id = ?", (user_id,))
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_profile_text(user_id: int) -> str:
    user = get_user_data(user_id)
    if not user:
        return "❌ Профиль не найден."

    username = user["username"] or "—"
    user_number = user["user_number"] or "—"
    registered_at = user["registered_at"]
    admin_lvl = user["admin_lvl"]
    banned = bool(user["banned"])

    try:
        member_cards = json.loads(user["member_cards"])
    except Exception:
        member_cards = {}

    try:
        skill_cards = json.loads(user["skill_cards"])
    except Exception:
        skill_cards = {}

    total_members = len(member_cards)
    total_skills = len(skill_cards)
    referrals_count = get_referrals_count(user_id)

    BOT_USERNAME = "CuCbKu_gg_bot"
    referral_link = f"https://t.me/{BOT_USERNAME}?start={user_id}"

    return (
        f"👤 Твой профиль:\n"
        f"📌 Номер: {user_number}\n\n"
        f"👥 Карточки участников: <b>{total_members}</b>\n"
        f"🧠 Суперспособностей: <b>{total_skills}</b>\n"
        f"🔥 Баланс: <b>{user['balance']}</b>\n\n"
        f"🆔 ID: {user_id}\n"
        f"💛 Username: @{username}\n"
        f"🗓 Зарегистрирован: {registered_at}\n"
        f"👥 <b>Приглашено друзей:</b> {referrals_count}\n\n"
        f"🔗 Твоя реферальная ссылка:\n"
        f"{referral_link}\n"
        f"За каждого приглашенного друга вы получаете возможность открыть карту участника, после 10 приглашенных друзей возможность выдаётся за каждого второго, после 20 приглашенных друзей возможность выдаётся за каждого третьего"
    )

 

# === UTILITS ===

async def safe_edit_or_replace(callback: CallbackQuery, new_text: str, reply_markup=None, parse_mode=None, keep_message: bool = False):
    msg: Message = callback.message

    try:
        if msg.content_type == "text":
            await msg.edit_text(new_text, reply_markup=reply_markup, parse_mode=parse_mode)
        elif msg.content_type in {"photo", "video", "document", "audio", "voice"}:
            try:
                await msg.edit_caption(new_text, reply_markup=reply_markup, parse_mode=parse_mode)
            except TelegramBadRequest:
                if not keep_message:
                    await msg.delete()
                    await callback.message.answer(new_text, reply_markup=reply_markup, parse_mode=parse_mode)
        else:
            if not keep_message:
                await msg.delete()
                await callback.message.answer(new_text, reply_markup=reply_markup, parse_mode=parse_mode)
    except TelegramBadRequest:
        if not keep_message:
            await callback.message.answer(new_text, reply_markup=reply_markup, parse_mode=parse_mode)

    await callback.answer()

# === ОБРАБОТКА Callback ===
@router.callback_query(F.data == "main_open_cards")
async def handle_open_cards(callback: CallbackQuery):
    await safe_edit_or_replace(
        callback,
        "📙 Какой тип карточек вы хотите открыть?",
        get_card_open_ui_keyboard()
    )

@router.callback_query(F.data == "main_card_collection")
async def handle_card_collection(callback: CallbackQuery):
    await safe_edit_or_replace(
        callback,
        "📦 Коллекцию каких карточек вы хотите посмотреть?",
        get_card_collection_ui_keyboard()
    )


from aiogram import F as FilterF
from aiogram.filters import Command
from database.db import user_exists


@router.message(Command("trade"))
async def start_trade_command(message: Message, state: FSMContext):
    """Команда /trade для начала обмена через username."""
    user_id = message.from_user.id
    
    # Парсим аргументы команды
    text = message.text or ""
    args = text.split(maxsplit=1)[1] if len(text.split()) > 1 else ""
    
    if not args:
        await message.answer(
            "❌ Укажите username партнера.\n\n"
            "Пример:\n"
            "<code>/trade @username</code>",
            parse_mode="HTML"
        )
        return
    
    # Проверяем формат username
    if not args.startswith("@"):
        await message.answer("❌ Username должен начинаться с @. Пример: @username")
        return
    
    username = args[1:]  # убираем @
    
    # Ищем пользователя в базе по username
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username FROM users WHERE username = ?", (username,))
    user_row = cursor.fetchone()
    conn.close()
    
    if not user_row:
        await message.answer(f"❌ Пользователь @{username} не найден.")
        return
    
    partner_id = user_row["user_id"]
    partner_username = user_row["username"]
    
    if partner_id == user_id:
        await message.answer("❌ Нельзя начать обмен с самим собой.")
        return
    
    # Отправляем уведомление партнеру с кнопками принятия/отклонения
    try:
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="✅ Принять обмен", callback_data=f"accept_exchange:{user_id}"),
            InlineKeyboardButton(text="❌ Отклонить обмен", callback_data=f"reject_exchange:{user_id}")
        )
        
        initiator_username = message.from_user.username or "не указан"
        await message.bot.send_message(
            chat_id=partner_id,
            text=f"🔄 <b>Вам предложили обмен!</b>\n\n"
                 f"Пользователь: @{initiator_username}\n"
                 f"хочет обменяться карточками.\n\n"
                 f"Выберите действие:",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
    except Exception as e:
        print(f"Не удалось отправить уведомление партнеру {partner_id}: {e}")
    
    # Показываем меню обмена инициатору
    await message.answer(
        text=f"✅ <b>Обмен создан!</b>\n\n"
             f"Партнер: @{partner_username}\n\n"
             f"Ожидаете ответа партнера...",
        reply_markup=None,
        parse_mode="HTML"
    )


@router.message(Command("trademenu"))
async def show_trade_menu(message: Message, state: FSMContext):
    """Показать меню текущего активного обмена."""
    from handlers.exchange import get_active_trade_for_user, get_trade_main_keyboard, get_partner_id
    
    user_id = message.from_user.id
    trade = get_active_trade_for_user(user_id)
    
    if not trade:
        await message.answer("❌ У вас нет активного обмена.")
        return
    
    partner_id = get_partner_id(trade, user_id)
    if not partner_id:
        await message.answer("❌ Ошибка: партнер не найден.")
        return
    
    await message.answer(
        text="🔄 <b>Меню обмена</b>\n\nВыберите действие:",
        reply_markup=get_trade_main_keyboard(partner_id),
        parse_mode="HTML"
    )


@router.callback_query(FilterF.data.startswith("start_trade:"))
async def start_trade_callback_handler(callback: CallbackQuery, state: FSMContext):
    """Обработчик callback для начала обмена из профиля."""
    try:
        partner_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка: неверный ID партнера", show_alert=True)
        return
    
    user_id = callback.from_user.id
    
    if partner_id == user_id:
        await callback.answer("❌ Нельзя начать обмен с самим собой", show_alert=True)
        return
    
    if not user_exists(partner_id):
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return
    
    # Импортируем create_trade из handlers.exchange
    from handlers.exchange import create_trade as trade_create, get_trade_main_keyboard
    
    trade_id = await trade_create(user_id, partner_id)
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
                 f"Используйте команду <code>/trademenu</code> для управления обменом.",
            parse_mode="HTML"
        )
    except Exception as e:
        print(f"Не удалось отправить уведомление партнеру {partner_id}: {e}")
    
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


@router.callback_query(F.data == "main_profile")
async def handle_profile_button(callback: CallbackQuery):
    user_id = callback.from_user.id

    update_user_info(
        user_id,
        callback.from_user.username or "",
        callback.from_user.first_name or "",
        callback.from_user.last_name or ""
    )

    text = get_profile_text(user_id)
    reply_markup = profile_ui(user_id)

    msg = callback.message

    if msg.content_type == ContentType.TEXT:
        try:
            await msg.edit_text(text, reply_markup=reply_markup, parse_mode="HTML")
        except Exception:
            await msg.delete()
            await msg.answer(text, reply_markup=reply_markup, parse_mode="HTML")
    else:
        try:
            await msg.delete()
        except Exception:
            pass
        await callback.message.answer(text, reply_markup=reply_markup, parse_mode="HTML")

    await callback.answer()



@router.callback_query(F.data == "support_menu_button")
async def support_button(callback: CallbackQuery):
    await safe_edit_or_replace(
        callback,
        new_text="❓ У вас возникли вопросы или есть идея?",
        reply_markup=support_ui()
    )

@router.callback_query(F.data == "donate_menu")
async def support_button(callback: CallbackQuery):
    await safe_edit_or_replace(
        callback,
        new_text="Донат может составлять любую сумму от 100 рублей\n\n"
        "Напоминаем: Донат не дает никакого преимущества, вы просто поддержите разработку бота и получите прикалюху ^_^\n\n" 
        "Оплатить можно:",
        reply_markup=donate_ui()
    )

@router.callback_query(F.data == "top_menu")
async def support_button(callback: CallbackQuery):
    await safe_edit_or_replace(
        callback,
        new_text="Выберите категорию:",
        reply_markup=top_menu_ui()
    )













@router.message(F.text == "Меню")
async def show_main_menu(message: Message):
    """Главное меню — и по кнопке, и по команде /menu."""
    user_id = message.from_user.id

    update_user_info(
        user_id,
        message.from_user.username or "",
        message.from_user.first_name or "",
        message.from_user.last_name or ""
    )

    from database.db import load_roulette_data
    data = load_roulette_data(str(user_id))
    spins = data.get("roulette_count", 0)

    # --- Проверяем таймеры ---
    member_card_status = get_timer_status(user_id, "data/table/timer_members_card.json", "👥Карта участника")
    skill_card_status = get_timer_status(user_id, "data/table/timer_skills_card.json", "🃏Суперспособность")

    # --- Текст меню ---
    text = (
        "🏠 Главное меню:\n\n"
        f"{member_card_status}\n"
        f"{skill_card_status}"
    )

    await message.answer(text, reply_markup=await get_main_keyboard(spins, user_id))



@router.callback_query(F.data == "go_back_menu")
async def go_back(callback: CallbackQuery):
    user_id = callback.from_user.id

    update_user_info(
        user_id,
        callback.from_user.username or "",
        callback.from_user.first_name or "",
        callback.from_user.last_name or ""
    )

    from database.db import load_roulette_data
    data = load_roulette_data(str(user_id))
    spins = data.get("roulette_count", 0)

    member_card_status = get_timer_status(user_id, "data/table/timer_members_card.json", "👥Карта участника")
    skill_card_status = get_timer_status(user_id, "data/table/timer_skills_card.json", "🃏Суперспособность")

    text = (
        "🏠 Главное меню:\n\n"
        f"{member_card_status}\n"
        f"{skill_card_status}"
    )
    reply_markup = await get_main_keyboard(spins, user_id)

    msg = callback.message

    if msg.content_type == ContentType.TEXT:
        try:
            await msg.edit_text(text, reply_markup=reply_markup, parse_mode="HTML")
        except Exception:
            await msg.delete()
            await msg.answer(text, reply_markup=reply_markup, parse_mode="HTML")
    else:
        try:
            await msg.delete()
        except Exception:
            pass
        await callback.message.answer(text, reply_markup=reply_markup, parse_mode="HTML")

# === АДМИН МЕНЮ ===
@router.callback_query(F.data == "admin_menu")
async def handle_admin_menu(callback: CallbackQuery):
    """Показать админ-меню только для админов."""
    from utils.config import ADMINS_LIST
    
    user_id = callback.from_user.id
    
    if user_id not in ADMINS_LIST:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    text = (
        "🔐 <b>Админ-панель</b>\n\n"
        "Выберите действие:"
    )
    
    from handlers.keyboard import admin_menu_ui
    await safe_edit_or_replace(
        callback,
        text,
        reply_markup=admin_menu_ui(),
        parse_mode="HTML",
        keep_message=True
    )


@router.callback_query(F.data == "admin_give_all_skills")
async def handle_admin_give_all_skills(callback: CallbackQuery):
    """Выдать все карты суперспособностей пользователю."""
    from utils.config import ADMINS_LIST
    from database.db import get_skill_cards, update_skill_cards
    import json
    
    user_id = callback.from_user.id
    
    if user_id not in ADMINS_LIST:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    # Загружаем все карты из каталога
    with open("data/cards/skills.json", "r", encoding="utf-8") as f:
        all_cards = json.load(f)
    
    # Получаем текущие карты пользователя
    user_cards = get_skill_cards(user_id)
    
    # Добавляем все карты, которых ещё нет
    added_count = 0
    for card in all_cards:
        card_name = card["name"]
        if card_name not in user_cards:
            user_cards[card_name] = {"rank": 1, "received_at": datetime.utcnow().isoformat()}
            added_count += 1
    
    # Сохраняем обновлённые карты
    update_skill_cards(user_id, user_cards)
    
    await callback.answer(f"✅ Выдано {added_count} карт суперспособностей!", show_alert=True)
    
    # Обновляем сообщение с админ-меню (не создавая дубль)
    text = (
        "🔐 <b>Админ-панель</b>\n\n"
        "Выберите действие:"
    )
    
    from handlers.keyboard import admin_menu_ui
    await safe_edit_or_replace(
        callback,
        text,
        reply_markup=admin_menu_ui(),
        parse_mode="HTML",
        keep_message=True
    )


@router.callback_query(F.data == "admin_give_1000_currency")
async def handle_admin_give_1000_currency(callback: CallbackQuery):
    """Выдать 1000 огонечков пользователю."""
    from utils.config import ADMINS_LIST
    from database.db import add_balance
    
    user_id = callback.from_user.id
    
    if user_id not in ADMINS_LIST:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    # Выдаём 1000 огонечков
    new_balance = add_balance(user_id, 1000)
    
    await callback.answer(f"✅ Выдано 1000 🔥! Новый баланс: {new_balance}", show_alert=True)
    
    # Обновляем сообщение с админ-меню (не создавая дубль)
    text = (
        "🔐 <b>Админ-панель</b>\n\n"
        "Выберите действие:"
    )
    
    from handlers.keyboard import admin_menu_ui
    await safe_edit_or_replace(
        callback,
        text,
        reply_markup=admin_menu_ui(),
        parse_mode="HTML",
        keep_message=True
    )


@router.callback_query(F.data == "admin_give_10000_currency")
async def handle_admin_give_10000_currency(callback: CallbackQuery):
    """Выдать 10000 огонечков пользователю."""
    from utils.config import ADMINS_LIST
    from database.db import add_balance
    
    user_id = callback.from_user.id
    
    if user_id not in ADMINS_LIST:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    # Выдаём 10000 огонечков
    new_balance = add_balance(user_id, 10000)
    
    await callback.answer(f"✅ Выдано 10000 🔥! Новый баланс: {new_balance}", show_alert=True)
    
    # Обновляем сообщение с админ-меню (не создавая дубль)
    text = (
        "🔐 <b>Админ-панель</b>\n\n"
        "Выберите действие:"
    )
    
    from handlers.keyboard import admin_menu_ui
    await safe_edit_or_replace(
        callback,
        text,
        reply_markup=admin_menu_ui(),
        parse_mode="HTML",
        keep_message=True
    )


@router.callback_query(F.data == "admin_give_all_members")
async def handle_admin_give_all_members(callback: CallbackQuery):
    """Выдать все карты участников пользователю."""
    from utils.config import ADMINS_LIST
    from database.db import get_member_cards, update_member_cards
    import json
    
    user_id = callback.from_user.id
    
    if user_id not in ADMINS_LIST:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    # Загружаем все карты из каталога
    with open("data/cards/members.json", "r", encoding="utf-8") as f:
        all_cards = json.load(f)
    
    # Получаем текущие карты пользователя
    user_cards = get_member_cards(user_id)
    
    # Добавляем все карты, которых ещё нет
    added_count = 0
    for card in all_cards:
        card_name = card["name"]
        if card_name not in user_cards:
            user_cards[card_name] = {"rank": 1, "received_at": datetime.utcnow().isoformat()}
            added_count += 1
    
    # Сохраняем обновлённые карты
    update_member_cards(user_id, user_cards)
    
    await callback.answer(f"✅ Выдано {added_count} карт участников!", show_alert=True)
    
    # Обновляем сообщение с админ-меню (не создавая дубль)
    text = (
        "🔐 <b>Админ-панель</b>\n\n"
        "Выберите действие:"
    )
    
    from handlers.keyboard import admin_menu_ui
    await safe_edit_or_replace(
        callback,
        text,
        reply_markup=admin_menu_ui(),
        parse_mode="HTML",
        keep_message=True
    )


# === АДМИН: СОЗДАТЬ ПРЕСЕЙВ ===
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

class PresaveCreateState(StatesGroup):
    waiting_for_link = State()
    waiting_for_card_image = State()


@router.callback_query(F.data == "admin_create_presave")
async def handle_admin_create_presave(callback: CallbackQuery, state: FSMContext):
    """Админ нажимает кнопку 'Создать пресейв' - запрос ссылки на band link."""
    from utils.config import ADMINS_LIST
    
    user_id = callback.from_user.id
    
    if user_id not in ADMINS_LIST:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    await state.set_state(PresaveCreateState.waiting_for_link)
    await callback.message.edit_text(
        "🎵 <b>Создание пресейва</b>\n\n"
        "Отправьте ссылку на Band Link для пресейва:",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(PresaveCreateState.waiting_for_link)
async def process_presave_link(message: Message, state: FSMContext):
    """Обработка ссылки на Band Link от админа."""
    from utils.config import ADMINS_LIST
    
    user_id = message.from_user.id
    
    if user_id not in ADMINS_LIST:
        return
    
    link = message.text.strip()
    if not link:
        await message.answer("❌ Отправьте корректную ссылку.")
        return
    
    await state.update_data(presave_link=link)
    await state.set_state(PresaveCreateState.waiting_for_card_image)
    await message.answer(
        "✅ Ссылка сохранена.\n\n"
        "Теперь отправьте изображение карточки, которая будет выдаваться за пресейв:",
        parse_mode="HTML"
    )


@router.message(PresaveCreateState.waiting_for_card_image, F.photo)
async def process_presave_card_image(message: Message, state: FSMContext, bot: Bot):
    """Обработка изображения карточки от админа - сохраняем и создаем кнопку пресейва."""
    from utils.config import ADMINS_LIST
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    import json
    
    user_id = message.from_user.id
    
    if user_id not in ADMINS_LIST:
        return
    
    # Получаем лучшее качество фото
    photo = message.photo[-1]
    file_id = photo.file_id
    
    # Получаем данные из состояния
    data = await state.get_data()
    presave_link = data.get("presave_link")
    
    # Сохраняем файл ID в базу или JSON для дальнейшего использования
    # Для простоты сохраним в JSON файл
    presave_config = {
        "link": presave_link,
        "card_file_id": file_id
    }
    
    with open("data/table/presave_config.json", "w", encoding="utf-8") as f:
        json.dump(presave_config, f, ensure_ascii=False)
    
    await state.clear()
    
    await message.answer(
        "✅ Пресейв успешно создан!\n\n"
        f"Ссылка: {presave_link}\n"
        "Карточка сохранена.\n\n"
        "Теперь пользователи могут нажать кнопку 'Сделать пресейв' в главном меню.",
        parse_mode="HTML"
    )