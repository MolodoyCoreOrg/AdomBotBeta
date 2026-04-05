import sqlite3, json
from datetime import datetime, timezone

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, ContentType
from aiogram.exceptions import TelegramBadRequest


from .keyboard import get_main_keyboard, get_card_open_ui_keyboard, get_card_collection_ui_keyboard, profile_ui, support_ui, donate_ui, top_menu_ui, get_persistent_bottom_keyboard, shop_ui
from database.db import add_user, user_exists, add_bonus, update_referral_bonuses, get_referral_message
from utils.helpers import get_timer_status



DB_PATH = "database/users.db"
def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

router = Router()

@router.message(Command("menu"))
@router.message(Command("start"))
async def start_handler(message: Message):

    user_id = message.from_user.id

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

async def safe_edit_or_replace(callback: CallbackQuery, new_text: str, reply_markup=None, parse_mode=None):
    msg: Message = callback.message

    try:
        if msg.content_type == "text":
            await msg.edit_text(new_text, reply_markup=reply_markup, parse_mode=parse_mode)
        elif msg.content_type in {"photo", "video", "document", "audio", "voice"}:
            try:
                await msg.edit_caption(new_text, reply_markup=reply_markup, parse_mode=parse_mode)
            except TelegramBadRequest:
                await msg.delete()
                await callback.message.answer(new_text, reply_markup=reply_markup, parse_mode=parse_mode)
        else:
            await msg.delete()
            await callback.message.answer(new_text, reply_markup=reply_markup, parse_mode=parse_mode)
    except TelegramBadRequest:
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


@router.callback_query(F.data == "main_profile")
async def handle_profile_button(callback: CallbackQuery):
    user_id = callback.from_user.id
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