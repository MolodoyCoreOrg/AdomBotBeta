import asyncio
import datetime
from aiogram import Router, F, Bot
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message, CallbackQuery, InlineQuery, InlineQueryResultArticle, 
    InputTextMessageContent, InlineKeyboardMarkup, InlineKeyboardButton
)

from database.db import (
    get_pidaraz_number,
    claim_pidaraz_number,
    get_all_pidarazs,
    get_pidaraz_stats,
    mark_pidaraz_confirmed,
)
from handlers.keyboard import pidaraz_ui

router = Router()

MAX_PIDARAZ_SLOTS = 100

class PidarazState(StatesGroup):
    waiting_for_number = State()

# ================== ОБРАБОТКА МЕНЮ ==================

@router.callback_query(F.data == "pidaraz_menu")
async def show_pidaraz_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    user_id = callback.from_user.id
    current_num = get_pidaraz_number(user_id)
    
    text = "🎪 <b>Пересчет пидаразов</b>\n\n"
    if current_num:
        stats = get_pidaraz_stats(user_id)
        text += (
            f"✅ Твой номер: <b>Пидараз {current_num}</b>\n"
            f"🔥 Стрик: <b>{stats['streak_current']}</b> (лучший: <b>{stats['best_streak']}</b>)\n\n"
            "Ты можешь линковать свой статус в любых чатах, просто напиши юзернейм бота!"
        )
    else:
        text += f"У тебя ещё нет номера. Всего доступно {MAX_PIDARAZ_SLOTS} уникальных слотов.\nВыбери свой любимый номер до 4 символов навсегда!"

    await callback.message.edit_text(text, reply_markup=pidaraz_ui(), parse_mode="HTML")
    await callback.answer()

# ================== БРОНЬ НОМЕРА ==================

# Перехватываем диплинк с кнопки из инлайн режима (если юзер нажал "Выбрать номер" в другом чате)
@router.message(CommandStart(deep_link="pick_pidaraz"))
async def start_pick_pidaraz_deeplink(message: Message, state: FSMContext):
    await state.set_state(PidarazState.waiting_for_number)
    await message.answer(
        "🔥 <b>Добро пожаловать в Пересчет!</b>\n\n"
        f"Напиши в чат любое число до 4 цифр (например: 7, 228, 666, 9999), чтобы забронировать его за собой.\n"
        f"Всего доступно {MAX_PIDARAZ_SLOTS} слотов!\n"
        "⚠️ <b>Внимание:</b> номер выбирается ОДИН раз и навсегда!",
        parse_mode="HTML"
    )

@router.callback_query(F.data == "pidaraz_pick")
async def ask_for_number(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    current_num = get_pidaraz_number(user_id)
    
    if current_num:
        await callback.answer(f"Ты уже Пидараз {current_num}! Изменить номер нельзя.", show_alert=True)
        return

    await state.set_state(PidarazState.waiting_for_number)
    await callback.message.edit_text(
        "🔢 Напиши в чат любое число от 1 до 4 знаков (например: 1, 7, 228, 666, 9999), чтобы забронировать номер.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Отмена", callback_data="pidaraz_menu")]])
    )
    await callback.answer()

@router.message(StateFilter(PidarazState.waiting_for_number))
async def process_number_input(message: Message, state: FSMContext):
    if not message.text or not message.text.isdigit():
        await message.answer("❌ Пожалуйста, отправь только число (например: 7, 228, 666).")
        return
        
    number = int(message.text)
    
    # Проверка на пасхалку 1488
    if number == 1488:
        await message.answer(
            "вы че натсы???\nhttps://youtu.be/UkonY2vBMHg?si=_ll1NUbGOyaScoiZ"
        )
        return

    # Проверка на ограничение в 4 символа (и положительность числа)
    if number < 1 or number > 9999 or len(message.text.strip()) > 4:
        await message.answer("❌ Число должно состоять от 1 до 4 цифр (от 1 до 9999).")
        return
        
    user_id = message.from_user.id
    username = message.from_user.username or ""
    first_name = message.from_user.first_name or "Без имени"
    
    success, msg = claim_pidaraz_number(user_id, number, username, first_name)
    if success:
        bot_info = await message.bot.me()
        await message.answer(
            f"✅ Поздравляю! Теперь ты <b>Пидараз {number}</b> навсегда!\n\n"
            f"В любом чате напиши <code>@{bot_info.username}</code> чтобы гордо заявить о себе!",
            parse_mode="HTML"
        )
        await state.clear()
    else:
        await message.answer(f"❌ {msg}\nПопробуй написать другое число.")

