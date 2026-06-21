import os
import random
import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    InlineQueryResultArticle, 
    InputTextMessageContent, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Import our customized Gemini generator
from ai_checker import analyze_message_for_drugs

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Core Bot Configuration (Token can be set in environment or fall back to dummy for export)
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Prebuilt funny classifications for the "Pidor-Meter"
PIDOR_CLASSIFICATIONS = [
    {"limit": 15, "desc": "Кристально чистый гетеросексуал. Икона маскулинности. (0-15%)"},
    {"limit": 40, "desc": "Латентный симпатяга. Подозрительно много времени проводит перед зеркалом. (16-40%)"},
    {"limit": 70, "desc": "Активный модник. Любит подкатанные джинсы и смузи с кокосовым молоком. (41-70%)"},
    {"limit": 90, "desc": "Классический представитель сверхразума. Живёт ради клаута, флексит без остановки. (71-90%)"},
    {"limit": 100, "desc": "Абсолютный Король Розового Фламинго! Пидораз 80-го уровня. Падайте ниц. (91-100%)"}
]

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    """
    Handler for /start command
    """
    welcome_text = (
        "👋 *Привет! Я AdomBot (Beta).* \n\n"
        "Я умею:\n"
        "1. **Карать за пропаганду:** Анализирую чат на рандомные слова и сочиняю "
        "уморительные обвинения в нелегальной пропаганде наркотиков 🔇.\n"
        "2. **Инлайн-режим «Пересчет пидаразов»:** Напиши `@AdomBot_bot` в любом чате, "
        "чтобы раздать тесты и составить списки!\n\n"
        "Закинь меня в группу, дай админку (чтобы я мог мутить), и шоу начнется!"
    )
    await message.reply(welcome_text, parse_mode="Markdown")

@dp.message(Command("check_drugs"))
async def cmd_check_drugs(message: types.Message):
    """
    Explicitly triggers the drug propaganda scanner on a replied message
    """
    target_msg = message.reply_to_message
    if not target_msg:
        await message.reply("⚠️ Эта команда должна быть ответом (reply) на сообщение, которое нужно проверить на пропаганду!")
        return
        
    text_to_check = target_msg.text or target_msg.caption
    if not text_to_check:
        await message.reply("❌ Сообщение не содержит текста для лингвистической экспертизы!")
        return

    # Indicate processing
    processing_msg = await message.reply("🔍 *Провожу лингвистическую экспертизу на предмет пропаганды...* 🧪", parse_mode="Markdown")
    
    # Analyze
    result = analyze_message_for_drugs(text_to_check)
    
    # Formulate message
    response_text = (
        f"« *{text_to_check}* »\n\n"
        f"🔇 *Заглушить:* {result['word']}\n"
        f"💬 {result['explanation']}\n\n"
        f"⏳ *Рекомендуемый срок:* {result['duration']}"
    )
    
    # Inline buttons for execution
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="🔕 Применить заглушение", callback_data=f"apply_mute:{target_msg.from_user.id}:{result['word']}"))
    builder.add(InlineKeyboardButton(text="🤷‍♂️ Понять и простить", callback_data="forgive_user"))
    
    await processing_msg.edit_text(response_text, parse_mode="Markdown", reply_markup=builder.as_markup())

@dp.message()
async def chat_message_listener(message: types.Message):
    """
    Listens to ordinary chat messages. Has a 5% random trigger rate,
    or triggers immediately if it detects certain classic slang/keywords.
    """
    if not message.text:
        return
        
    lower_text = message.text.lower()
    slang_triggers = ["клаут", "clout", "соли", "флекс", "газ", "трип", "пропаганда", "нарко"]
    
    # Trigger conditions
    is_trigger_word = any(trigger in lower_text for trigger in slang_triggers)
    is_random_chance = random.random() < 0.05  # 5% chance on any message
    
    if is_trigger_word or is_random_chance:
        # Prompt analysis
        result = analyze_message_for_drugs(message.text)
        
        response_text = (
            f"« *{message.text}* »\n\n"
            f"🔇 *Заглушить:* {result['word']}\n"
            f"💬 {result['explanation']}\n\n"
            f"⏳ *Рекомендуемый срок:* {result['duration']}"
        )
        
        builder = InlineKeyboardBuilder()
        builder.add(InlineKeyboardButton(text="🔕 Применить мут", callback_data=f"apply_mute:{message.from_user.id}:{result['word']}"))
        builder.add(InlineKeyboardButton(text="❌ Отклонить", callback_data="forgive_user"))
        
        await message.reply(response_text, parse_mode="Markdown", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("apply_mute"))
async def callback_apply_mute(callback: types.CallbackQuery):
    """
    Simulates or executes actual mute if bot is admin
    """
    parts = callback.data.split(":")
    user_id = int(parts[1])
    word = parts[2]
    
    try:
        # Try to enforce restrict member in Telegram (fails if not group admin)
        # We restrict member for 5 minutes
        await bot.restrict_chat_member(
            chat_id=callback.message.chat.id,
            user_id=user_id,
            permissions=types.ChatPermissions(can_send_messages=False),
            until_date=int(asyncio.get_event_loop().time()) + 300
        )
        await callback.message.reply(f"🔇 Пользователь [{user_id}] успешно заглушен в соответствии с заключением по слову '{word}'!")
    except Exception as e:
        # Graceful notice if permissions are missing (e.g. in DM or non-admin)
        await callback.answer(f"🔒 Недостаточно прав для мута, но экспертиза по слову '{word}' утверждена чатом!", show_alert=True)
        
    await callback.message.edit_reply_markup(reply_markup=None)

