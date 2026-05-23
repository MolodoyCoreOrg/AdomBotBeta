import sqlite3
from datetime import datetime, timedelta
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.enums import ParseMode

from database.db import connect

router = Router()

DB_PATH = "database/users.db"
MAX_PIDARAZ_NUMBERS = 100  # Initial limit, can be expanded later

# ===== DATABASE FUNCTIONS =====

def create_pidoraz_table():
    """Create table for pidoraz numbers if it doesn't exist."""
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS pidoraz_numbers (
                user_id INTEGER PRIMARY KEY,
                pidoraz_number INTEGER UNIQUE NOT NULL,
                username TEXT,
                first_name TEXT,
                assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_notified TIMESTAMP,
                notified_today INTEGER DEFAULT 0
            )
        """)
        conn.commit()

def get_user_pidoraz_number(user_id: int) -> int | None:
    """Get user's assigned pidoraz number."""
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT pidoraz_number FROM pidoraz_numbers WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        return row[0] if row else None

def get_username_by_pidoraz_number(number: int) -> str | None:
    """Get username by pidoraz number."""
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT username FROM pidoraz_numbers WHERE pidoraz_number = ?", (number,))
        row = cur.fetchone()
        return row[0] if row else None

def get_all_pidoraz_numbers() -> list:
    """Get all assigned pidoraz numbers with user info."""
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT pidoraz_number, username, first_name, assigned_at 
            FROM pidoraz_numbers 
            ORDER BY pidoraz_number
        """)
        return cur.fetchall()

def get_available_numbers() -> list:
    """Get list of available (not taken) numbers."""
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT pidoraz_number FROM pidoraz_numbers")
        taken = {row[0] for row in cur.fetchall()}
        return [n for n in range(1, MAX_PIDARAZ_NUMBERS + 1) if n not in taken]

def assign_pidoraz_number(user_id: int, number: int, username: str, first_name: str) -> bool:
    """Assign a pidoraz number to a user. Returns False if number is already taken."""
    try:
        with connect() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO pidoraz_numbers (user_id, pidoraz_number, username, first_name, assigned_at)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, number, username, first_name, datetime.now()))
            conn.commit()
            return True
    except sqlite3.IntegrityError:
        return False

def update_notification_status(user_id: int):
    """Update last notification timestamp for user."""
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("""
            UPDATE pidoraz_numbers 
            SET last_notified = ?, notified_today = 1
            WHERE user_id = ?
        """, (datetime.now(), user_id))
        conn.commit()

def reset_daily_notifications():
    """Reset daily notification status for all users (call once per day)."""
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE pidoraz_numbers SET notified_today = 0")
        conn.commit()

def get_users_to_notify() -> list:
    """Get list of users who haven't been notified today."""
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT user_id, pidoraz_number, username, first_name 
            FROM pidoraz_numbers 
            WHERE notified_today = 0
        """)
        return cur.fetchall()

# ===== INLINE KEYBOARDS =====

def get_pidoraz_main_keyboard() -> InlineKeyboardBuilder:
    """Main keyboard for pidoraz bot."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔢 Выбрать номер", callback_data="pidoraz_select_number"),
        InlineKeyboardButton(text="📋 Список пидаразов", callback_data="pidoraz_list")
    )
    builder.row(
        InlineKeyboardButton(text="ℹ️ Мой номер", callback_data="pidoraz_my_number")
    )
    return builder

def get_available_numbers_keyboard(page: int = 0) -> InlineKeyboardBuilder:
    """Keyboard with available numbers (paginated)."""
    available = get_available_numbers()
    per_page = 20
    total_pages = (len(available) + per_page - 1) // per_page
    
    start = page * per_page
    end = start + per_page
    page_numbers = available[start:end]
    
    builder = InlineKeyboardBuilder()
    
    for num in page_numbers:
        builder.row(InlineKeyboardButton(text=f"№{num}", callback_data=f"pidoraz_assign_{num}"))
    
    # Pagination
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"pidoraz_page_{page-1}"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="Вперед ➡️", callback_data=f"pidoraz_page_{page+1}"))
    
    if nav_buttons:
        builder.row(*nav_buttons)
    
    builder.row(InlineKeyboardButton(text="↩️ Назад", callback_data="pidoraz_back"))
    return builder

