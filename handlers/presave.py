import asyncio
import time
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.filters import Command
from database.db import (
    add_presave_action, get_presave_action, mark_presave_rewarded,
    delete_presave_action, get_unrewarded_presave_actions
)
from handlers.cards_handler.skills import award_specific_skill
from utils.config import ADMINS_LIST

router = Router()

# ========== Обработчик нажатия кнопки ==========
@router.callback_query(F.data == "presave_click")
async def presave_click(callback: CallbackQuery):
    user_id = callback.from_user.id

    # Проверяем, не нажимал ли уже
    action = get_presave_action(user_id)
    if action:
        if action["rewarded"]:
            await callback.answer("Вы уже получили карту за пресейв!", show_alert=True)
        else:
            await callback.answer("Ваш запрос уже обрабатывается. Пожалуйста, отправьте скриншот пресейва.", show_alert=True)
        return

    # Сохраняем время нажатия
    now = int(time.time())
    add_presave_action(user_id, now)

    # Отправляем ссылку на пресейв и просим отправить скриншот
    link_button = InlineKeyboardButton(
        text="🔗 Перейти к пресейву",
        url="https://band.link/yaytsa_ptitsy"  # замените на реальную ссылку
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[link_button]])
    await callback.message.answer(
        "✅ Спасибо! Перейдите по ссылке, чтобы сделать пресейв.\n"
        "После этого отправьте сюда один скриншот, подтверждающий пресейв. "
        "Администратор проснется утром, проверит и выдаст вам уникальную карту суперспособности.",
        reply_markup=keyboard
    )

    await callback.answer("Готово! Ждите карту после проверки.", show_alert=True)


# ========== Приём скриншотов ==========
@router.message(F.photo)
async def handle_presave_screenshot(message: Message, bot: Bot):
    """Принимает скриншот от пользователя, который нажал кнопку пресейва."""
    user_id = message.from_user.id
    action = get_presave_action(user_id)
    if not action:
        await message.reply("❌ Вы не нажимали кнопку пресейва. Пожалуйста, сначала нажмите кнопку.")
        return
    if action["rewarded"]:
        await message.reply("❌ Вы уже получили карту за пресейв.")
        return

    # Получаем лучшее качество фото
    photo = message.photo[-1]
    file_id = photo.file_id

    # Уведомляем всех администраторов
    for admin_id in ADMINS_LIST:
        try:
            await bot.send_photo(
                chat_id=admin_id,
                photo=file_id,
                caption=(
                    f"📸 Новый скриншот от пользователя "
                    f"@{message.from_user.username or message.from_user.first_name} (ID: {user_id}).\n"
                    f"Для выдачи карты используйте /presave_grant {user_id}"
                )
            )
        except Exception:
            pass

    await message.reply("✅ Твой скриншот отправлен администратору. После проверки получишь карту, либо пизды, тут как повезёт...")


# ========== Админ-команды ==========
@router.message(Command("presave_review"))
async def presave_review(message: Message):
    """Показывает список пользователей, ожидающих проверки."""
    if message.from_user.id not in ADMINS_LIST:
        await message.answer("❌ У вас нет доступа к этой команде.")
        return

    pending = get_unrewarded_presave_actions()
    if not pending:
        await message.answer("Нет пользователей, ожидающих проверки.")
        return

    text = "📋 Ожидают проверки:\n"
    for p in pending:
        text += f"• ID: {p['user_id']}, нажал: {time.ctime(p['pressed_at'])}\n"
    await message.answer(text)


@router.message(Command("presave_grant"))
async def presave_grant(message: Message, bot: Bot):
    """Выдает карту пользователю после проверки."""
    if message.from_user.id not in ADMINS_LIST:
        await message.answer("❌ У вас нет доступа к этой команде.")
        return

    parts = message.text.split()
    if len(parts) != 2:
        await message.reply("Использование: /presave_grant <user_id>")
        return

    try:
        user_id = int(parts[1])
    except ValueError:
        await message.reply("❌ user_id должен быть числом.")
        return

    action = get_presave_action(user_id)
    if not action:
        await message.reply(f"❌ Пользователь {user_id} не нажимал кнопку пресейва.")
        return
    if action["rewarded"]:
        await message.reply(f"❌ Пользователь {user_id} уже получил карту.")
        return

    # Выдаём карту
    success = award_specific_skill(user_id, "Яйцо")
    if success:
        mark_presave_rewarded(user_id)
        delete_presave_action(user_id)

        # Отправляем картинку карты вместе с текстом
        image_path = "data/images/skills/yaica.jpg"  # путь к изображению карты "Яйцо"
        try:
            photo = FSInputFile(image_path)
            await bot.send_photo(
                chat_id=user_id,
                photo=photo,
                caption="🎉 Поздравляем, братухо! Ты получил эксклюзивную карту суперспособности ,нах, *Яйца у птицы*, за пресейв нашей песни *Тихая роскошь*! Нормальный ты поц, яйцы, что надо ёпт. Не подкачал нах",
                parse_mode="HTML"
            )
        except Exception as e:
            # Если картинка не найдена, отправляем только текст
            await bot.send_message(
                chat_id=user_id,
                text="🎉 Поздравляем, братухо! Ты получил эксклюзивную карту суперспособности ,нах, *Яйца у птицы*, за пресейв нашей песни *Тихая роскошь*! Нормальный ты поц, яйцы, что надо ёпт. Не подкачал нах",
                parse_mode="HTML"
            )
            print(f"Не удалось отправить изображение карты пользователю {user_id}: {e}")

        await message.reply(f"✅ Карта выдана пользователю {user_id}.")
    else:
        await message.reply(f"❌ Не удалось выдать карту пользователю {user_id}. Возможно, карта уже есть или произошла ошибка.")