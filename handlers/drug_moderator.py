import random
import logging
from aiogram import Router, F
from aiogram.types import Message
from openai import AsyncOpenAI

from utils.config import LLM_API_KEY

router = Router()

# Инициализация клиента для работы с нейросетью
# Используем корректный путь для Google Gemini
client = AsyncOpenAI(
    api_key=LLM_API_KEY,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)

# Вероятность срабатывания бота (0.3 = 30%)
TRIGGER_CHANCE = 0.3

SYSTEM_PROMPT = """Ты саркастичный и немного поехавший бот-модератор. Твоя задача — взять одно совершенно случайное и безобидное слово из сообщения пользователя и придумать абсурдную, притянутую за уши причину, почему это слово якобы является сленгом для наркотиков или их пропагандой.

Отвечай СТРОГО в таком формате:
🔇 Заглушить: [слово]
💬 '[слово]' — [твоя смешная и абсурдная причина].

Пример:
Пользователь: я сегодня купил хлеб
Твой ответ:
🔇 Заглушить: хлеб
💬 'Хлеб' — известный в узких кругах сленг для обозначения прессованного гашиша, маскировка под пекарню является классической схемой наркоторговцев."""

@router.message(F.text & ~F.text.startswith("/"))
async def random_drug_moderator(message: Message):
    # 1. Проверяем шанс срабатывания
    if random.random() > TRIGGER_CHANCE:
        logging.info(" [Drug Moderator] Сообщение пропущено по рандому (шанс 30%).")
        return
        
    # 2. Если сообщение слишком короткое, пропускаем
    if len(message.text.split()) < 2:
        logging.info(" [Drug Moderator] Сообщение слишком короткое (< 2 слов).")
        return
        
    try:
        logging.info(f" [Drug Moderator] Сработало на сообщение: '{message.text}'. Отправляю запрос в Gemini...")
        
        # 3. Делаем асинхронный запрос к нейросети (используем модель Gemini)
        response = await client.chat.completions.create(
            model="gemini-1.5-flash",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": message.text}
            ],
            temperature=0.8,
            max_tokens=150
        )
        
        # Получаем сгенерированный текст
        ai_text = response.choices[0].message.content.strip()
        
        # 4. Отправляем ответ в чат
        await message.reply(ai_text, parse_mode="HTML")
        logging.info(" [Drug Moderator] Ответ успешно отправлен в чат!")
        
    except Exception as e:
        logging.error(f" [Drug Moderator] Ошибка при обращении к LLM: {e}")