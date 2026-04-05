import asyncio
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from database.db import init_db
from __init__ import routers
from utils.config import TOKEN
from handlers.notify import notify_member_card_reminder, notify_skill_card_reminder
from handlers.roulette import roulette_increment_task
from handlers.donate import run_da_client

import socketio

sio = socketio.AsyncClient()

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# ====== Aiogram команды ======
for router in routers:
    dp.include_router(router)

async def main():
    init_db()
    await asyncio.gather(
        dp.start_polling(bot),
        run_da_client()
    )

if __name__ == "__main__":
    async def run():
        # Запуск фоновых напоминаний
        asyncio.create_task(notify_member_card_reminder())
        asyncio.create_task(notify_skill_card_reminder())
        asyncio.create_task(roulette_increment_task())

        await main()

    asyncio.run(run())