import asyncio
from datetime import datetime

from aiogram import Bot
from aiogram.utils.keyboard import InlineKeyboardButton, InlineKeyboardBuilder
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from utils.config import TOKEN
from database.db import connect

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

# Единое ежедневное напоминание для общей колоды.
last_card_notify_date = None
REMINDER_HOUR_UTC = 19  # 19:00 UTC = 22:00 МСК
REMINDER_MINUTE = 0

def get_notify_card_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🎴 Открыть карту", callback_data="draw_card"),
    )
    return builder.as_markup()

async def notify_card_reminder():
    global last_card_notify_date

    while True:
        now = datetime.utcnow()
        today_str = now.strftime("%Y-%m-%d")

        if now.hour == REMINDER_HOUR_UTC and 0 <= now.minute <= 4:
            if last_card_notify_date != today_str:
                print(f"[notify_card] Отправка уведомлений в {now} UTC")
                await send_reminder(
                    "🎴 Пора открыть карту из общей колоды!",
                    reply_markup=get_notify_card_keyboard(),
                )
                last_card_notify_date = today_str

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


# --- Рассылка для выбранного списка пользователей ---
async def send_reminder_to_users(text: str, reply_markup, users_list: list):
    """Отправить уведомление только указанному списку пользователей (30 сообщений в минуту)."""
    # 30 сообщений в минуту = 1 сообщение каждые 2 секунды
    for user_id in users_list:
        await _safe_send(user_id, text, reply_markup)
        await asyncio.sleep(2)  # 2 секунды между сообщениями = 30 сообщений в минуту

# --- Запуск всех задач ---
async def main():
    await notify_card_reminder()


if __name__ == "__main__":
    asyncio.run(main())