import json, os
from aiogram import types, Router
from aiogram.filters import Command

router = Router()


STATS_PATH = "data/table/stats.json"

def load_stats():
    if not os.path.exists(STATS_PATH):
        return {
            "total_users": 0,
            "cards_opened": {
                "members": 0,
                "skills": 0
            }
        }
    with open(STATS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_stats(stats):
    with open(STATS_PATH, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)

def increment_stat(key, subkey=None):
    stats = load_stats()
    if subkey:
        stats[key][subkey] += 1
    else:
        stats[key] += 1
    save_stats(stats)














@router.message(Command("stats"))
async def send_stats(message: types.Message):
    from handlers.admin import admin_GG
    user_id = message.from_user.id

    # Проверка на админа (если есть система ролей)
    if not admin_GG.is_admin(user_id):
        return await message.reply("У вас нет доступа к этой команде.")

    stats = load_stats()
    text = (
        f"📊 Общая статистика:\n"
        f"👥 Пользователей зарегистрировано: {stats['total_users']}\n\n"
        f"🃏 Карточек открыто:\n"
        f"• Участников: {stats['cards_opened']['members']}\n"
        f"• Способностей: {stats['cards_opened']['skills']}"
    )
    await message.reply(text)