import os
import datetime
from telebot import TeleBot, types
from storage import JSONRecountStorage

# Инициализация токена и хранилища
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN_HERE")
MAX_SLOTS = 100

bot = TeleBot(TOKEN)
storage = JSONRecountStorage("recount_data.json", MAX_SLOTS)

def get_mention(user_info: dict) -> str:
    """Генерирует кликабельное упоминание пользователя в Markdown"""
    if user_info.get("username"):
        return f"@{user_info['username']}"
    else:
        # Если юзернейма нет, делаем гиперссылку по Telegram ID
        first_name = user_info.get("first_name", "Пидараз")
        return f"[{first_name}](tg://user?id={user_info['id']})"

# 1. Команда /start
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    user = storage.get_user(user_id)
    bot_info = bot.get_me()

    if user and user.get("slot_number") is not None:
        bot.send_message(
            message.chat.id,
            f"🏳️‍🌈 *Вы уже зарегистрированы в системе!*\n\n"
            f"Ваш персональный номер: *Пидараз {user['slot_number']}*.\n\n"
            f"Теперь вы можете использовать инлайн-режим бота в любом чате! "
            f"Просто введите:\n`@{bot_info.username}` и выберите предложенный вариант.",
            parse_mode="Markdown"
        )
        return

    welcome_text = (
        f"🏳️‍🌈 *Добро пожаловать в Пересчет Пидаразов!*\n\n"
        f"Здесь ты можешь занять свой уникальный пожизненный номер пидараза (от 1 до {MAX_SLOTS}).\n\n"
        f"⚠️ *Важные правила:*\n"
        f"1. Номер выбирается ОДИН раз и изменить его нельзя.\n"
        f"2. Занятый номер никто другой занять не сможет.\n"
        f"3. Всего доступно ровно {MAX_SLOTS} слотов.\n\n"
        f"👇 *Как занять номер?*\n"
        f"Просто напиши мне в ответ любое число от 1 до {MAX_SLOTS}. Например: 7"
    )

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Посмотреть список занятых 🏳️‍🌈", callback_data="show_occupied_list"))

    bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown", reply_markup=markup)

# 2. Команда /list
@bot.message_handler(commands=['list'])
def list_slots(message):
    send_occupied_list(message.chat.id)

# Вспомогательная функция отправки списка
def send_occupied_list(chat_id: int):
    slots = storage.get_slots(MAX_SLOTS)
    users = storage.get_all_users()
    
    user_map = {u["id"]: u for u in users}
    occupied_slots = [s for s in slots if s["user_id"] is not None]

    if not occupied_slots:
        bot.send_message(
            chat_id,
            f"📭 Все слоты свободны!\n"
            f"Будь первым! Напиши число от 1 до {MAX_SLOTS}, чтобы зарезервировать номер."
        )
        return

    report = f"🏳️‍🌈 *Список зарегистрированных пидаразов ({len(occupied_slots)}/{MAX_SLOTS}):*\n\n"
    for slot in occupied_slots:
        u = user_map.get(slot["user_id"])
        if u:
            mention = get_mention(u)
            report += f"• *Пидараз {slot['number']}* — {mention} на связи\n"

    bot.send_message(chat_id, report, parse_mode="Markdown", disable_web_page_preview=True)

# 3. Админская команда ручной рассылки утреннего пересчета
@bot.message_handler(commands=['morning_recount_admin'])
def manual_morning_recount(message):
    bot.send_message(message.chat.id, "Запускаю утренний пересчет пидаразов...")
    trigger_morning_recount()
    bot.send_message(message.chat.id, "Рассылка запущена среди всех зарегистрированных!")

def trigger_morning_recount():
    users = storage.get_all_users()
    registered_users = [u for u in users if u.get("slot_number") is not None]

    for u in registered_users:
        try:
            slot_num = u["slot_number"]
            text = (
                f"⏰ *ПЕРЕСЧЕТ ПИДАРАЗОВ!*\n\n"
                f"Пидараз *{slot_num}* на связи??? Подтверди присутствие!"
            )
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton(
                f"🙋‍♂️ Пидараз {slot_num} на связи!", 
                callback_data=f"checkin_{slot_num}"
            ))
            bot.send_message(u["id"], text, parse_mode="Markdown", reply_markup=markup)
        except Exception as e:
            print(f"Не удалось отправить уведомление пользователю {u['id']}: {e}")

