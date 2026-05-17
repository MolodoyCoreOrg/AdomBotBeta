import asyncio
from datetime import datetime, timedelta
import json
import os
from aiogram import Bot
from aiogram.utils.keyboard import InlineKeyboardButton, InlineKeyboardBuilder
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramRetryAfter, TelegramForbiddenError, TelegramBadRequest

from utils.config import TOKEN
from database.db import connect, get_all_user_ids, load_roulette_data, save_roulette_data

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

# Путь к файлу с днями рождения
BIRTHDAYS_JSON_PATH = "data/cards/birthdays.json"
BIRTHDAY_IMAGES_PATH = "data/images/birthdays/"

# Глобальная переменная для хранения даты последнего уведомления
last_birthday_notify_date = None


def get_birthdays_data():
    """Загрузить данные о днях рождения из JSON файла."""
    try:
        with open(BIRTHDAYS_JSON_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[get_birthdays_data] Ошибка загрузки {BIRTHDAYS_JSON_PATH}: {e}")
        return {"birthdays": [], "birthday_bonuses": {}}


def get_today_birthdays():
    """Получить список именинников на сегодня."""
    data = get_birthdays_data()
    today = datetime.now()
    today_str = today.strftime("%d.%m")
    
    today_birthdays = []
    for member in data.get("birthdays", []):
        if member.get("date") == today_str and member.get("status") == "Готово":
            today_birthdays.append(member)
    
    return today_birthdays


def get_birthday_bonuses():
    """Получить настройки бонусов на день рождения."""
    data = get_birthdays_data()
    return data.get("birthday_bonuses", {
        "fire_points_multiplier": 2,
        "super_ability_draws": 2,
        "casino_spins_bonus": 5
    })


def get_birthday_keyboard(birthday_member):
    """Создать клавиатуру для поздравления с днем рождения."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🎁 Получить бонусы", callback_data="claim_birthday_bonus"),
    )
    builder.row(
        InlineKeyboardButton(text="🎉 Поздравить", callback_data=f"greet_birthday_{birthday_member['id']}"),
    )
    return builder.as_markup()


async def _safe_send(user_id: int, text: str, reply_markup=None, photo=None):
    """Безопасная отправка сообщений с обработкой ошибок."""
    try:
        if photo:
            await bot.send_photo(user_id, photo=photo, caption=text, reply_markup=reply_markup)
        else:
            await bot.send_message(user_id, text, reply_markup=reply_markup)
        return True
    except TelegramForbiddenError:
        print(f"[safe_send] Пользователь {user_id} заблокировал бота.")
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            print(f"[safe_send] Сообщение не изменилось для {user_id}.")
        else:
            print(f"[safe_send] BadRequest {user_id}: {e}")
    except TelegramRetryAfter as e:
        print(f"[safe_send] FloodWait {e.retry_after} сек для {user_id}")
        await asyncio.sleep(e.retry_after)
        return await _safe_send(user_id, text, reply_markup, photo)
    except Exception as e:
        print(f"[safe_send] Ошибка для {user_id}: {e}")
    return False


def apply_birthday_bonuses(user_id: int):
    """Применить бонусы пользователю в день рождения участника."""
    bonuses = get_birthday_bonuses()
    
    with connect() as conn:
        cur = conn.cursor()
        
        # Получаем текущие данные пользователя из roulette_user
        cur.execute("SELECT * FROM roulette_user WHERE user_id = ?", (user_id,))
        user_data = cur.fetchone()
        
        if not user_data:
            # Если записи нет, создаём её
            cur.execute("""
                INSERT INTO roulette_user (user_id, fire_points, roulette_count)
                VALUES (?, ?, ?)
            """, (user_id, bonuses.get("fire_points_multiplier", 2) * 10, 5 + bonuses.get("casino_spins_bonus", 5)))
        else:
            # Обновляем существующую запись
            current_fire_points = user_data["fire_points"] if "fire_points" in user_data.keys() else 0
            current_roulette_count = user_data["roulette_count"]
            
            # Увеличиваем огоньки (умножаем на множитель)
            new_fire_points = current_fire_points + (bonuses.get("fire_points_multiplier", 2) * 10)
            
            # Добавляем крутки в казико
            new_roulette_count = current_roulette_count + bonuses.get("casino_spins_bonus", 5)
            
            cur.execute("""
                UPDATE roulette_user 
                SET fire_points = ?, roulette_count = ?
                WHERE user_id = ?
            """, (new_fire_points, new_roulette_count, user_id))
        
        conn.commit()


async def send_birthday_notification():
    """Отправить уведомление о дне рождении участника всем пользователям."""
    global last_birthday_notify_date
    
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    
    # Проверяем, наступило ли время отправки (0:00 по UTC)
    if now.hour == 0 and now.minute == 0:
        if last_birthday_notify_date != today_str:
            today_birthdays = get_today_birthdays()
            
            if today_birthdays:
                # Формируем сообщение
                for birthday_member in today_birthdays:
                    greeting_text = birthday_member.get("greeting", "")
                    nickname = birthday_member.get("nickname", "")
                    real_name = birthday_member.get("real_name", "")
                    
                    message = (
                        f"🎉 <b>СЕГОДНЯ ДЕНЬ РОЖДЕНИЯ!</b> 🎉\n\n"
                        f"⭐ <b>Именинник:</b> {nickname} ({real_name})\n\n"
                        f"🎈 {greeting_text}\n\n"
                        f"🎁 <b>В честь праздника все пользователи получают бонусы:</b>\n"
                        f"🔥 Увеличенные огоньки\n"
                        f"🃏 Дополнительные открытия суперспособностей\n"
                        f"🎰 Больше круток в казино\n\n"
                        f"Жмите кнопку ниже, чтобы получить свои подарки! 👇"
                    )
                    
                    # Пытаемся найти изображение
                    image_path = None
                    image_file = birthday_member.get("image")
                    if image_file and os.path.exists(os.path.join(BIRTHDAY_IMAGES_PATH, image_file)):
                        image_path = os.path.join(BIRTHDAY_IMAGES_PATH, image_file)
                    
                    # Получаем всех пользователей
                    with connect() as conn:
                        cur = conn.cursor()
                        cur.execute("SELECT user_id FROM users")
                        all_users = cur.fetchall()
                    
                    keyboard = get_birthday_keyboard(birthday_member)
                    
                    # Отправляем сообщения batches по 25 пользователей
                    for i in range(0, len(all_users), 25):
                        batch = all_users[i:i + 25]
                        tasks = [_safe_send(user_id, message, keyboard, image_path) for (user_id,) in batch]
                        await asyncio.gather(*tasks)
                        await asyncio.sleep(1)
                    
                    # Применяем бонусы всем пользователям
                    for (user_id,) in all_users:
                        try:
                            apply_birthday_bonuses(user_id)
                        except Exception as e:
                            print(f"[apply_birthday_bonuses] Ошибка для пользователя {user_id}: {e}")
                    
                    last_birthday_notify_date = today_str
                    print(f"[Birthday] Отправлено уведомление о дне рождения {nickname}")
            
            else:
                # Сегодня нет дней рождений
                last_birthday_notify_date = today_str
    
    await asyncio.sleep(60)  # Проверяем каждую минуту


async def notify_birthday_reminder():
    """Основная задача для напоминания о днях рождениях."""
    global last_birthday_notify_date
    
    while True:
        try:
            await send_birthday_notification()
        except Exception as e:
            print(f"[notify_birthday_reminder] Ошибка: {e}")
            await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(notify_birthday_reminder())