def get_confirm_number_keyboard(number: int) -> InlineKeyboardBuilder:
    """Keyboard to confirm number selection."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=f"✅ Подтвердить №{number}", callback_data=f"pidoraz_confirm_{number}"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="pidoraz_select_number")
    )
    return builder

def get_notify_keyboard(number: int) -> InlineKeyboardBuilder:
    """Keyboard for daily notification."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=f"📣 Пидараз {number} на связи", callback_data=f"pidoraz_notify_{number}")
    )
    return builder

def get_my_number_keyboard(number: int) -> InlineKeyboardBuilder:
    """Keyboard when viewing own number."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📣 Сообщить всем", callback_data=f"pidoraz_notify_{number}")
    )
    builder.row(
        InlineKeyboardButton(text="↩️ Назад", callback_data="pidoraz_back")
    )
    return builder

# ===== HANDLERS =====

@router.callback_query(F.data == "pidoraz_main")
async def handle_pidoraz_main(callback: CallbackQuery):
    """Main menu for pidoraz feature."""
    user_id = callback.from_user.id
    username = callback.from_user.username or ""
    first_name = callback.from_user.first_name or ""
    
    assigned_number = get_user_pidoraz_number(user_id)
    
    if assigned_number:
        text = (
            f"<b>Твой номер:</b> <b>{assigned_number}</b>\n\n"
            f"Ты закреплен за этим номером навсегда! 🔒\n\n"
            f"Используй @CuCbKu_gg_bot в чатах чтобы показать свой номер."
        )
        reply_markup = get_my_number_keyboard(assigned_number)
    else:
        text = (
            "<b>🔢 Пересчет пидаразов</b>\n\n"
            "Выбери свой уникальный номер от 1 до 100!\n"
            "⚠️ Номер выбирается один раз и изменить его нельзя!\n\n"
            f"Свободно номеров: <b>{len(get_available_numbers())}</b> из {MAX_PIDARAZ_NUMBERS}"
        )
        reply_markup = get_pidoraz_main_keyboard()
    
    await callback.message.edit_text(text, reply_markup=reply_markup.as_markup(), parse_mode=ParseMode.HTML)
    await callback.answer()

@router.callback_query(F.data == "pidoraz_select_number")
async def handle_select_number(callback: CallbackQuery):
    """Show available numbers to select."""
    user_id = callback.from_user.id
    
    # Check if user already has a number
    if get_user_pidoraz_number(user_id):
        await callback.answer("❌ У тебя уже есть номер!", show_alert=True)
        return
    
    available = get_available_numbers()
    if not available:
        await callback.answer("❌ Все номера заняты!", show_alert=True)
        return
    
    text = (
        "<b>Выбери свободный номер:</b>\n\n"
        f"Доступно: <b>{len(available)}</b> из {MAX_PIDARAZ_NUMBERS}\n"
        "Нажми на номер чтобы выбрать его."
    )
    
    reply_markup = get_available_numbers_keyboard(0)
    await callback.message.edit_text(text, reply_markup=reply_markup.as_markup(), parse_mode=ParseMode.HTML)
    await callback.answer()

@router.callback_query(F.data.startswith("pidoraz_page_"))
async def handle_page_navigation(callback: CallbackQuery):
    """Navigate through pages of available numbers."""
    page = int(callback.data.split("_")[-1])
    
    available = get_available_numbers()
    per_page = 20
    total_pages = (len(available) + per_page - 1) // per_page
    
    start = page * per_page
    end = start + per_page
    page_numbers = available[start:end]
    
    text = (
        "<b>Выбери свободный номер:</b>\n\n"
        f"Страница {page + 1} из {total_pages}\n"
        f"Доступно: <b>{len(available)}</b> из {MAX_PIDARAZ_NUMBERS}"
    )
    
    reply_markup = get_available_numbers_keyboard(page)
    await callback.message.edit_text(text, reply_markup=reply_markup.as_markup(), parse_mode=ParseMode.HTML)
    await callback.answer()

@router.callback_query(F.data.startswith("pidoraz_assign_"))
async def handle_assign_number(callback: CallbackQuery):
    """Handle number selection."""
    user_id = callback.from_user.id
    number = int(callback.data.split("_")[-1])
    
    # Double check if user already has a number
    if get_user_pidoraz_number(user_id):
        await callback.answer("❌ У тебя уже есть номер!", show_alert=True)
        return
    
    # Check if number is still available
    if number not in get_available_numbers():
        await callback.answer("❌ Этот номер уже занят!", show_alert=True)
        return
    
    text = (
        f"<b>Подтверждение выбора</b>\n\n"
        f"Ты выбрал номер <b>№{number}</b>\n"
        "⚠️ Помни: изменить номер будет нельзя!"
    )
    
    reply_markup = get_confirm_number_keyboard(number)
    await callback.message.edit_text(text, reply_markup=reply_markup.as_markup(), parse_mode=ParseMode.HTML)
    await callback.answer()

@router.callback_query(F.data.startswith("pidoraz_confirm_"))
async def handle_confirm_number(callback: CallbackQuery):
    """Confirm and assign the number."""
    user_id = callback.from_user.id
    number = int(callback.data.split("_")[-1])
    username = callback.from_user.username or "без_username"
    first_name = callback.from_user.first_name or "Аноним"
    
    # Final check
    if get_user_pidoraz_number(user_id):
        await callback.answer("❌ У тебя уже есть номер!", show_alert=True)
        return
    
    success = assign_pidoraz_number(user_id, number, username, first_name)
    
    if success:
        text = (
            f"🎉 <b>Поздравляю!</b>\n\n"
            f"Теперь ты <b>Пидараз №{number}</b>!\n\n"
            f"Этот номер закреплен за тобой навсегда.\n"
            f"Используй @CuCbKu_gg_bot в чатах чтобы показать свой номер."
        )
        reply_markup = get_my_number_keyboard(number)
        await callback.message.edit_text(text, reply_markup=reply_markup.as_markup(), parse_mode=ParseMode.HTML)
        
        # Send welcome message
        await callback.message.answer(
            f"🔥 Добро пожаловать в клуб, Пидараз #{number}!"
        )
    else:
        await callback.answer("❌ Не удалось закрепить номер. Попробуй другой.", show_alert=True)
        await handle_select_number(callback)
    
    await callback.answer()

@router.callback_query(F.data == "pidoraz_list")
async def handle_pidoraz_list(callback: CallbackQuery):
    """Show list of all pidoraz numbers."""
    all_numbers = get_all_pidoraz_numbers()
    
    if not all_numbers:
        text = "📋 <b>Список пидаразов</b>\n\nПока никто не выбрал номер. Будь первым!"
    else:
        text = "📋 <b>Список пидаразов</b>\n\n"
        text += f"Всего: <b>{len(all_numbers)}</b> из {MAX_PIDARAZ_NUMBERS}\n\n"
        
        for num, username, first_name, assigned_at in all_numbers:
            if username:
                link = f"https://t.me/{username}"
                text += f"<b>Пидараз {num}</b> - <a href='{link}'>{first_name or username}</a>\n"
            else:
                text += f"<b>Пидараз {num}</b> - {first_name or 'Аноним'}\n"
    
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="↩️ Назад", callback_data="pidoraz_back"))
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode=ParseMode.HTML)
    await callback.answer()

@router.callback_query(F.data == "pidoraz_my_number")
async def handle_my_number(callback: CallbackQuery):
    """Show user's own number."""
    user_id = callback.from_user.id
    number = get_user_pidoraz_number(user_id)
    
    if not number:
        text = (
            "❌ <b>У тебя нет номера</b>\n\n"
            "Ты пока что <b>безномерный пидараз</b>.\n"
            "Выбери свой уникальный номер!"
        )
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="🔢 Выбрать номер", callback_data="pidoraz_select_number"))
        builder.row(InlineKeyboardButton(text="↩️ Назад", callback_data="pidoraz_back"))
        await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode=ParseMode.HTML)
    else:
        text = (
            f"<b>Твой номер:</b> <b>{number}</b>\n\n"
            f"Ты <b>Пидараз №{number}</b>!"
        )
        reply_markup = get_my_number_keyboard(number)
        await callback.message.edit_text(text, reply_markup=reply_markup.as_markup(), parse_mode=ParseMode.HTML)
    
    await callback.answer()

