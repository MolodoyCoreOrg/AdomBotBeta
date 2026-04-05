# ADMIN_IDS = {1114626593, 347632821, 462179661, 776301286}  # тут твои ID админов
import sqlite3, math, json, os

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardButton, InlineKeyboardMarkup

from utils.config import ADMINS_LIST, RARITY_WEIGHTS
from database.db import update_member_cards, update_skill_cards

router = Router()

DB_PATH = "database/users.db"

def connect():
    return sqlite3.connect(DB_PATH)

# === СПИСОК ПОЛЬЗОВАТЕЛЕЙ USERS ===

USERS_PER_PAGE = 10


def get_users(offset=0, limit=10):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT user_number, user_id, username FROM users ORDER BY user_number ASC LIMIT ? OFFSET ?", (limit, offset))
    users = cursor.fetchall()
    conn.close()
    return users


def get_total_users():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    total = cursor.fetchone()[0]
    conn.close()
    return total


def get_user_info(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT user_number, user_id, username, registered_at FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user


def build_users_keyboard(page):
    offset = (page - 1) * USERS_PER_PAGE
    users = get_users(offset, USERS_PER_PAGE)
    total = get_total_users()
    total_pages = math.ceil(total / USERS_PER_PAGE)

    buttons = [
        [InlineKeyboardButton(text=f"{num}. @{username} ({uid})", callback_data=f"view_user:{uid}")]
        for num, uid, username in users
    ]

    navigation = [
        InlineKeyboardButton(text="⬅️", callback_data=f"users_page:{page - 1}" if page > 1 else "noop"),
        InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="noop"),
        InlineKeyboardButton(text="➡️", callback_data=f"users_page:{page + 1}" if page < total_pages else "noop"),
    ]

    buttons.append(navigation)
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(F.text == "/users")
async def handle_users_command(message: Message):
    # проверка на админа (admin_lvl > 0)
    user_id = message.from_user.id
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT admin_lvl FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if not row or row[0] <= 0:
        await message.answer("У тебя нет прав для этой команды.")
        return

    keyboard = build_users_keyboard(page=1)
    await message.answer("Пользователи бота:", reply_markup=keyboard)


@router.callback_query(F.data.startswith("users_page:"))
async def handle_users_pagination(callback: CallbackQuery):
    page = int(callback.data.split(":")[1])
    keyboard = build_users_keyboard(page)
    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("view_user:"))
async def handle_view_user(callback: CallbackQuery):
    user_id = int(callback.data.split(":")[1])
    user = get_user_info(user_id)
    if not user:
        await callback.answer("Пользователь не найден", show_alert=True)
        return

    number, uid, username, registered_at = user
    # Заглушка по приглашенным друзьям
    invited_count = 0

    text = (
        f"<b>Информация о пользователе</b>\n"
        f"🔢 Номер: {number}\n"
        f"👤 Username: @{username}\n"
        f"🆔 ID: {uid}\n"
        f"📅 Зарегистрирован: {registered_at}\n"
        f"👥 Приглашено друзей: {invited_count}"
    )

    buttons = [
        [InlineKeyboardButton(text="Управление пользователем", callback_data=f"manage_user:{uid}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="users_page:1")],
    ]

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await callback.answer()


@router.callback_query(F.data.startswith("manage_user:"))
async def handle_manage_user(callback: CallbackQuery):
    user_id = int(callback.data.split(":")[1])
    buttons = [
        [InlineKeyboardButton(text="❌ Удалить пользователя", callback_data=f"delete_user:{user_id}")],
        [InlineKeyboardButton(text="🚫 Забанить пользователя", callback_data=f"ban_user:{user_id}")],
        [InlineKeyboardButton(text="🗑 Удалить все карты участников", callback_data=f"clear_member_cards:{user_id}")],
        [InlineKeyboardButton(text="🧹 Удалить все суперспособности", callback_data=f"clear_skill_cards:{user_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"view_user:{user_id}")]
    ]

    await callback.message.edit_text("Выберите действие:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await callback.answer()


@router.callback_query(F.data == "noop")
async def noop_callback(callback: CallbackQuery):
    await callback.answer()

@router.callback_query(F.data.startswith("delete_user:"))
async def delete_user(callback: CallbackQuery):
    user_id = int(callback.data.split(":")[1])

    # Удаление из таблицы users
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

    # Удаление из JSON-файлов (если они у тебя есть)
    remove_user_from_timer_files(user_id)
    remove_user_from_bonuses(user_id)

    await callback.message.edit_text("✅ Пользователь полностью удалён.")

@router.callback_query(F.data.startswith("ban_user:"))
async def ban_user(callback: CallbackQuery):
    user_id = int(callback.data.split(":")[1])
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET banned = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    await callback.message.edit_text("🚫 Пользователь забанен.")



@router.callback_query(F.data.startswith("clear_member_cards:"))
async def clear_member_cards(callback: CallbackQuery):
    user_id = int(callback.data.split(":")[1])
    update_member_cards(user_id, {})  # Пустой словарь = очистка
    await callback.message.edit_text("🗑 Все карточки участников удалены.")


@router.callback_query(F.data.startswith("clear_skill_cards:"))
async def clear_skill_cards(callback: CallbackQuery):
    user_id = int(callback.data.split(":")[1])
    update_skill_cards(user_id, {})
    await callback.message.edit_text("🧹 Все суперспособности удалены.")

@router.callback_query(F.data.startswith("view_user:"))
async def view_user_back(callback: CallbackQuery):
    user_id = int(callback.data.split(":")[1])
    await handle_view_user(callback, user_id)









def remove_user_from_timer_files(user_id: int):
    paths = [
        "data/table/timer_members_card.json",
        "data/table/timer_skills_card.json"
    ]
    for path in paths:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if str(user_id) in data:
                del data[str(user_id)]
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)



def remove_user_from_bonuses(user_id: int):
    path = "data/table/bonuses.json"
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if str(user_id) in data:
            del data[str(user_id)]
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)