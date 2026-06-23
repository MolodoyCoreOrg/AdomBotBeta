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

from database.db import get_pidaraz_number, claim_pidaraz_number, get_all_pidarazs
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
        text += f"✅ Твой номер: <b>Пидараз {current_num}</b>\n\nТы можешь линковать свой статус в любых чатах, просто напиши юзернейм бота!"
    else:
        text += f"У тебя ещё нет номера. Доступно слотов: {MAX_PIDARAZ_SLOTS}.\nВыбери свой уникальный номер навсегда!"

    await callback.message.edit_text(text, reply_markup=pidaraz_ui(), parse_mode="HTML")
    await callback.answer()

# ================== БРОНЬ НОМЕРА ==================

# Перехватываем диплинк с кнопки из инлайн режима (если юзер нажал "Выбрать номер" в другом чате)
@router.message(CommandStart(deep_link="pick_pidaraz"))
async def start_pick_pidaraz_deeplink(message: Message, state: FSMContext):
    await state.set_state(PidarazState.waiting_for_number)
    await message.answer(
        "🔥 <b>Добро пожаловать в Пересчет!</b>\n\n"
        f"Напиши в чат число от 1 до {MAX_PIDARAZ_SLOTS}, чтобы забронировать его за собой.\n"
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
        f"🔢 Напиши в чат число от 1 до {MAX_PIDARAZ_SLOTS}, чтобы забронировать номер.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Отмена", callback_data="pidaraz_menu")]])
    )
    await callback.answer()

@router.message(StateFilter(PidarazState.waiting_for_number))
async def process_number_input(message: Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("❌ Пожалуйста, отправь только число.")
        return
        
    number = int(message.text)
    if number < 1 or number > MAX_PIDARAZ_SLOTS:
        await message.answer(f"❌ Число должно быть от 1 до {MAX_PIDARAZ_SLOTS}.")
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
        
    await callback.answer("Принято!", show_alert=False)
    await callback.message.edit_text(f"✅ Утренний пересчет пройден!\nПидараз {pid_number} на связи!")

async def daily_pidaraz_check(bot: Bot):
    while True:
        now = datetime.datetime.now()
        target = now.replace(hour=10, minute=0, second=0, microsecond=0)
        
        if now >= target:
            target += datetime.timedelta(days=1)
            
        wait_seconds = (target - now).total_seconds()
        await asyncio.sleep(wait_seconds)
        
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
            
            # БЕЗОПАСНАЯ ЗАДЕРЖКА: 2 секунды между сообщениями
            # (ровно 30 сообщений в минуту)
            await asyncio.sleep(2)