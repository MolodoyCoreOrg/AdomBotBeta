from aiogram import Router
from aiogram.types import Message
from aiogram import F

from database.db import connect

router = Router()


@router.message(F.text.startswith('/set_timezone '))
async def set_timezone_cmd(message: Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Usage: /set_timezone Europe/Moscow")
        return
    tz = parts[1].strip()
    try:
        # minimal validation: try to store; real validation happens when formatting
        with connect() as conn:
            cur = conn.cursor()
            cur.execute("UPDATE users SET timezone = ? WHERE user_id = ?", (tz, message.from_user.id))
            conn.commit()
        await message.answer(f"Timezone set to {tz} (will be used for displaying card dates)")
    except Exception as e:
        await message.answer(f"Failed to set timezone: {e}")