@router.callback_query(F.data.startswith("pidoraz_notify_"))
async def handle_notify(callback: CallbackQuery):
    """Send notification to all users about this pidoraz number."""
    user_id = callback.from_user.id
    number = int(callback.data.split("_")[-1])
    
    # Verify user owns this number
    if get_user_pidoraz_number(user_id) != number:
        await callback.answer("❌ Это не твой номер!", show_alert=True)
        return
    
    username = callback.from_user.username or ""
    first_name = callback.from_user.first_name or ""
    
    # Get all users with pidoraz numbers
    all_users = get_all_pidoraz_numbers()
    
    sent_count = 0
    failed_count = 0
    
    for num, uname, fname, _ in all_users:
        try:
            # Find user_id for this pidoraz number
            with connect() as conn:
                cur = conn.cursor()
                cur.execute("SELECT user_id FROM pidoraz_numbers WHERE pidoraz_number = ?", (num,))
                row = cur.fetchone()
                if row:
                    target_user_id = row[0]
                    if username:
                        msg_text = f"📣 <b>Пидараз {number} ({first_name}) на связи!</b>\n\n<a href='https://t.me/{username}'>{first_name or username}</a> подтверждает свой статус!"
                    else:
                        msg_text = f"📣 <b>Пидараз {number} на связи!</b>"
                    
                    await callback.message.bot.send_message(
                        target_user_id,
                        msg_text,
                        parse_mode=ParseMode.HTML
                    )
                    sent_count += 1
        except Exception as e:
            print(f"Failed to notify user {num}: {e}")
            failed_count += 1
    
    await callback.answer(f"Отправлено {sent_count} уведомлений!", show_alert=True)
    
    # Update notification status
    update_notification_status(user_id)

