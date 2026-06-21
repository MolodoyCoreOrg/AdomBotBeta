import os
import random
import logging
import json
from google import genai
from google.genai import types

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Fallback presets if the Gemini API is unavailable or limits are reached
FALLBACK_PRESETS = [
    {
        "word": "клаута",
        "explanation": "'Клаут' (clout) — сленг, в данном контексте может означать влияние/статус, достигнутый через психотропное расширение сознания, и поэтому требует немедленного заглушения как часть скрытой наркотематики.",
        "duration": "420 секунд"
    },
    {
        "word": "соль",
        "explanation": "'Соль' — хотя в быту означает безобидную приправу, в современном цифровом пространстве является прямым триггером опасных синтетических солей. Бот считает упоминание подозрительным.",
        "duration": "2 часа"
    },
    {
        "word": "флексить",
        "explanation": "'Флекс' — указывает на выраженные неестественные изгибы опорно-двигательного аппарата под стимулятором. Попытка привлечь внимание карается заглушением.",
        "duration": "15 минут"
    },
    {
        "word": "чай",
        "explanation": "'Чай' — может использоваться в качестве тайного шифра или обходного наименования для растительных наркотических средств. Профилактическое заглушение.",
        "duration": "10 минут"
    },
    {
        "word": "код",
        "explanation": "'Код' — созвучно с популярным аптечным препаратом 'Кодеин'. Написание программного кода признано латентной формой кодеиновой пропаганды.",
        "duration": "1 час за кодерство"
    }
]

def analyze_message_for_drugs(text: str) -> dict:
    """
    Analyzes user text to find a random/critical word and generate a funny,
    absurd explanation of why it is drug propaganda. It uses the Gemini API.
    If the key is unavailable, it switches to a smart fallback algorithm.
    """
    # Prefer configuring via environment variable, but support direct key insertion
    api_key = os.getenv("GEMINI_API_KEY", "AQ.Ab8RN6IHA6WQVyTJtjqtfp6dh8cvhlx4gwN3OQhmUVsLXgUFeg")
    
    # Check if we have a valid key (avoiding dummy placeholders)
    if not api_key or "MY_GEMINI_API_KEY" in api_key or "AQ." not in api_key:
        logger.warning("No active Gemini API key found. Using hilarious fallback presets.")
        return get_offline_fallback(text)
        
    try:
        # Initialize Google GenAI Client (Modern SDK v2+)
        client = genai.Client(api_key=api_key)
        
        prompt = f"""
        Пользователь написал в чат следующее сообщение: "{text}".
        Твоя задача — взять ровно одно слово из этого сообщения и в забавной, абсурдной, карикатурной форме заявить, что оно пропагандирует наркотики (или является сленгом наркоманов/дилеров, или скрытым шифром).
        Будь максимально креативным и ироничным! Стиль должен быть строго псевдонаучным, притязательным, канцелярским стилем параноидального борца с пропагандой, который докапывается до любых мелочей.
        
        Возвращай ответ строго в формате JSON со следующими полями:
        - word: слово, которое мы затыкаем
        - explanation: уморительное подробное русское псевдонаучное объяснение связи этого слова со сленгом наркобизнеса
        - duration: забавная длительность блокировки (например: '420 секунд за чайную церемонию', '30 минут репрессий')
        """
        
        # We query the modern gemini-3.5-flash model
        response = client.models.generate_content(
            model='gemini-3.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction="Вы — юмористический бот AdomBot, который банит участников чата по абсурдным надуманным обвинениям в пропаганде наркотиков. Вы всегда отвечаете строго валидным JSON.",
                response_mime_type="application/json",
                response_schema={
                    "type": "OBJECT",
                    "properties": {
                        "word": {"type": "STRING"},
                        "explanation": {"type": "STRING"},
                        "duration": {"type": "STRING"}
                    },
                    "required": ["word", "explanation", "duration"]
                }
            )
        )
        
        # Parse output JSON
        data = json.loads(response.text.strip())
        return {
            "word": data.get("word", "слова"),
            "explanation": data.get("explanation", "Вызвал подозрение у модератора за скрытые метафоры."),
            "duration": data.get("duration", "10 минут")
        }
        
    except Exception as e:
        logger.error(f"Gemini API invocation failed: {e}. Falling back safely.")
        return get_offline_fallback(text)

def get_offline_fallback(text: str) -> dict:
    """
    Clever local offline generator that extracts a word from user's message
    and crafts a humorous drug-pretext reason using pre-coded formats.
    """
    words = [w.strip(".,!?\"'()«»") for w in text.split() if len(w) > 3]
    if not words:
        words = ["чат"]
        
    chosen_word = random.choice(words)
    preset = random.choice(FALLBACK_PRESETS)
    
    # Customize the preset template specifically targeting the user's word
    custom_explanation = preset["explanation"].replace(preset["word"], chosen_word)
    # Check if we need to adapt grammar or just return elegant phrasing
    if chosen_word.lower() not in custom_explanation.lower():
        custom_explanation = f"'{chosen_word}' — данное слово созвучно с запрещенной криптолексикой или {custom_explanation}"
        
    return {
        "word": chosen_word,
        "explanation": custom_explanation,
        "duration": preset["duration"]
    }
