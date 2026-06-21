import os
import datetime
import logging
import asyncio
from typing import Optional

from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import InlineQuery, InlineQueryResultArticle, InputTextMessageContent, Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.client.default import DefaultBotProperties

from storage import JSONRecountStorage

# Логирование
logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN_HERE")
MAX_SLOTS = 100

# Создаем инстансы
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode="Markdown"))
dp = Dispatcher()
router = Router()
storage = JSONRecountStorage("recount_data.json", MAX_SLOTS)

def get_mention(user_info: dict) -> str:
    """Генерирует форматирование для юзернейма или ссылки на Telegram ID"""
    if user_info.get("username"):
        return f"@{user_info['username']}"
    else:
        first_name = user_info.get("first_name", "Пидараз")
        return f"[{first_name}](tg://user?id={user_info['id']})"

# 1. Стартовая команда
@router.message(CommandStart())
async def cmd_start(message: Message):
    user_id = message.from_user.id
    user = storage.get_user(user_id)
    bot_info = await bot.get_me()

    if user and user.get("slot_number") is not None:
        await message.answer(
            f"🏳️‍🌈 *Вы успешно зарегистрированы!*\n\n"
            f"Ваш номер: *Пидараз {user['slot_number']}*.\n\n"
            f"Теперь вы можете отправлять статус в любое время через `@` инлайн\\-режим:\n"
            f"`@{bot_info.username}`"
        )
        return

    welcome_text = (
        f"🏳️‍🌈 *Добро пожаловать в Пересчет Пидаразов!*\n\n"
        f"Здесь ты можешь занять свой уникальный пожизненный номер пидараза (от 1 до {MAX_SLOTS}).\n\n"
        f"⚠️ *Важные правила:*\n"
        f"1. Номер выбирается ОДИН раз и изменить его нельзя.\n"
        f"2. Занятый номер никто другой забрать не сможет.\n"
        f"3. Всего доступно ровно {MAX_SLOTS} слотов.\n\n"
        f"👇 *Как выбрать номер?*\n"
        f"Просто напиши в ответ любое число от 1 до {MAX_SLOTS}."
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="Посмотреть список занятых 🏳️‍🌈", callback_data="show_occupied_list")

    await message.answer(welcome_text, reply_markup=builder.as_markup())

# 2. Список занятых слотов (/list)
@router.message(Command("list"))
async def cmd_list(message: Message):
    await send_occupied_list(message.chat.id)

async def send_occupied_list(chat_id: int):
    slots = storage.get_slots(MAX_SLOTS)
    users = storage.get_all_users()
    
    user_map = {u["id"]: u for u in users}
    occupied_slots = [s for s in slots if s["user_id"] is not None]

    if not occupied_slots:
        await bot.send_message(
            chat_id,
            f"📭 Все слоты свободны!\n"
            f"Напиши число от 1 до {MAX_SLOTS}, чтобы стать первым."
        )
        return

    report = f"🏳️‍🌈 *Список зарегистрированных пидаразов ({len(occupied_slots)}/{MAX_SLOTS}):*\n\n"
    for slot in occupied_slots:
        u = user_map.get(slot["user_id"])
        if u:
            mention = get_mention(u)
            report += f"• *Пидараз {slot['number']}* — {mention} на связи\n"

    await bot.send_message(chat_id, report, disable_web_page_preview=True)

# 3. Админская команда запуска утреннего пересчета
@router.message(Command("morning_recount_admin"))
async def cmd_morning_recount_admin(message: Message):
    await message.answer("Запускаю утренний пересчет пидаразов...")
    await trigger_morning_recount()
    await message.answer("Рассылка завершена!")

async def trigger_morning_recount():
    users = storage.get_all_users()
    registered_users = [u for u in users if u.get("slot_number") is not None]

    for u in registered_users:
        try:
            slot_num = u["slot_number"]
            text = (
                f"⏰ *ПЕРЕСЧЕТ ПИДАРАЗОВ!*\n\n"
                f"Пидараз *{slot_num}* на связи??? Подтверди присутствие!"
            )
            builder = InlineKeyboardBuilder()
            builder.button(
                text=f"🙋‍♂️ Пидараз {slot_num} на связи!", 
                callback_data=f"checkin_{slot_num}"
            )
            await bot.send_message(u["id"], text, reply_markup=builder.as_markup())
        except Exception as e:
            logging.error(f"Не удалось отправить уведомление пользователю {u['id']}: {e}")

