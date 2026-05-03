import json
import re
import asyncio
from aiogram import Router, F, types
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database.db import (
    get_member_cards, get_skill_cards, 
    get_user_full_data, create_exchange_offer, get_pending_offers_to_user,
    get_pending_offers_from_user, update_exchange_offer_status, 
    set_exchange_offer_message_id, add_exchange_to_history,
    get_user_exchange_history, remove_member_card, remove_skill_card,
    add_member_card, add_skill_card, get_exchange_offer,
    connect, find_user_by_username
)
from handlers.keyboard import (
    get_exchange_main_keyboard, get_exchange_card_type_keyboard,
    get_exchange_member_cards_keyboard, get_exchange_skill_cards_keyboard,
    get_exchange_offer_keyboard
)
from utils.helpers import safe_edit_message, safe_delete
from utils.config import TOKEN
from aiogram import Bot

bot = Bot(token=TOKEN)
router = Router()

# Состояния для FSM
class ExchangeStates(StatesGroup):
    selecting_card_type = State()
    selecting_my_card = State()
    entering_username = State()
    selecting_their_card = State()

@router.callback_query(F.data == "exchange_menu")
async def exchange_menu(callback: CallbackQuery):
    """Главное меню обмена."""
    text = (
        "🔄 <b>Система обмена карточками</b>\n\n"
        "Здесь вы можете обмениваться карточками с другими игроками:\n"
        "• Карточки участников 👥\n"
        "• Суперспособности 🃏\n\n"
        "Выберите действие:"
    )
    
    await safe_edit_message(callback.message, text, reply_markup=get_exchange_main_keyboard())

@router.callback_query(F.data.startswith("inline_exchange_start:"))
async def inline_exchange_start(callback: CallbackQuery, state: FSMContext):
    """Начать обмен из inline-режима."""
    # Извлекаем данные
    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer("❌ Ошибка в данных обмена", show_alert=True)
        return

    card_type = parts[1]
    card_name = parts[2]
    user_id = callback.from_user.id

    # Проверяем, есть ли у пользователя такая карта
    if card_type == "member":
        user_cards = get_member_cards(user_id)
    elif card_type == "skill":
        user_cards = get_skill_cards(user_id)
    else:
        await callback.answer("❌ Неподдерживаемый тип карты", show_alert=True)
        return

    if card_name not in user_cards:
        await callback.answer("❌ У вас нет этой карты!", show_alert=True)
        return

    # Сохраняем данные о карте в state
    await state.update_data(
        my_card_type=card_type,
        my_card_name=card_name
    )

    # Устанавливаем состояние entering_username
    await state.set_state(ExchangeStates.entering_username)

    # Отправляем сообщение с просьбой ввести username
    await callback.message.edit_text(
        f"🔄 Вы выбрали для обмена:\n"
        f"💎 Тип: {'👥 Карта участника' if card_type == 'member' else '🃏 Суперспособность'}\n"
        f"📝 Название: <b>{card_name}</b>\n\n"
        f"Теперь введите @username пользователя, с которым хотите обменяться:"
    )

    # Отвечаем на callback, чтобы убрать часики
    await callback.answer()

@router.callback_query(F.data == "create_exchange")
async def create_exchange(callback: CallbackQuery, state: FSMContext):
    """Начать создание обмена."""
    user_id = callback.from_user.id
    
    # Проверяем, есть ли у пользователя карты для обмена
    member_cards = get_member_cards(user_id)
    skill_cards = get_skill_cards(user_id)
    
    if not member_cards and not skill_cards:
        await callback.answer("❌ У вас нет карт для обмена!", show_alert=True)
        return
    
    text = "🔄 Выберите тип карты, которую хотите предложить для обмена:"
    await safe_edit_message(callback.message, text, reply_markup=get_exchange_card_type_keyboard())
    
    await state.set_state(ExchangeStates.selecting_card_type)

