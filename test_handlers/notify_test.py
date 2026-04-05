
import datetime
import asyncio

# Тестовое время напоминания
REMINDER_HOUR = 14
REMINDER_MINUTE = 18

# last_skill_notify_date
last_skill_notify_date = None

async def send_reminder(msg):
    print(f"REMINDER: {msg}")

async def test_reminder():
    global last_skill_notify_date

    # Можно сразу задать любое "текущее" время для проверки
    now = datetime.datetime.utcnow().replace(hour=14, minute=37)
    today_str = now.strftime("%Y-%m-%d")

    # Проверка условия
    if now.hour == REMINDER_HOUR and now.minute == REMINDER_MINUTE:
        if last_skill_notify_date != today_str:
            await send_reminder("🧠 Пора открыть суперспособность!")
            last_skill_notify_date = today_str

# Запуск теста
asyncio.run(test_reminder())