# 4. Обработка кнопок (Callback)
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    if call.data == "show_occupied_list":
        bot.answer_callback_query(call.id)
        send_occupied_list(call.message.chat.id)
        return

    if call.data.startswith("checkin_"):
        slot_num = int(call.data.split("_")[1])
        user_id = call.from_user.id
        date_str = datetime.date.today().isoformat()

        user = storage.get_user(user_id)
        if not user or user.get("slot_number") != slot_num:
            bot.answer_callback_query(call.id, "Это не твой номер или ты не зарегистрирован!", show_alert=True)
            return

        success = storage.record_check_in(user_id, date_str)
        if not success:
            bot.answer_callback_query(call.id, "Вы уже отметились сегодня как 'на связи'!", show_alert=True)
            return

        bot.answer_callback_query(call.id, "Вы успешно подтвердили свое присутствие!")
        
        # Обновляем сообщение (убираем кнопку)
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"✅ Пидараз {slot_num} на связи! Присутствие подтверждено."
        )

        # Рассылаем всем остальным пользователям оповещение
        all_users = storage.get_all_users()
        mention = get_mention(user)
        broadcast_text = f"📣 *Пересчет:* Пидараз *{slot_num}* ({mention}) на связи!"

        for recipient in all_users:
            try:
                bot.send_message(recipient["id"], broadcast_text, parse_mode="Markdown")
            except Exception:
                pass # Игнорируем заблокированные чаты

# 5. Выбор номера через обычный текст
@bot.message_handler(func=lambda message: True)
def handle_text_message(message):
    text = message.text.strip()
    user_id = message.from_user.id

    try:
        num = int(text)
    except ValueError:
        # Если прислали текст, а не число
        user = storage.get_user(user_id)
        if not user or user.get("slot_number") is None:
            bot.reply_to(message, f"Чтобы занять слот, введи число от 1 до {MAX_SLOTS}. Например: 7")
        return

    success, error = storage.choose_slot(
        user_id=user_id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        last_name=message.from_user.last_name,
        slot_number=num
    )

    if success:
        bot_info = bot.get_me()
        bot.reply_to(
            message,
            f"🎉 *Поздравляем!*\n\n"
            f"Вы успешно забронировали слот *#{num}*.\n"
            f"Отныне и вовек вы отмечены как *Пидараз {num}*!\n\n"
            f"Используйте инлайн-режим в любом чате: просто введите `@{bot_info.username}`.",
            parse_mode="Markdown"
        )
    else:
        bot.reply_to(message, f"❌ Ошибка: {error}")

# 6. Обработка Инлайн Запросов
@bot.inline_handler(lambda query: True)
def handle_inline_query(query):
    user_id = query.from_user.id
    user = storage.get_user(user_id)
    bot_info = bot.get_me()

    results = []
    
    if user and user.get("slot_number") is not None:
        slot_num = user["slot_number"]
        mention = get_mention(user)
        msg_text = f"🏳️‍🌈 Пидараз {slot_num} ({mention}) на связи!"

        item = types.InlineQueryResultArticle(
            id=f"pidaraz_{slot_num}",
            title="Пересчет Пидаразов",
            description=f"Отправить: 'Пидараз {slot_num} на связи'",
            input_message_content=types.InputTextMessageContent(
                message_text=msg_text,
                parse_mode="Markdown"
            )
        )
        results.append(item)
    else:
        # Если у пользователя нет номера
        start_link = f"https://t.me/{bot_info.username}?start=choose"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Выбрать номер 🏳️‍🌈", url=start_link))

        item = types.InlineQueryResultArticle(
            id="no_number_found",
            title="Я безномерный пидараз 🤷‍♂️",
            description="У вас ещё нет номера. Нажмите для перехода к выбору.",
            input_message_content=types.InputTextMessageContent(
                message_text="Я безномерный пидараз... 🤷‍♂️\n\nМне нужно зайти в бота и занять слот!",
                parse_mode="Markdown"
            ),
            reply_markup=markup
        )
        results.append(item)

    bot.answer_inline_query(query.id, results, is_personal=True, cache_time=0)

if __name__ == "__main__":
    print("Бот успешно запущен и слушает запросы...")
    bot.infinity_polling()