@router.callback_query(F.data.startswith("exchange_type:"))
async def select_exchange_type(callback: CallbackQuery, state: FSMContext):
    """Выбор типа карты для обмена."""
    card_type = callback.data.split(":")[1]  # 'member' или 'skill'
    user_id = callback.from_user.id
    
    await state.update_data(card_type=card_type)
    
    if card_type == "member":
        cards = get_member_cards(user_id)
        if not cards:
            await callback.answer("❌ У вас нет карт участников для обмена!", show_alert=True)
            return
        
        text = "👥 Выберите карту участника, которую хотите предложить для обмена:"
        await safe_edit_message(callback.message, text, reply_markup=get_exchange_member_cards_keyboard(cards))
        
    else:  # skill
        cards = get_skill_cards(user_id)
        if not cards:
            await callback.answer("❌ У вас нет суперспособностей для обмена!", show_alert=True)
            return
        
        text = "🃏 Выберите суперспособность, которую хотите предложить для обмена:"
        await safe_edit_message(callback.message, text, reply_markup=get_exchange_skill_cards_keyboard(cards))
    
    await state.set_state(ExchangeStates.selecting_my_card)
    
    # Отвечаем на callback, чтобы убрать часики загрузки
    await callback.answer()

@router.callback_query(F.data.startswith("select_my_card:"))
async def select_my_card(callback: CallbackQuery, state: FSMContext):
    """Выбор конкретной карты для обмена."""
    data = callback.data.split(":")
    card_type = data[1]
    card_name = data[2]
    user_id = callback.from_user.id
    
    # Сохраняем данные в состоянии
    await state.update_data(my_card_type=card_type, my_card_name=card_name)
    
    text = (
        f"🔄 Вы выбрали для обмена:\n"
        f"💎 Тип: {'👥 Карта участника' if card_type == 'member' else '🃏 Суперспособность'}\n"
        f"📝 Название: <b>{card_name}</b>\n\n"
        f"Теперь введите @username пользователя, с которым хотите обменяться:"
    )
    
    await safe_edit_message(callback.message, text)
    await state.set_state(ExchangeStates.entering_username)
    
    # Отвечаем на callback, чтобы убрать часики загрузки
    await callback.answer()

@router.message(ExchangeStates.entering_username)
async def enter_username(message: Message, state: FSMContext):
    """Обработка ввода username."""
    user_id = message.from_user.id
    username_text = message.text.strip()
    
    # Извлекаем username из текста (может быть с @ или без)
    username_match = re.search(r'@?([a-zA-Z0-9_]+)', username_text)
    if not username_match:
        await message.answer("❌ Неверный формат username. Попробуйте снова:")
        return
    
    username = username_match.group(1)
    
    # Проверяем, не пытается ли пользователь обменяться с самим собой
    user_data = get_user_full_data(user_id)
    if user_data and user_data["username"] and user_data["username"].lower() == username.lower():
        await message.answer("❌ Нельзя обмениваться с самим собой! Введите другой username:")
        return
    
    # Ищем пользователя по username
    target_user = find_user_by_username(username)
    
    if not target_user:
        await message.answer("❌ Пользователь с таким username не найдены. Проверьте правильность и попробуйте снова:")
        return
    
    target_user_id = target_user["user_id"]
    target_username = target_user["username"]
    
    # Получаем данные о выбранной карте из state
    state_data = await state.get_data()
    my_card_type = state_data.get("my_card_type")
    my_card_name = state_data.get("my_card_name")
    
    # Проверяем, есть ли еще у пользователя выбранная карта
    if my_card_type == "member":
        user_cards = get_member_cards(user_id)
        if my_card_name not in user_cards:
            await message.answer("❌ У вас больше нет этой карты! Начните обмен заново.")
            await state.clear()
            return
    
    # Сохраняем данные о целевом пользователе
    await state.update_data(target_user_id=target_user_id, target_username=target_username)
    
    # Запрашиваем тип карты, которую хотим получить
    text = (
        f"🎯 Пользователь: @{target_username}\n"
        f"💎 Ваша карта: <b>{my_card_name}</b>\n\n"
        f"Выберите тип карты, которую хотите получить взамен:"
    )
    
    await message.answer(text, reply_markup=get_exchange_card_type_keyboard(prefix="request"))
    await state.set_state(ExchangeStates.selecting_their_card)
    
    # Удаляем сообщение с username
    await safe_delete(message)

