import random
import logging
from aiogram import Router, F
from aiogram.types import Message
from openai import AsyncOpenAI

from utils.config import LLM_API_KEY

router = Router()

# Инициализация клиента для работы с нейросетью
client = AsyncOpenAI(
    api_key=LLM_API_KEY,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)

# Шанс 1.0 означает, что бот будет отвечать на 100% сообщений. 
# Когда протестируете, можешь изменить это значение (например, 0.1 для 10%)
TRIGGER_CHANCE = 0.3

# Немного смягчили промпт, чтобы внутренние фильтры безопасности Google реже блокировали генерацию
SYSTEM_PROMPT = """Ты саркастичный и абсурдный бот-модератор чата. Твоя задача — взять одно совершенно случайное и безобидное слово из сообщения пользователя и придумать смешную, притянутую за уши причину, почему это слово якобы является скрытым сленгом для "запрещенных веществ" или их пропагандой. 
Твоя цель — рассмешить пользователей абсурдностью обвинения.

Отвечай СТРОГО в таком формате:
🔇 Заглушить: [слово]
💬 '[слово]' — [твоя смешная и абсурдная причина].

Пример:
Пользователь: я сегодня купил хлеб
Твой ответ:
🔇 Заглушить: хлеб
💬 'Хлеб' — известный в узких кругах сленг для обозначения прессованного гашиша, маскировка под пекарню является классической схемой контрабандистов."""

# Фильтр: реагируем ТОЛЬКО в группах и супергруппах, чтобы не лезть в личные сообщения бота (где пресейв)
@router.message(F.chat.type.in_({"group", "supergroup"}))
async def random_drug_moderator(message: Message):
    # Получаем текст сообщения (даже если это подпись к фото/видео)
    text = message.text or message.caption
    
    # Игнорируем пустые сообщения (например, просто стикеры) и команды (начинаются с /)
    if not text or text.startswith("/"):
        return
        
    # Проверка шанса срабатывания
    if random.random() > TRIGGER_CHANCE:
        logging.info(" [Drug Moderator] Сообщение пропущено по рандому.")
        return
        
    # Игнорируем слишком короткие сообщения (меньше 2 слов)
    if len(text.split()) < 2:
        logging.info(" [Drug Moderator] Сообщение слишком короткое.")
        return
        
    try:
        logging.info(f" [Drug Moderator] Проверяем сообщение в группе: '{text}'")
        
        # Запрос к нейросети Gemini
        response = await client.chat.completions.create(
            model="gemini-1.5-flash",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text}
            ],
            temperature=0.9,
            max_tokens=200
        )
        
        ai_text = response.choices[0].message.content.strip()
        
        # Отправка ответа в группу с привязкой к сообщению пользователя
        await message.reply(ai_text, parse_mode="HTML")
        logging.info(" [Drug Moderator] Успешный ответ!")
        
    except Exception as e:
        logging.error(f" [Drug Moderator] Ошибка при обращении к LLM: {e}")