# 4. Обработчик Callback-кликов
@router.callback_query(F.data == "show_occupied_list")
async def cb_show_occupied_list(callback: CallbackQuery):
    await callback.answer()
    await send_occupied_list(callback.message.chat.id)

@router.callback_query(F.data.startswith("checkin_"))
async def cb_checkin(callback: CallbackQuery):
    slot_num = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    date_str = datetime.date.today().isoformat()

    user = storage.get_user(user_id)
    if not user or user.get("slot_number") != slot_num:
        await callback.answer("Это не твой номер или ты не зарегистрирован!", show_alert=True)
        return

    success = storage.record_check_in(user_id, date_str)
    if not success:
        await callback.answer("Вы уже отметились сегодня!", show_alert=True)
        return

    await callback.answer("Присутствие подтверждено!")
    
    # Обновляем сообщение (кнопку убираем)
    await callback.message.edit_text(f"✅ Пидараз {slot_num} на связи! Присутствие подтверждено.")

    # Делаем рассылку
    all_users = storage.get_all_users()
    mention = get_mention(user)
    broadcast_text = f"📣 *Пересчет:* Пидараз *{slot_num}* ({mention}) на связи!"

    for recipient in all_users:
        try:
            await bot.send_message(recipient["id"], broadcast_text)
        except Exception:
            pass

# 5. Обработчик текстовых сообщений (выбор номера)
@router.message(F.text)
async def handle_registration(message: Message):
    text = message.text.strip()
    user_id = message.from_user.id

    try:
        num = int(text)
    except ValueError:
        user = storage.get_user(user_id)
        if not user or user.get("slot_number") is None:
            await message.reply(f"Чтобы зарегистрироваться, напиши число от 1 до {MAX_SLOTS}. Например: 7")
        return

    success, error = storage.choose_slot(
        user_id=user_id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
        slot_number=num
    )

    if success:
        bot_info = await bot.get_me()
        await message.reply(
            f"🎉 *Поздравляем!*\n\n"
            f"Вы успешно зарезервировали слот *#{num}*.\n"
            f"Отныне и вовек вы зафиксированы как *Пидараз {num}*!\n\n"
            f"Теперь вы можете залинковать себя в любом чате через инлайн-режим:\n"
            f"Просто введите `@{bot_info.username}`."
        )
    else:
        await message.reply(f"❌ Ошибка: {error}")

# 6. Инлайн-режим через @bot_username
@router.inline_query()
async def inline_handler(inline_query: InlineQuery):
    user_id = inline_query.from_user.id
    user = storage.get_user(user_id)
    bot_info = await bot.get_me()

    results = []

    if user and user.get("slot_number") is not None:
        slot_num = user["slot_number"]
        mention = get_mention(user)
        msg_text = f"🏳️‍🌈 Пидараз {slot_num} ({mention}) на связи!"

        item = InlineQueryResultArticle(
            id=f"pidaraz_{slot_num}",
            title="Пересчет Пидаразов",
            description=f"Отправить: 'Пидараз {slot_num} на связи'",
            input_message_content=InputTextMessageContent(
                message_text=msg_text,
                parse_mode="Markdown"
            )
        )
        results.append(item)
    else:
        # Безномерной
        start_link = f"https://t.me/{bot_info.username}?start=choose"
        builder = InlineKeyboardBuilder()
        builder.button(text="Выбрать номер 🏳️‍🌈", url=start_link)

        item = InlineQueryResultArticle(
            id="not_registered",
            title="Я безномерный пидараз 🤷‍♂️",
            description="Нажми, чтобы зайти в бота и выбрать свободный номер.",
            input_message_content=InputTextMessageContent(
                message_text="Я безномерный пидараз... 🤷‍♂️\n\nМне нужно зайти в бота и занять слот!",
                parse_mode="Markdown"
            ),
            reply_markup=builder.as_markup()
        )
        results.append(item)

    await inline_query.answer(results, is_personal=True, cache_time=0)

async def main():
    dp.include_router(router)
    print("AIOGRAM Бот успешно запущен и готов к работе...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