@router.callback_query(F.data.startswith("request_type:"))
async def select_request_type(callback: CallbackQuery, state: FSMContext):
    """Выбор типа карты, которую хотим получить."""
    card_type = callback.data.split(":")[1]  # 'member' или 'skill'
    user_id = callback.from_user.id
    
    state_data = await state.get_data()
    target_user_id = state_data.get("target_user_id")
    target_username = state_data.get("target_username")
    
    await state.update_data(requested_card_type=card_type)
    
    # Получаем карты целевого пользователя
    if card_type == "member":
        cards = get_member_cards(target_user_id)
        if not cards:
            await callback.answer(f"❌ У @{target_username} нет карт участников для обмена!", show_alert=True)
            return
        
        text = f"👥 Выберите карту участника, которую хотите получить от @{target_username}:"
        await safe_edit_message(callback.message, text, reply_markup=get_exchange_member_cards_keyboard(cards, prefix="request"))
        
    else:  # skill
        cards = get_skill_cards(target_user_id)
        if not cards:
            await callback.answer(f"❌ У @{target_username} нет суперспособностей для обмена!", show_alert=True)
            return
        
        text = f"🃏 Выберите суперспособность, которую хотите получить от @{target_username}:"
        await safe_edit_message(callback.message, text, reply_markup=get_exchange_skill_cards_keyboard(cards, prefix="request"))
    
    # Отвечаем на callback, чтобы убрать часики загрузки
    await callback.answer()

@router.callback_query(F.data.startswith("request_card:"))
async def select_request_card(callback: CallbackQuery, state: FSMContext):
    """Выбор конкретной карты для запроса."""
    data = callback.data.split(":")
    card_type = data[1]
    card_name = data[2]
    user_id = callback.from_user.id
    
    # Получаем все данные из состояния
    state_data = await state.get_data()
    my_card_type = state_data.get("my_card_type")
    my_card_name = state_data.get("my_card_name")
    target_user_id = state_data.get("target_user_id")
    target_username = state_data.get("target_username")
    
    # Проверяем, есть ли у пользователя выбранная карта
    if my_card_type == "member":
        user_cards = get_member_cards(user_id)
        if my_card_name not in user_cards:
            await callback.answer("❌ У вас больше нет этой карты!", show_alert=True)
            return
    else:
        user_cards = get_skill_cards(user_id)
        if my_card_name not in user_cards:
            await callback.answer("❌ У вас больше нет этой карты!", show_alert=True)
            return
    
    # Проверяем, есть ли у оппонента выбранная карта
    if card_type == "member":
        target_cards = get_member_cards(target_user_id)
        if card_name not in target_cards:
            await callback.answer(f"❌ У @{target_username} больше нет этой карты!", show_alert=True)
            return
    else:
        target_cards = get_skill_cards(target_user_id)
        if card_name not in target_cards:
            await callback.answer(f"❌ У @{target_username} больше нет этой карты!", show_alert=True)
            return
    
    # Создаем предложение обмена
    user_data = get_user_full_data(user_id)
    from_user_username = user_data["username"] if user_data and user_data["username"] else f"user_{user_id}"
    
    offer_id = create_exchange_offer(
        from_user_id=user_id,
        to_user_id=target_user_id,
        from_user_username=from_user_username,
        to_user_username=target_username,
        offered_card_type=my_card_type,
        offered_card_name=my_card_name,
        requested_card_type=card_type,
        requested_card_name=card_name
    )
    
    # Отправляем уведомление целевому пользователю
    try:
        offer_text = (
            f"🔄 <b>Новое предложение обмена!</b>\n"
            f"👤 От: @{from_user_username}\n"
            f"💎 Предлагает: <b>{my_card_name}</b> ({'👥 участник' if my_card_type == 'member' else '🃏 способность'})\n"
            f"🎯 Просит: <b>{card_name}</b> ({'👥 участник' if card_type == 'member' else '🃏 способность'})\n"
            f"⏳ Предложение действительно 24 часа"
        )
        
        # Отправляем сообщение целевому пользователю
        sent_message = await bot.send_message(
            target_user_id, 
            offer_text, 
            reply_markup=get_exchange_offer_keyboard(offer_id)
        )
        
        # Сохраняем ID сообщения
        set_exchange_offer_message_id(offer_id, sent_message.message_id)
        
    except Exception as e:
        print(f"Не удалось отправить уведомление пользователю {target_user_id}: {e}")
    
    # Подтверждение пользователю
    success_text = (
        f"✅ <b>Предложение обмена отправлено!</b>\n\n"
        f"👤 Кому: @{target_username}\n"
        f"💎 Вы предлагаете: <b>{my_card_name}</b>\n"
        f"🎯 Вы просите: <b>{card_name}</b>\n\n"
        f"Ожидайте ответа. Вы можете отслеживать статус в разделе 'Мои предложения'"
    )
    
    await safe_edit_message(callback.message, success_text)
    await state.clear()
    
    # Отвечаем на callback, чтобы убрать часики загрузки
    await callback.answer()

