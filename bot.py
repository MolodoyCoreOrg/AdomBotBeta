import asyncio
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from database.db import init_db
from __init__ import routers
from utils.config import TOKEN
from handlers.notify import notify_card_reminder
from handlers.roulette import roulette_increment_task
from handlers.donate import run_da_client
from handlers.pidaraz import daily_pidaraz_check

import socketio

sio = socketio.AsyncClient()

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

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
        asyncio.create_task(notify_card_reminder())
        asyncio.create_task(roulette_increment_task())
        asyncio.create_task(daily_pidaraz_check(bot))

        await main()

    asyncio.run(run())