@router.callback_query(F.data == "pidoraz_back")
async def handle_back(callback: CallbackQuery):
    """Go back to main menu."""
    from handlers.menu import safe_edit_or_replace
    
    user_id = callback.from_user.id
    assigned_number = get_user_pidoraz_number(user_id)
    
    if assigned_number:
        text = (
            f"<b>Твой номер:</b> <b>{assigned_number}</b>\n\n"
            f"Ты закреплен за этим номером навсегда! 🔒"
        )
        reply_markup = get_my_number_keyboard(assigned_number)
    else:
        text = (
            "<b>🔢 Пересчет пидаразов</b>\n\n"
            "Выбери свой уникальный номер от 1 до 100!\n"
            "⚠️ Номер выбирается один раз и изменить его нельзя!"
        )
        reply_markup = get_pidoraz_main_keyboard()
    
    await callback.message.edit_text(text, reply_markup=reply_markup.as_markup(), parse_mode=ParseMode.HTML)
    await callback.answer()

# ===== COMMAND HANDLERS =====

@router.message(Command("pidaraz"))
@router.message(Command("pidoraz"))
async def cmd_pidoraz(message: Message):
    """Command to view pidoraz status."""
    user_id = message.from_user.id
    number = get_user_pidoraz_number(user_id)
    
    if number:
        text = (
            f"🔥 <b>Ты Пидараз №{number}</b>!\n\n"
            f"Этот номер закреплен за тобой навсегда."
        )
    else:
        text = (
            "😔 <b>Ты безномерный пидараз</b>.\n\n"
            "Запусти бота и выбери свой номер!"
        )
    
    await message.answer(text, parse_mode=ParseMode.HTML)

# ===== MENTION HANDLER =====

@router.message(F.text.regexp(r"@CuCbKu_gg_bot"))
async def handle_mention(message: Message):
    """Handle @mention of the bot in chats."""
    user_id = message.from_user.id
    number = get_user_pidoraz_number(user_id)
    username = message.from_user.username or ""
    first_name = message.from_user.first_name or ""
    
    if number:
        if username:
            text = f"🔥 <b>Пидараз {number} на связи!</b>\n\n<a href='https://t.me/{username}'>{first_name}</a> подтверждает свой статус!"
        else:
            text = f"🔥 <b>Пидараз {number} на связи!</b>\n\n{first_name} подтверждает свой статус!"
    else:
        text = "😔 <b>Я безномерный пидараз</b>.\n\nЕще не выбрал свой номер!"
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="🔢 Выбрать номер", url="https://t.me/CuCbKu_gg_bot"))
        await message.answer(text, reply_markup=builder.as_markup(), parse_mode=ParseMode.HTML)
        return
    
    await message.answer(text, parse_mode=ParseMode.HTML)

# ===== DAILY NOTIFICATION TASK =====

async def send_daily_notifications(bot: Bot):
    """Send daily notifications to all pidoraz users."""
    users = get_users_to_notify()
    
    for user_id, number, username, first_name in users:
        try:
            text = f"📢 <b>Пидараз {number} на связи???</b>\n\nПодтверди свой статус!"
            reply_markup = get_notify_keyboard(number)
            
            await bot.send_message(
                user_id,
                text,
                reply_markup=reply_markup.as_markup(),
                parse_mode=ParseMode.HTML
            )
            
            update_notification_status(user_id)
        except Exception as e:
            print(f"Failed to notify user {user_id}: {e}")
    
    # Reset daily status after sending
    reset_daily_notifications()

# ===== INITIALIZATION =====

def init_pidoraz_feature():
    """Initialize the pidoraz feature."""
    create_pidoraz_table()