@dp.callback_query(F.data == "forgive_user")
async def callback_forgive(callback: types.CallbackQuery):
    await callback.answer("Администратор помиловал юзера. Экспертиза отправлена в архив.")
    await callback.message.edit_reply_markup(reply_markup=None)


# ==========================================
# INLINE MODE: «Пересчет пидаразов»
# ==========================================

@dp.inline_query()
async def inline_pidor_calculator(inline_query: types.InlineQuery):
    """
    Inline Query Handler for typing @AdomBot_bot
    Returns articles: Individual test, group statistics, and random scan.
    """
    user_id = inline_query.from_user.id
    username = inline_query.from_user.username or inline_query.from_user.first_name
    query_text = inline_query.query.strip()
    
    # Determine result parameters for random values
    # We seed based on user_id + day to keep the score persistent for the day!
    import datetime
    today_seed = int(datetime.date.today().strftime("%Y%m%d")) + user_id
    random.seed(today_seed)
    
    score = random.randint(0, 100)
    classification = PIDOR_CLASSIFICATIONS[0]["desc"]
    for cl in PIDOR_CLASSIFICATIONS:
        if score <= cl["limit"]:
            classification = cl["desc"]
            break
            
    # Reset seed to random for other dynamic elements
    random.seed()
    
    # 1. Individual Article Result
    individual_text = (
        f"📊 *ИНДИВИДУАЛЬНЫЙ ПИДОР-ТЕСТ* 📊\n\n"
        f"👤 Пользователь: @{username}\n"
        f"📈 Уровень совпадения: *{score}%*\n"
        f"📝 Вердикт: _{classification}_\n\n"
        f"⚡ _Проверено через AdomBot Beta Inline Scanner_"
    )
    
    item1 = InlineQueryResultArticle(
        id="pidor_individual",
        title="📈 Твой Пидор-Метр",
        description=f"Рассчитать твой % пидараза на сегодня. Сейчас у тебя: {score}%",
        input_message_content=InputTextMessageContent(
            message_text=individual_text,
            parse_mode="Markdown"
        ),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🔄 Пересчитать завтра", switch_inline_query_current_chat="")
        ]])
    )
    
    # 2. Interactive Pidor-of-the-day result selection
    scanning_text = (
        f"🚨 *ЗАПУЩЕН ИНЛАЙН-ПЕРЕСЧЕТ ПИДАРАЗОВ* 🚨\n\n"
        f"🔎 Локаторы развернуты. Идет глубокое сканирование участников чата...\n"
        f"🏳️‍🌈 Вероятность пидор-излучения: 99.8%\n\n"
        f"👉 Нажмите на кнопку ниже, чтобы узнать результат!"
    )
    
    item2 = InlineQueryResultArticle(
        id="pidor_day_game",
        title="👑 Выявить Пидора Дня",
        description="Запустить сканирование и случайный выбор пидора дня в текущем чате!",
        input_message_content=InputTextMessageContent(
            message_text=scanning_text,
            parse_mode="Markdown"
        ),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🔎 Показать результаты поиска", callback_data="reveal_pidor_of_day")
        ]])
    )

    # 3. Overall Stat Tally Article
    tally_text = (
        f"📊 *ОБЩАЯ СТАТИСТИКА ПЕРЕСЧЕТА* 📊\n\n"
        f"🏆 Топ-активисты чата:\n"
        f"1. @vlad_core — 32 раза застукан\n"
        f"2. @molodoy_dev — 24 раза застукан\n"
        f"3. @skater_boy — 15 раз застукан\n"
        f"4. @rayka — 12 раз застукан\n\n"
        f"📢 Проводите замеры чаще, чтобы разбавить статистику!"
    )
    
    item3 = InlineQueryResultArticle(
        id="pidor_global_stats",
        title="📊 Топ-Статистика Чата",
        description="Посмотреть доску почета и текущие результаты пересчета пидаразов",
        input_message_content=InputTextMessageContent(
            message_text=tally_text,
            parse_mode="Markdown"
        )
    )

    await inline_query.answer(
        results=[item1, item2, item3],
        cache_time=10,
        is_personal=True
    )


@dp.callback_query(F.data == "reveal_pidor_of_day")
async def callback_reveal_pidor(callback: types.CallbackQuery):
    """
    Fires on the inline message button to pick a random user from current chat members
    """
    user_name = callback.from_user.username or callback.from_user.first_name
    await callback.message.edit_text(
        f"⏳ *РАСШИФРОВКА СИГНАЛА...*\n\n"
        f"🛰 Сигнал получен со спутника.\n"
        f"Цель обнаружена... Обсчитываем координаты...",
        parse_mode="Markdown"
    )
    await asyncio.sleep(2)
    
    await callback.message.edit_text(
        f"🏆 *ОБЪЯВЛЕНИЕ ПОБЕДИТЕЛЯ* 🏆\n\n"
        f"Сегодня почетный титул 👑 *ПИДОР ДНЯ* 👑 присуждается:\n"
        f"👉 @{user_name} ! 🎉\n\n"
        f"💬 _Решение обжалованию не подлежит._",
        parse_mode="Markdown"
    )

# Async entry point
async def main():
    logger.info("Starting Telegram Bot Core (AdomBot)...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
