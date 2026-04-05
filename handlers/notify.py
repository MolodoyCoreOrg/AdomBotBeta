import asyncio
from datetime import datetime

from aiogram import Bot
from aiogram.utils.keyboard import InlineKeyboardButton, InlineKeyboardBuilder
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from utils.config import TOKEN  # Твой токен
from database.db import connect, get_all_user_ids, load_roulette_data, save_roulette_data

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

MAX_SPINS = 10

# Глобальные переменные для хранения даты последнего уведомления
last_member_notify_date = None
last_skill_notify_date = None

def get_notify_member_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(
            InlineKeyboardButton(text="👥 Карточка участника", callback_data="draw_member"),
        )
    return builder.as_markup()

async def notify_member_card_reminder():
    global last_member_notify_date
    while True:
        now = datetime.utcnow()
        today_str = now.strftime("%Y-%m-%d")
        weekday = now.weekday()  # понедельник=0 ... воскресенье=6

        # Напоминаем только в воскресенье в 19:00 UTC
        if weekday == 6 and now.hour == 19:
            if last_member_notify_date != today_str:
                await send_reminder("✨ Пора открыть карточку участника!", reply_markup = get_notify_member_keyboard())
                last_member_notify_date = today_str
        await asyncio.sleep(60)



def get_notify_skill_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(
            InlineKeyboardButton(text="🃏 Суперспособность", callback_data="draw_skill"),
        )
    return builder.as_markup()

REMINDER_HOUR = 19
REMINDER_MINUTE = 0

async def notify_skill_card_reminder():
    global last_skill_notify_date
    while True:
        now = datetime.utcnow()
        today_str = now.strftime("%Y-%m-%d")

        # Проверяем, наступило ли заданное время
        if now.hour == REMINDER_HOUR and now.minute == REMINDER_MINUTE:
            if last_skill_notify_date != today_str:
                await send_reminder(
                    "🧠 Пора открыть суперспособность!", 
                    reply_markup=get_notify_skill_keyboard()
                )
                last_skill_notify_date = today_str

        await asyncio.sleep(10) 



# --- Безопасная отправка сообщений ---
from aiogram.exceptions import TelegramRetryAfter, TelegramForbiddenError, TelegramBadRequest


async def _safe_send(user_id: int, text: str, reply_markup=None):
    try:
        await bot.send_message(user_id, text, reply_markup=reply_markup)
        return True  # успешно
    except TelegramForbiddenError:
        # пользователь заблокировал бота → игнорируем
        print(f"[safe_send] Пользователь {user_id} заблокировал бота.")
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            # просто дубликат → не критично
            print(f"[safe_send] Сообщение не изменилось для {user_id}.")
        else:
            print(f"[safe_send] BadRequest {user_id}: {e}")
    except TelegramRetryAfter as e:
        # Flood control → ждём и пробуем снова
        print(f"[safe_send] FloodWait {e.retry_after} сек для {user_id}")
        await asyncio.sleep(e.retry_after)
        return await _safe_send(user_id, text, reply_markup)
    except Exception as e:
        print(f"[safe_send] Ошибка для {user_id}: {e}")
    return False


# --- Массовая рассылка (25 сообщений в секунду) ---
async def send_reminder(text: str, reply_markup=None):
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT user_id FROM users")
        all_users = cur.fetchall()

    for i in range(0, len(all_users), 25):
        batch = all_users[i:i + 25]
        tasks = [_safe_send(user_id, text, reply_markup) for (user_id,) in batch]
        await asyncio.gather(*tasks)
        await asyncio.sleep(1)

# --- Запуск всех задач ---
async def main():
    await asyncio.gather(
        notify_skill_card_reminder(),
        notify_member_card_reminder()
    )


if __name__ == "__main__":
    asyncio.run(main())