@router.callback_query(F.data == "view_my_offers")
async def view_my_offers(callback: CallbackQuery):
    """Просмотр моих исходящих предложений."""
    user_id = callback.from_user.id
    offers = get_pending_offers_from_user(user_id)
    
    if not offers:
        text = "📭 У вас нет активных исходящих предложений обмена."
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="↪️ Назад", callback_data="exchange_menu"),
        )
        await safe_edit_message(callback.message, text, reply_markup=builder.as_markup())
        return
    
    text = "📤 <b>Ваши исходящие предложения обмена:</b>\n\n"
    
    for i, offer in enumerate(offers, 1):
        status_emoji = "⏳"
        text += (
            f"{i}. {status_emoji} Для: @{offer['to_user_username']}\n"
            f"   💎 Предлагаете: <b>{offer['offered_card_name']}</b>\n"
            f"   🎯 Просите: <b>{offer['requested_card_name']}</b>\n\n"
        )
    
    # Создаем клавиатуру с кнопкой "Назад"
    builder = InlineKeyboardBuilder()
    
    for offer in offers:
        builder.row(
            InlineKeyboardButton(
                text=f"❌ Отменить обмен с @{offer['to_user_username']}", 
                callback_data=f"cancel_exchange:{offer['id']}"
            )
        )
    
    builder.row(
        InlineKeyboardButton(text="↪️ Назад", callback_data="exchange_menu"),
    )
    
    await safe_edit_message(callback.message, text, reply_markup=builder.as_markup())

@router.callback_query(F.data == "view_incoming_offers")
async def view_incoming_offers(callback: CallbackQuery):
    """Просмотр входящих предложений."""
    user_id = callback.from_user.id
    offers = get_pending_offers_to_user(user_id)
    
    if not offers:
        text = "📭 У вас нет входящих предложений обмена."
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="↪️ Назад", callback_data="exchange_menu"),
        )
        await safe_edit_message(callback.message, text, reply_markup=builder.as_markup())
        return
    
    text = "📥 <b>Входящие предложения обмена:</b>\n\n"
    
    for i, offer in enumerate(offers, 1):
        status_emoji = "⏳"
        text += (
            f"{i}. {status_emoji} От: @{offer['from_user_username']}\n"
            f"   💎 Предлагает: <b>{offer['offered_card_name']}</b>\n"
            f"   🎯 Просит: <b>{offer['requested_card_name']}</b>\n\n"
        )
    
    # Создаем клавиатуру с кнопкой "Назад"
    builder = InlineKeyboardBuilder()
    
    for offer in offers:
        builder.row(
            InlineKeyboardButton(
                text=f"✅ Ответить на предложение от @{offer['from_user_username']}", 
                callback_data=f"respond_exchange:{offer['id']}"
            )
        )
    
    builder.row(
        InlineKeyboardButton(text="↪️ Назад", callback_data="exchange_menu"),
    )
    
    await safe_edit_message(callback.message, text, reply_markup=builder.as_markup())

