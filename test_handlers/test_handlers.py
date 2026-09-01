import os, sqlite3, asyncio, random, json, datetime
from datetime import date

from aiogram import types, Router, F, Bot
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder, InlineKeyboardButton
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from database.db import connect

from utils.config import ADMINS_LIST, TOKEN

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

router = Router()






@router.message(Command("test_notify"))
async def test_notify(message: Message):
    if message.from_user.id not in ADMINS_LIST:
        await message.answer("❌ У вас нет доступа к этой команде.")
        return
    
    from handlers.notify import get_notify_skill_keyboard, send_reminder
    await send_reminder(
        "🧪 Тестовое уведомление: открой суперспособность!",
        reply_markup=get_notify_skill_keyboard()
    )
    await message.answer("✅ Тестовое оповещение отправлено.")





@router.message(Command("test_max_roulette"))
async def notify_max_roulette(message: Message, bot: Bot):
    if message.from_user.id not in ADMINS_LIST:
        await message.answer("❌ У вас нет доступа к этой команде.")
        return
    
    from handlers.roulette import MAX_SPINS
    while True:
        with connect() as conn:
            cursor = conn.cursor()
            # выбираем только тех, у кого достаточно спинов и notified_max = 0
            cursor.execute("""
                SELECT user_id, roulette_count FROM roulette_user
                WHERE roulette_count >= ? AND notified_max = 0
            """, (MAX_SPINS,))
            users_to_notify = cursor.fetchall()

        for row in users_to_notify:
            user_id = row["user_id"]
            count = row["roulette_count"]

            try:
                await bot.send_message(
                    chat_id=user_id,
                    text=f"🎰 У тебя накопилось {count} рулеток! Самое время испытать удачу!"
                )
                print(f"[notify_max_roulette] Отправлено уведомление пользователю {user_id} о максимуме рулеток.")

                # обновляем notified_max = 1
                with connect() as conn:
                    conn.execute(
                        "UPDATE roulette_user SET notified_max = 1 WHERE user_id = ?",
                        (user_id,)
                    )
                    conn.commit()

            except Exception as e:
                print(f"[notify_max_roulette] Не удалось отправить пользователю {user_id}: {e}")
                return

MAX_PER_SECOND = 25

async def send_reminder(text: str, reply_markup=None):
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT user_id FROM users")
        all_users = [row[0] for row in cur.fetchall()]

    # разбиваем пользователей на батчи по 25
    for i in range(0, len(all_users), MAX_PER_SECOND):
        batch = all_users[i:i + MAX_PER_SECOND]

        tasks = []
        for user_id in batch:
            tasks.append(_safe_send(user_id, text, reply_markup))

        # параллельно отправляем 25 сообщений
        await asyncio.gather(*tasks, return_exceptions=True)

        # пауза 1 секунда перед следующей пачкой
        await asyncio.sleep(1)


async def _safe_send(user_id: int, text: str, reply_markup=None):
    try:
        await bot.send_message(user_id, text, reply_markup=reply_markup)
    except Exception as e:
        # сюда будет падать FloodWait, если даже батч превысит лимит
        print(f"Не удалось отправить {user_id}: {e}")



last_skill_notify_date = None

def get_notify_skill_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(
            InlineKeyboardButton(text="🎴 Открыть карту", callback_data="draw_card"),
        )
    return builder.as_markup()

REMINDER_HOUR = 19
REMINDER_MINUTE = 0

@router.message(Command("test_notify_skill"))
async def test_notify_skill(event):
    global last_skill_notify_date
    now = datetime.datetime.now(datetime.timezone.utc)
    today_str = now.strftime("%Y-%m-%d")

    # Проверка, отправлялось ли уведомление сегодня
    if last_skill_notify_date != today_str:
        await send_reminder(
            "🎴 Пора открыть карту из общей колоды!",
            reply_markup=get_notify_skill_keyboard()
        )
        last_skill_notify_date = today_str
        await event.answer("✅ Напоминание отправлено!")
    else:
        await event.answer("ℹ️ Напоминание уже было сегодня.")