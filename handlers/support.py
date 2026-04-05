import os, json

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.enums import ParseMode

from .keyboard import get_back_menu_button

router = Router()

SUPPORT_CHAT_ID = -1002454421703  # 🔁 Замените на ID вашего чата поддержки
COUNTER_PATH = "data/table/support_counter.json"
VOTES_PATH = "data/table/votes.json"

# === votes ===

def load_votes():
    if not os.path.exists(VOTES_PATH):
        return {}
    with open(VOTES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_votes(data):
    with open(VOTES_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def initialize_votes(idea_id: int):
    data = load_votes()
    data[str(idea_id)] = {"yes": 0, "no": 0}
    save_votes(data)

def vote_on_idea(idea_id: int, vote: str):
    data = load_votes()
    idea_key = str(idea_id)
    if idea_key not in data:
        data[idea_key] = {"yes": 0, "no": 0}
    if vote in data[idea_key]:
        data[idea_key][vote] += 1
    save_votes(data)

def get_votes(idea_id: int):
    data = load_votes()
    return data.get(str(idea_id), {"yes": 0, "no": 0})



# === counter ===
def load_counter():
    if not os.path.exists(COUNTER_PATH):
        return {"problems": 0, "ideas": 0}
    with open(COUNTER_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_counter(data: dict):
    with open(COUNTER_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def increment_problem_counter() -> int:
    counter = load_counter()
    counter["problems"] += 1
    save_counter(counter)
    return counter["problems"]

def increment_idea_counter() -> int:
    counter = load_counter()
    counter["ideas"] += 1
    save_counter(counter)
    return counter["ideas"]

# --- FSM ---
class SupportState(StatesGroup):
    waiting_for_problem = State()
    waiting_for_idea = State()

def resolved_button(user_id: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Решено", callback_data=f"resolved:{user_id}")]
        ]
    )

def idea_vote_markup(idea_id: int, user_id: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅", callback_data=f"vote_yes:{idea_id}"),
                InlineKeyboardButton(text="❌", callback_data=f"vote_no:{idea_id}")
            ],
            [InlineKeyboardButton(text="Подтвердить", callback_data=f"confirm_idea:{idea_id}:{user_id}")]
        ]
    )

# --- Проблема ---
@router.callback_query(F.data == "support_problem")
async def handle_problem_click(callback: CallbackQuery, state: FSMContext):
    await state.set_state(SupportState.waiting_for_problem)
    await callback.message.delete()
    await callback.message.answer("✍️ Опиши свою проблему, и мы постараемся помочь как можно скорее.(Изображения пока что не поддерживаются, если хотите отправить изображение, то напишите об этом в проблеме и с вами свяжутся.)", reply_markup=get_back_menu_button())

@router.message(SupportState.waiting_for_problem)
async def handle_problem_text(message: Message, state: FSMContext, bot: Bot):
    await state.clear()

    number = increment_problem_counter()
    user = message.from_user
    user_id = message.from_user.id
    text = (
        f"Проблема №{number}: Пользователь @{user.username or 'без username'} ({user.id}) сообщил о своей проблеме:\n\n"
        f"{message.text}"
    )



    messages_to_delete = [message.message_id - 1, message.message_id]
    await delete_messages(bot, message.chat.id, messages_to_delete)
    await message.answer("✅ Проблема отправлена в поддержку.", reply_markup=get_back_menu_button())
    await message.bot.send_message(
        SUPPORT_CHAT_ID,
        text,
        reply_markup=resolved_button(user_id),
        parse_mode=ParseMode.HTML
    )

@router.callback_query(F.data.startswith("resolved:"))
async def handle_resolved(callback: CallbackQuery):
    user_id = int(callback.data.split(":")[1])

        # Получаем исходный текст сообщения
    original_text = callback.message.text or ""

    # Если в тексте уже есть статус, удаляем его, чтобы не дублировать
    lines = original_text.splitlines()
    first_line = lines[0]
    statuses = ["В разработке", "Отказано"]
    if any(first_line.startswith(status) for status in statuses):
        lines = lines[1:]  # удаляем старый статус

        # Добавляем статус в начало
    new_text = "Решено\n\n\n" + "\n".join(lines)

    # Редактируем сообщение
    await callback.message.edit_text(new_text, reply_markup=None)
    await callback.message.bot.send_message(user_id, "✅ Ваша проблема была решена или будет решена в ближайшее время.")
    await callback.answer("Пользователю отправлено сообщение.")

# --- Идея ---
idea_counter = 1
votes = {}  # idea_id: {"yes": 0, "no": 0}

@router.callback_query(F.data == "support_idea")
async def handle_idea_click(callback: CallbackQuery, state: FSMContext):
    await state.set_state(SupportState.waiting_for_idea)
    await callback.message.delete()
    await callback.message.answer("💭 Опиши свою идею по улучшению бота.(Изображения пока что не поддерживаются, если хотите отправить изображение, то напишите об этом в проблеме и с вами свяжутся.)", reply_markup=get_back_menu_button())

async def delete_messages(bot: Bot, chat_id: int, message_ids: list[int]):
    for msg_id in message_ids:
        try:
            await bot.delete_message(chat_id, msg_id)
        except Exception as e:
            print(f"Ошибка при удалении сообщения {msg_id}: {e}")


@router.message(SupportState.waiting_for_idea)
async def handle_idea_text(message: Message, state: FSMContext, bot: Bot):
    await state.clear()

    number = increment_idea_counter()
    idea_id = number  # Используем номер идеи как ID
    user = message.from_user

    # Инициализируем голосование
    initialize_votes(idea_id)

    text = (
        f"Идея №{number}: Пользователь @{user.username or 'без username'} ({user.id}) предлагает идею по улучшению бота:\n\n"
        f"{message.text}"
    )

    messages_to_delete = [message.message_id - 1, message.message_id]
    await delete_messages(bot, message.chat.id, messages_to_delete)
    await message.answer("💡 Идея отправлена в поддержку.", reply_markup=get_back_menu_button())

    await message.bot.send_message(
        SUPPORT_CHAT_ID,
        text,
        reply_markup=idea_vote_markup(idea_id, user.id),
        parse_mode=ParseMode.HTML
    )

# --- Голосование ---
@router.callback_query(F.data.startswith("vote:"))
async def handle_vote(callback: CallbackQuery):
    _, vote_type, idea_id_str = callback.data.split(":")
    idea_id = int(idea_id_str)

    vote_on_idea(idea_id, vote_type)
    current_votes = get_votes(idea_id)

    text = f"Согласны: {current_votes['yes']}   Против: {current_votes['no']}"
    await callback.answer("Голос засчитан", show_alert=False)
    await callback.message.edit_reply_markup(reply_markup=idea_vote_markup(idea_id, callback.from_user.id, text))

def idea_vote_markup(idea_id: int, user_id: int, footer_text: str = "Согласны: 0   Против: 0"):
    buttons = [
        [
            InlineKeyboardButton(text="✅", callback_data=f"vote:yes:{idea_id}"),
            InlineKeyboardButton(text="❌", callback_data=f"vote:no:{idea_id}")
        ],
        [
            InlineKeyboardButton(text="Подтвердить", callback_data=f"confirm_idea:{idea_id}:{user_id}"),
            InlineKeyboardButton(text="Отказать", callback_data=f"reject_idea:{idea_id}:{user_id}")
        ],
        [InlineKeyboardButton(text=footer_text, callback_data="noop")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# --- Подтверждение ---
@router.callback_query(F.data.startswith("confirm_idea:"))
async def confirm_idea(callback: CallbackQuery):
    # пример разбора callback data
    _, idea_id_str, user_id_str = callback.data.split(":")
    idea_id = int(idea_id_str)
    user_id = int(user_id_str)

    # Получаем исходный текст сообщения
    original_text = callback.message.text or ""

    # Если в тексте уже есть статус, удаляем его, чтобы не дублировать
    lines = original_text.splitlines()
    first_line = lines[0]
    statuses = ["В разработке", "Отказано"]
    if any(first_line.startswith(status) for status in statuses):
        lines = lines[1:]  # удаляем старый статус

    # Добавляем статус в начало
    new_text = "В разработке\n\n\n" + "\n".join(lines)

    # Редактируем сообщение
    await callback.message.edit_text(new_text, reply_markup=None)
    await callback.message.pin(disable_notification=True)

    # Отправляем уведомление пользователю
    await callback.answer("Идея помечена как В разработке.")

    


@router.callback_query(F.data.startswith("reject_idea:"))
async def reject_idea(callback: CallbackQuery):
    _, idea_id_str, user_id_str = callback.data.split(":")
    idea_id = int(idea_id_str)
    user_id = int(user_id_str)

    original_text = callback.message.text or ""

    lines = original_text.splitlines()
    first_line = lines[0]
    statuses = ["В разработке", "Отказано"]
    if any(first_line.startswith(status) for status in statuses):
        lines = lines[1:]

    new_text = "Отказано\n\n\n" + "\n".join(lines)

    await callback.message.edit_text(new_text, reply_markup=None)
    await callback.answer("Идея помечена как Отказано.")