# ================== СПИСОК ПИДАРАЗОВ ==================

@router.callback_query(F.data == "pidaraz_list")
async def show_pidaraz_list(callback: CallbackQuery):
    users = get_all_pidarazs()
    if not users:
        await callback.answer("Список пока пуст!", show_alert=True)
        return
        
    text = f"📋 <b>Священный список (Занято {len(users)}/{MAX_PIDARAZ_SLOTS}):</b>\n\n"
    for u in users:
        name = f"@{u['username']}" if u['username'] else u['first_name']
        text += f"<b>{u['pid_number']}</b>. {name}\n"
        
    # Кнопка назад в меню пидаразов
    markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="↪️ Назад", callback_data="pidaraz_menu")]])
    await callback.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
    await callback.answer()

# ================== INLINE РЕЖИМ (@bot_username) ==================

@router.inline_query()
async def inline_pidaraz_query(inline_query: InlineQuery):
    user_id = inline_query.from_user.id
    pid_number = get_pidaraz_number(user_id)
    bot_info = await inline_query.bot.me()
    
    if pid_number:
        text = f"Пидараз {pid_number} на связи! 🫡"
        result = InlineQueryResultArticle(
            id=f"pid_{user_id}",
            title=f"Я Пидараз {pid_number}",
            description="Отправить свой статус в чат",
            input_message_content=InputTextMessageContent(message_text=text)
        )
    else:
        text = "Я безномерный пидараз 😔"
        markup = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="Выбрать номер", url=f"https://t.me/{bot_info.username}?start=pick_pidaraz")
        ]])
        result = InlineQueryResultArticle(
            id=f"nopid_{user_id}",
            title="Я безномерный пидараз",
            description="У тебя еще нет номера! Нажми, чтобы выбрать.",
            input_message_content=InputTextMessageContent(message_text=text),
            reply_markup=markup
        )
    
    await inline_query.answer([result], cache_time=1, is_personal=True)

# ================== ЕЖЕДНЕВНАЯ РАССЫЛКА ==================

@router.callback_query(F.data == "pidaraz_here")
async def pidaraz_here_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    pid_number = get_pidaraz_number(user_id)
    
    if not pid_number:
        await callback.answer("У тебя нет номера!", show_alert=True)
        return

    stats = mark_pidaraz_confirmed(user_id)
    if stats is False:
        stats = get_pidaraz_stats(user_id)

    await callback.answer("Принято!", show_alert=False)
    await callback.message.edit_text(
        f"✅ Утренний пересчет пройден!\n"
        f"Пидараз {pid_number} на связи!\n"
        f"🔥 Стрик: {stats['streak_current']} (лучший: {stats['best_streak']})"
    )

async def send_pidaraz_check_requests(bot: Bot):
    users = get_all_pidarazs()
    for u in users:
        try:
            markup = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text=f"Пидараз {u['pid_number']} на связи", callback_data="pidaraz_here")
            ]])
            await bot.send_message(
                chat_id=u['user_id'],
                text=f"Утренний пересчет! Пидараз {u['pid_number']} на связи???",
                reply_markup=markup
            )
        except Exception:
            pass

        await asyncio.sleep(2)


async def daily_pidaraz_check(bot: Bot):
    while True:
        now = datetime.datetime.now()
        target = now.replace(hour=10, minute=0, second=0, microsecond=0)
        
        if now >= target:
            target += datetime.timedelta(days=1)
            
        wait_seconds = (target - now).total_seconds()
        await asyncio.sleep(wait_seconds)
        
        await send_pidaraz_check_requests(bot)