@router.callback_query(F.data.startswith("respond_exchange:"))
async def respond_exchange(callback: CallbackQuery):
    """Отображение конкретного предложения для ответа."""
    offer_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    
    offer = get_exchange_offer(offer_id)
    if not offer:
        await callback.answer("❌ Предложение не найдено или устарело!", show_alert=True)
        return
    
    if offer["to_user_id"] != user_id:
        await callback.answer("❌ Это предложение не для вас!", show_alert=True)
        return
    
    if offer["status"] != "pending":
        await callback.answer("❌ Это предложение уже обработано!", show_alert=True)
        return
    
    text = (
        f"🔄 <b>Предложение обмена</b>\n\n"
        f"👤 От: @{offer['from_user_username']}\n"
        f"💎 Предлагает: <b>{offer['offered_card_name']}</b> ({'👥 участник' if offer['offered_card_type'] == 'member' else '🃏 способность'})\n"
        f"🎯 Просит: <b>{offer['requested_card_name']}</b> ({'👥 участник' if offer['requested_card_type'] == 'member' else '🃏 способность'})\n\n"
        f"⏳ Предложение действительно до: {offer['expires_at']}"
    )
    
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Принять", callback_data=f"accept_exchange:{offer_id}"),
        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_exchange:{offer_id}")
    )
    builder.row(
        InlineKeyboardButton(text="↪️ Назад", callback_data="view_incoming_offers")
    )
    
    await safe_edit_message(callback.message, text, reply_markup=builder.as_markup())

@router.callback_query(F.data.startswith("accept_exchange:"))
async def accept_exchange(callback: CallbackQuery):
    """Принятие предложения обмена."""
    offer_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    
    offer = get_exchange_offer(offer_id)
    if not offer:
        await callback.answer("❌ Предложение не найдено или устарело!", show_alert=True)
        return
    
    if offer["to_user_id"] != user_id:
        await callback.answer("❌ Это предложение не для вас!", show_alert=True)
        return
    
    if offer["status"] != "pending":
        await callback.answer("❌ Это предложение уже обработано!", show_alert=True)
        return
    
    # Проверяем, есть ли еще у пользователей нужные карты
    # from_user должен иметь offered_card (то, что он предлагает)
    from_user_cards = get_member_cards(offer["from_user_id"]) if offer["offered_card_type"] == "member" else get_skill_cards(offer["from_user_id"])
    # to_user должен иметь requested_card (то, что у него просят)
    to_user_cards = get_member_cards(offer["to_user_id"]) if offer["requested_card_type"] == "member" else get_skill_cards(offer["to_user_id"])
    
    if offer["offered_card_name"] not in from_user_cards:
        await callback.answer("❌ У отправителя больше нет этой карты!", show_alert=True)
        update_exchange_offer_status(offer_id, "cancelled")
        return
    
    if offer["requested_card_name"] not in to_user_cards:
        await callback.answer("❌ У вас больше нет этой карты!", show_alert=True)
        return
    
    # Выполняем обмен
    try:
        # Удаляем карты у пользователей
        # from_user отдает offered_card
        if offer["offered_card_type"] == "member":
            remove_member_card(offer["from_user_id"], offer["offered_card_name"])
        else:
            remove_skill_card(offer["from_user_id"], offer["offered_card_name"])
        
        # to_user отдает requested_card
        if offer["requested_card_type"] == "member":
            remove_member_card(offer["to_user_id"], offer["requested_card_name"])
        else:
            remove_skill_card(offer["to_user_id"], offer["requested_card_name"])
        
        # Добавляем карты пользователям
        # to_user получает offered_card (то, что предложил from_user)
        if offer["offered_card_type"] == "member":
            add_member_card(offer["to_user_id"], offer["offered_card_name"])
        else:
            add_skill_card(offer["to_user_id"], offer["offered_card_name"])
        
        # from_user получает requested_card (то, что он просил)
        if offer["requested_card_type"] == "member":
            add_member_card(offer["from_user_id"], offer["requested_card_name"])
        else:
            add_skill_card(offer["from_user_id"], offer["requested_card_name"])
        
        # Обновляем статус предложения
        update_exchange_offer_status(offer_id, "accepted")
        
        # Добавляем в историю
        add_exchange_to_history(
            offer_id=offer_id,
            from_user_id=offer["from_user_id"],
            to_user_id=offer["to_user_id"],
            from_user_username=offer["from_user_username"],
            to_user_username=offer["to_user_username"],
            exchanged_card_type=offer["offered_card_type"],
            exchanged_card_name=offer["offered_card_name"],
            received_card_type=offer["requested_card_type"],
            received_card_name=offer["requested_card_name"]
        )
        
        # Уведомляем отправителя
        try:
            success_text = (
                f"✅ <b>Ваше предложение обмена принято!</b>\n\n"
                f"👤 Пользователь: @{offer['to_user_username']}\n"
                f"💎 Вы получили: <b>{offer['requested_card_name']}</b>\n"
                f"🎯 Вы отдали: <b>{offer['offered_card_name']}</b>"
            )
            await bot.send_message(offer["from_user_id"], success_text)
        except Exception as e:
            print(f"Не удалось уведомить отправителя {offer['from_user_id']}: {e}")
        
        # Уведомление текущему пользователю
        success_text = (
            f"✅ <b>Обмен выполнен успешно!</b>\n\n"
            f"👤 Пользователь: @{offer['from_user_username']}\n"
            f"💎 Вы получили: <b>{offer['offered_card_name']}</b>\n"
            f"🎯 Вы отдали: <b>{offer['requested_card_name']}</b>"
        )
        
        await safe_edit_message(callback.message, success_text)
        
    except Exception as e:
        print(f"Ошибка при выполнении обмена: {e}")
        await callback.answer("❌ Произошла ошибка при обмене!", show_alert=True)

