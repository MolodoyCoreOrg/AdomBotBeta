import asyncio
import time
import json
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.filters import Command, StateFilter
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from database.db import (
    add_presave_action, get_presave_action, mark_presave_rewarded,
    delete_presave_action, get_unrewarded_presave_actions, update_presave_screenshot
)
from handlers.cards_handler.skills import award_specific_skill
from utils.config import ADMINS_LIST

router = Router()

# ===== СОСТОЯНИЯ ДЛЯ ПРЕСЕЙВА =====
class PresaveState(StatesGroup):
    waiting_for_screenshot = State()


# ===== КНОПКА "СДЕЛАТЬ ПРЕСЕЙВ" В ГЛАВНОМ МЕНЮ =====
# Добавляем кнопку в главное меню через keyboard.py
# Пользователь нажимает кнопку - появляется кнопка с ссылкой и кнопка "Отправить скриншот"

@router.callback_query(F.data == "presave_click")
async def presave_click(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id

    # Проверяем, не нажимал ли уже
    action = get_presave_action(user_id)
    if action:
        if action["rewarded"]:
            await callback.answer("Вы уже получили карту за пресейв!", show_alert=True)
        elif action.get("screenshot_file_id"):
            await callback.answer("Вы уже отправили скриншот, дождитесь модерации", show_alert=True)
        else:
            # Пользователь нажал кнопку, но ещё не отправил скриншот - показываем интерфейс
            pass
    
    # Загружаем конфиг пресейва
    try:
        with open("data/table/presave_config.json", "r", encoding="utf-8") as f:
            config = json.load(f)
        presave_link = config.get("link", "https://band.link/ya_lublu_zhizn")
    except FileNotFoundError:
        presave_link = "https://band.link/ya_lublu_zhizn"

    # Сохраняем время нажатия
    now = int(time.time())
    add_presave_action(user_id, now)

    # Отправляем ссылку на пресейв и кнопку "Отправить скриншот"
    link_button = InlineKeyboardButton(
        text="🔗 Перейти к пресейву",
        url=presave_link
    )
    screenshot_button = InlineKeyboardButton(
        text="📸 Отправить скриншот",
        callback_data="presave_send_screenshot"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[link_button], [screenshot_button]])
    
    # Отправляем картинку YaLG.jpg с текстом
    image_path = "data/images/skills/YaLG.jpg"
    caption_text = (
        "🎵 <b>Сделать пресейв</b>\n\n"
        "Поддержи трек \"Я люблю жизнь\" - сделай пресейв!\n"
        "Перейди по ссылке ниже, послушай трек и добавь его в свою медиатеку.\n"
        "После этого отправь скриншот для получения эксклюзивной карты!\n\n"
        "✅ После проверки ты получишь уникальную карту, которую нельзя продать или обменять."
    )
    
    try:
        photo = FSInputFile(image_path)
        await callback.message.answer_photo(
            photo=photo,
            caption=caption_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    except Exception as e:
        # Если картинка не найдена, отправляем только текст
        await callback.message.answer(
            caption_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        print(f"Не удалось отправить изображение YaLG.jpg: {e}")

    await callback.answer("Готово! Ждите карту после проверки.", show_alert=True)


@router.callback_query(F.data == "presave_send_screenshot")
async def presave_send_screenshot_callback(callback: CallbackQuery, state: FSMContext):
    """Пользователь нажал кнопку 'Отправить скриншот' - переходим в режим ожидания фото."""
    user_id = callback.from_user.id
    
    action = get_presave_action(user_id)
    if not action:
        await callback.answer("❌ Сначала нажмите кнопку 'Сделать пресейв'", show_alert=True)
        return
    
    if action["rewarded"]:
        await callback.answer("❌ Вы уже получили карту за пресейв.", show_alert=True)
        return
    
    if action.get("screenshot_file_id"):
        await callback.answer("Вы уже отправили скриншот, дождитесь модерации", show_alert=True)
        return
    
    # Устанавливаем состояние ожидания скриншота
    await state.set_state(PresaveState.waiting_for_screenshot)
    await callback.message.answer(
        "📸 Теперь отправьте скриншот, подтверждающий пресейв.\n"
        "⚠️ Можно отправить только ОДИН скриншот!"
    )
    await callback.answer()


@router.message(PresaveState.waiting_for_screenshot, F.photo)
async def handle_presave_screenshot(message: Message, state: FSMContext, bot: Bot):
    """Принимает скриншот от пользователя, который нажал кнопку пресейва."""
    user_id = message.from_user.id
    
    action = get_presave_action(user_id)
    if not action:
        await message.reply("❌ Вы не нажимали кнопку пресейва. Пожалуйста, сначала нажмите кнопку.")
        return
    
    if action["rewarded"]:
        await message.reply("❌ Вы уже получили карту за пресейв.")
        return
    
    if action.get("screenshot_file_id"):
        await message.reply("❌ Вы уже отправили скриншот, дождитесь модерации")
        return

    # Получаем лучшее качество фото
    photo = message.photo[-1]
    file_id = photo.file_id
    
    # Сохраняем file_id скриншота в БД
    update_presave_screenshot(user_id, file_id)
    
    # Очищаем состояние
    await state.clear()

    # Уведомляем всех администраторов с кнопками "Принять" и "Отклонить"
    approve_button = InlineKeyboardButton(
        text="✅ Принять и выдать карточку",
        callback_data=f"presave_approve:{user_id}"
    )
    reject_button = InlineKeyboardButton(
        text="❌ Отклонить",
        callback_data=f"presave_reject:{user_id}"
    )
    review_keyboard = InlineKeyboardMarkup(inline_keyboard=[[approve_button, reject_button]])
    
    for admin_id in ADMINS_LIST:
        try:
            await bot.send_photo(
                chat_id=admin_id,
                photo=file_id,
                caption=(
                    f"📸 Новый скриншот от пользователя "
                    f"@{message.from_user.username or message.from_user.first_name} (ID: {user_id}).\n"
                    f"Выберите действие:"
                ),
                reply_markup=review_keyboard
            )
        except Exception:
            pass

    await message.reply("✅ Твой скриншот отправлен администратору. После проверки получишь карту, либо пизды, тут как повезёт...")


@router.message(F.photo)
async def handle_unexpected_screenshot(message: Message):
    """Обработка скриншотов, отправленных без перехода в состояние ожидания."""
    user_id = message.from_user.id
    action = get_presave_action(user_id)
    
    if action and action.get("screenshot_file_id"):
        await message.reply("❌ Вы уже отправили скриншот, дождитесь модерации")
    elif action and not action["rewarded"]:
        await message.reply("❌ Нажмите кнопку 'Отправить скриншот', чтобы загрузить изображение.")
    else:
        await message.reply("❌ Вы не нажимали кнопку пресейва. Пожалуйста, сначала нажмите кнопку 'Сделать пресейв'.")


# ========== АДМИН: ПРИНЯТЬ/ОТКЛОНИТЬ ==========\
@router.callback_query(F.data.startswith("presave_approve:"))
async def presave_approve(callback: CallbackQuery, bot: Bot):
    """Админ нажал 'Принять и выдать карточку'."""
    from utils.config import ADMINS_LIST
    
    admin_id = callback.from_user.id
    if admin_id not in ADMINS_LIST:
        await callback.answer("❌ У вас нет доступа к этой команде.", show_alert=True)
        return
    
    user_id = int(callback.data.split(":")[1])
    
    action = get_presave_action(user_id)
    if not action:
        await callback.answer("❌ Пользователь не нажимал кнопку пресейва.", show_alert=True)
        return
    
    if action["rewarded"]:
        await callback.answer("❌ Пользователь уже получил карту.", show_alert=True)
        return
    
    # Загружаем конфиг пресейва для получения карты
    try:
        with open("data/table/presave_config.json", "r", encoding="utf-8") as f:
            config = json.load(f)
        card_name = config.get("card_name", "Яйцо")  # По умолчанию "Яйцо"
    except FileNotFoundError:
        card_name = "Яйцо"
    
    # Определяем путь к изображению в зависимости от карты
    if card_name == "Я люблю жизнь":
        image_path = "data/images/skills/YaLG.jpg"
        caption_text = "🎉 Поздравляем, братухо! Ты получил эксклюзивную карту суперспособности *Я люблю жизнь*, за пресейв песни ниги204vip с одноименным названием! Спасибо тебе! Люби жизнь, будь попроще к себе и посерьезнее к делу! Добра и позитива!"
    else:  # Яйцо
        image_path = "data/images/skills/yaica.jpg"
        caption_text = "🎉 Поздравляем, братухо! Ты получил эксклюзивную карту суперспособности *Яйцо*! Эта карта доступна только за пресейвы!"
    
    # Выдаём карту
    success = award_specific_skill(user_id, card_name)
    if success:
        mark_presave_rewarded(user_id)
        delete_presave_action(user_id)

        # Отправляем картинку карты вместе с текстом
        try:
            photo = FSInputFile(image_path)
            await bot.send_photo(
                chat_id=user_id,
                photo=photo,
                caption=caption_text,
                parse_mode="Markdown"
            )
        except Exception as e:
            # Если картинка не найдена, отправляем только текст
            await bot.send_message(
                chat_id=user_id,
                text=caption_text,
                parse_mode="Markdown"
            )
            print(f"Не удалось отправить изображение карты пользователю {user_id}: {e}")

        await callback.answer(f"✅ Карта выдана пользователю {user_id}.", show_alert=True)
        
        # Редактируем сообщение админа
        await callback.message.edit_caption(
            caption=f"✅ ПРИНЯТО! Карта выдана пользователю {user_id}.",
            reply_markup=None
        )
    else:
        await callback.answer(f"❌ Не удалось выдать карту пользователю {user_id}.", show_alert=True)


@router.callback_query(F.data.startswith("presave_reject:"))
async def presave_reject(callback: CallbackQuery, bot: Bot):
    """Админ нажал 'Отклонить'."""
    from utils.config import ADMINS_LIST
    
    admin_id = callback.from_user.id
    if admin_id not in ADMINS_LIST:
        await callback.answer("❌ У вас нет доступа к этой команде.", show_alert=True)
        return
    
    user_id = int(callback.data.split(":")[1])
    
    action = get_presave_action(user_id)
    if not action:
        await callback.answer("❌ Пользователь не нажимал кнопку пресейва.", show_alert=True)
        return
    
    # Удаляем запись о пресейве
    delete_presave_action(user_id)
    
    # Уведомляем пользователя
    try:
        await bot.send_message(
            chat_id=user_id,
            text="❌ Ваш скриншот был отклонён администрацией. Попробуйте снова, если считаете, что это ошибка."
        )
    except Exception:
        pass
    
    await callback.answer(f"❌ Скриншот отклонён.", show_alert=True)
    
    # Редактируем сообщение админа
    await callback.message.edit_caption(
        caption=f"❌ ОТКЛОНЕНО! Заявка пользователя {user_id} удалена.",
        reply_markup=None
    )