@router.callback_query(F.data.startswith("reject_exchange:"))
async def reject_exchange(callback: CallbackQuery):
    """Отклонение предложения обмена."""
    offer_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    
    offer = get_exchange_offer(offer_id)
    if not offer:
        await callback.answer("❌ Предложение не найдено или устарело!", show_alert=True)
        return
    
    if offer["to_user_id"] != user_id:
        await callback.answer("❌ Это предложение не для вас!", show_alert=True)
        return
    
    if offer["status"] != "pending":
        await callback.answer("❌ Это предложение уже обработано!", show_alert=True)
        return
    
    # Обновляем статус предложения
    update_exchange_offer_status(offer_id, "rejected")
    
    # Уведомляем отправителя
    try:
        reject_text = (
            f"❌ Ваше предложение обмена отклонено\n\n"
            f"👤 Пользователь: @{offer['to_user_username']}\n"
            f"💎 Предлагали: {offer['offered_card_name']}\n"
            f"🎯 Просили: {offer['requested_card_name']}"
        )
        await bot.send_message(offer["from_user_id"], reject_text)
    except Exception as e:
        print(f"Не удалось уведомить отправителя {offer['from_user_id']}: {e}")
    
    await callback.answer("✅ Предложение отклонено!", show_alert=False)
    await safe_edit_message(callback.message, "❌ Вы отклонили предложение обмена.")

@router.callback_query(F.data.startswith("cancel_exchange:"))
async def cancel_exchange(callback: CallbackQuery):
    """Отмена своего предложения обмена."""
    offer_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    
    offer = get_exchange_offer(offer_id)
    if not offer:
        await callback.answer("❌ Предложение не найдено или устарело!", show_alert=True)
        return
    
    if offer["from_user_id"] != user_id:
        await callback.answer("❌ Это не ваше предложение!", show_alert=True)
        return
    
    if offer["status"] != "pending":
        await callback.answer("❌ Это предложение уже обработано!", show_alert=True)
        return
    
    # Обновляем статус предложения
    update_exchange_offer_status(offer_id, "cancelled")
    
    # Удаляем сообщение у получателя, если оно есть
    if offer["message_id"]:
        try:
            await bot.delete_message(offer["to_user_id"], offer["message_id"])
        except Exception as e:
            print(f"Не удалось удалить сообщение у получателя: {e}")
    
    await callback.answer("✅ Предложение отменено!", show_alert=False)
    await safe_edit_message(callback.message, "❌ Вы отменили свое предложение обмена.")

# Фоновая задача для очистки просроченных предложений
async def cleanup_expired_exchanges_task():
    """Background task to clean up expired exchange offers."""
    while True:
        from database.db import cleanup_expired_exchange_offers
        cleanup_expired_exchange_offers()
        await asyncio.sleep(3600)  # Check every hour
