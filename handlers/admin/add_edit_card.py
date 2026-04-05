# ADMIN_IDS = {1114626593, 347632821, 462179661, 776301286}  # тут твои ID админов
import os, json, sqlite3, re, logging

from aiogram import types, Router, F
from aiogram.types import Message, FSInputFile, CallbackQuery, ContentType
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
from utils.helpers import safe_edit_message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from handlers.keyboard import (
get_rarity_keyboard,

get_sort_member_menu_keyboard,
get_list_member_keyboard,
get_edit_mode_member_keyboard,
get_rank_images_keyboard, 
get_rank_select_keyboard, 
get_member_list_page_keyboard,

get_edit_mode_skill_keyboard,
get_list_skill_keyboard,
get_skill_list_page_keyboard,
get_sort_skill_menu_keyboard,
)
from handlers.picture import find_image_file
from utils.config import ADMINS_LIST, RARITY_WEIGHTS
from handlers.keyboard import get_list_kazin_keyboard, get_edit_mode_kazin_keyboard

router = Router()

DB_PATH = "database/users.db"

def connect():
    return sqlite3.connect(DB_PATH)

async def is_admin(user_id: int) -> bool:
    ADMINS = ADMINS_LIST  # например, список айдишников админов
    return user_id in ADMINS











# --- Кнопка сортировки ---

@router.callback_query(lambda c: c.data and c.data.startswith("sort_member_menu"))
async def show_sort_member_menu(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    keyboard = get_sort_member_menu_keyboard()
    await safe_edit_message(callback.message, "Выберите способ сортировки:", reply_markup=keyboard)

@router.callback_query(lambda c: c.data and c.data.startswith("sort_skill_menu"))
async def show_sort_skill_menu(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    keyboard = get_sort_skill_menu_keyboard()
    await safe_edit_message(callback.message, "Выберите способ сортировки:", reply_markup=keyboard)



# --- Сортировка по редкости ---

@router.callback_query(lambda c: c.data and c.data.startswith("sort_member_by_rarity"))
async def sort_member_by_rarity(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    cards_member = load_member_cards()
    rarity_order = {"Обычная": 0, "Редкая": 1, "Эпическая": 2, "Легендарная": 3}
    cards_member.sort(key=lambda c: rarity_order.get(c.get("rarity", "Обычная"), 0))

    save_member_cards(cards_member)
    # Показываем первую карточку отсортированного списка
    await send_member_card(callback, 0)

# --- Сортировка по имени (алфавит) ---

@router.callback_query(lambda c: c.data and c.data.startswith("sort_member_by_name"))
async def sort_member_by_name(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return


    cards_member = load_member_cards()
    cards_member.sort(key=lambda c: c.get("name", "").lower())

    save_member_cards(cards_member)
    await send_member_card(callback, 0)






# --- Сортировка по редкости ---

@router.callback_query(lambda c: c.data and c.data.startswith("sort_skill_by_rarity"))
async def sort_skill_by_rarity(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    cards_skill = load_skill_cards()
    rarity_order = {"Обычная": 0, "Редкая": 1, "Эпическая": 2, "Легендарная": 3}
    cards_skill.sort(key=lambda c: rarity_order.get(c.get("rarity", "Обычная"), 0))

    save_skill_cards(cards_skill)
    # Показываем первую карточку отсортированного списка
    await send_skill_card(callback, 0)

# --- Сортировка по имени (алфавит) ---

@router.callback_query(lambda c: c.data and c.data.startswith("sort_skill_by_name"))
async def sort_skill_by_name(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return


    cards_skill = load_skill_cards()
    cards_skill.sort(key=lambda c: c.get("name", "").lower())

    save_skill_cards(cards_skill)
    await send_skill_card(callback, 0)




















#ДОБАВЛЕНИЕ КАРТОЧЕК

# Пути
MEMBERS_JSON = "data/cards/members.json"
SKILLS_JSON = "data/cards/skills.json"
MEMBER_IMG_PATH = "data/images/members"
SKILL_IMG_PATH = "data/images/skills"

# FSM states
class AddMember(StatesGroup):
    waiting_for_image = State()
    waiting_for_name = State()
    waiting_for_skill = State()
    waiting_for_rarity = State()

class AddSkill(StatesGroup):
    waiting_for_image = State()
    waiting_for_name = State()
    waiting_for_rarity = State()

# Шансы выпадения по редкости
RARITY_CHANCES = RARITY_WEIGHTS

# Функция для очистки имени файла (разрешает латиницу, кириллицу, цифры, -, _)
def sanitize_filename(name: str) -> str:
    return re.sub(r'[^\w\-]', '_', name, flags=re.UNICODE)

# === MEMBER ===
# redefine AddMember to include waiting_for_work
class AddMember(StatesGroup):
    waiting_for_image = State()
    waiting_for_name = State()
    waiting_for_skill = State()
    waiting_for_work = State()
    waiting_for_rarity = State()

@router.message(Command("addmember"))
async def start_add_member(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        await message.answer("🚫 Только админы могут использовать эту команду.")
        return
    await message.answer("Пришли изображение участника (только для 1 ранга!)")
    await state.set_state(AddMember.waiting_for_image)

@router.message(AddMember.waiting_for_image, F.photo)
async def member_get_image(message: Message, state: FSMContext):
    await state.update_data(photo=message.photo[-1].file_id)
    await message.answer("Теперь введи имя участника")
    await state.set_state(AddMember.waiting_for_name)

@router.message(AddMember.waiting_for_name)
async def member_get_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Теперь укажи его суперспособность")
    await state.set_state(AddMember.waiting_for_skill)

@router.message(AddMember.waiting_for_skill)
async def member_get_skill(message: Message, state: FSMContext):
    await state.update_data(skill=message.text)

    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="Участник объединения", callback_data="work:participant"),
        types.InlineKeyboardButton(text="Саппортер", callback_data="work:supporter"),
        types.InlineKeyboardButton(text="Победитель конкурса", callback_data="work:concurswinner"),
        width=3
    )

    await message.answer(
        "Выберите звание участника:",
        reply_markup=builder.as_markup()
    )
    await state.set_state(AddMember.waiting_for_work)

@router.callback_query(AddMember.waiting_for_work)
async def member_get_work(callback: CallbackQuery, state: FSMContext):
    data_val = callback.data or ""
    # normalize to human-readable label
    if data_val == "work:participant":
        work_label = "Участник объединения"
    elif data_val == "work:supporter":
        work_label = "Саппортер"
    elif data_val == "work:concurswinner":
        work_label = "Победитель конкурса"
    elif data_val in ("Участник объединения", "Саппортер", "Победитель конкурса"):
        work_label = data_val
    else:
        await callback.answer("Неверный выбор", show_alert=True)
        return

    await state.update_data(work=work_label)

    await callback.message.answer("Выбери редкость участника:", reply_markup=get_rarity_keyboard())
    await state.set_state(AddMember.waiting_for_rarity)

@router.callback_query(AddMember.waiting_for_rarity)
async def member_get_rarity(callback: CallbackQuery, state: FSMContext):
    rarity = callback.data
    if rarity not in RARITY_CHANCES:
        await callback.answer("Неверная редкость", show_alert=True)
        return

    data = await state.get_data()
    photo_id = data.get("photo")
    name = data.get("name")
    skill = data.get("skill")
    work = data.get("work", "")  # новое поле

    if not (photo_id and name and skill):
        await callback.answer("Ошибка: не все данные указаны.", show_alert=True)
        await state.clear()
        return

    sanitized_name = sanitize_filename(name)

    # Загружаем текущих участников
    if os.path.exists(MEMBERS_JSON):
        with open(MEMBERS_JSON, "r", encoding="utf-8") as f:
            data_list = json.load(f)
    else:
        data_list = []

    # Проверка дубликата имени
    if any(member["name"].lower() == name.lower() for member in data_list):
        await callback.answer("❗ Участник с таким именем уже существует!", show_alert=True)
        return

    # Скачиваем изображение
    file = await callback.bot.get_file(photo_id)
    image_dir = f"{MEMBER_IMG_PATH}/rank_1"
    os.makedirs(image_dir, exist_ok=True)
    image_path = f"{image_dir}/{sanitized_name}.jpg"
    await callback.bot.download_file(file.file_path, image_path)

    # Добавляем участника (только базовое изображение)
    member_card = {
        "name": name,
        "skill": skill,
        "rarity": rarity,
        "work": work,  # сохраняем звание
        "image": f"{sanitized_name}.jpg"  # Только 1 ранг
    }

    data_list.append(member_card)
    with open(MEMBERS_JSON, "w", encoding="utf-8") as f:
        json.dump(data_list, f, indent=4, ensure_ascii=False)

    await callback.message.answer(f"✅ Участник '{name}' успешно добавлен.")
    print(f"[LOG] Добавлен участник: {name} (work: {work})")
    await state.clear()

# === SKILL ===
@router.message(Command("addskill"))
async def start_add_skill(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        await message.answer("🚫 Только админы могут использовать эту команду.")
        return
    await message.answer("Пришли изображение суперспособности")
    await state.set_state(AddSkill.waiting_for_image)

@router.message(AddSkill.waiting_for_image, F.photo)
async def skill_get_image(message: Message, state: FSMContext):
    await state.update_data(photo=message.photo[-1].file_id)
    await message.answer("Теперь введи название суперспособности")
    await state.set_state(AddSkill.waiting_for_name)

@router.message(AddSkill.waiting_for_name)
async def skill_get_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Выбери редкость суперспособности:", reply_markup=get_rarity_keyboard())
    await state.set_state(AddSkill.waiting_for_rarity)

@router.callback_query(AddSkill.waiting_for_rarity)
async def skill_get_rarity(callback: CallbackQuery, state: FSMContext):
    rarity = callback.data
    if rarity not in RARITY_CHANCES:
        await callback.answer("Неверная редкость", show_alert=True)
        return

    data = await state.get_data()
    photo_id = data["photo"]
    name = data["name"]

    sanitized_name = sanitize_filename(name)

    # Загружаем текущие суперспособности
    if os.path.exists(SKILLS_JSON):
        with open(SKILLS_JSON, "r", encoding="utf-8") as f:
            data_list = json.load(f)
    else:
        data_list = []

    # Проверяем дубликат имени (без учёта регистра)
    if any(skill["name"].lower() == name.lower() for skill in data_list):
        await callback.answer("❗ Суперспособность с таким именем уже существует!", show_alert=True)
        return

    file = await callback.bot.get_file(photo_id)
    path = f"{SKILL_IMG_PATH}/{sanitized_name}.jpg"
    await callback.bot.download_file(file.file_path, path)

    skill_card = {
        "name": name,
        "rarity": rarity,
        "image": f"{sanitized_name}.jpg"
    }

    data_list.append(skill_card)
    with open(SKILLS_JSON, "w", encoding="utf-8") as f:
        json.dump(data_list, f, indent=4, ensure_ascii=False)

    await callback.message.answer(f"Суперспособность '{name}' добавлена.")
    print(f"Добавлена новая суперспособность '{name}'")
    await state.clear()














    

# === EDIT CARD ===

MEMBER_CARDS_PATH = "data/cards/members.json"
IMAGES_PATH = "data/images/members/rank_1"
IMAGES_PATH_MAIN = "data/images/members"

class EditMemberCardStates(StatesGroup):
    waiting_for_member_name = State()
    waiting_for_member_skill = State()
    waiting_for_member_rarity = State()
    waiting_for_rank_image_upload = State()

# --- Загрузка/сохранение карт ---

def load_member_cards():
    if not os.path.exists(MEMBER_CARDS_PATH):
        return []
    with open(MEMBER_CARDS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_member_cards(cards):
    try:
        with open(MEMBER_CARDS_PATH, "w", encoding="utf-8") as f:
            json.dump(cards, f, indent=4, ensure_ascii=False)
    except Exception as e:
        logging.error(f"Ошибка при сохранении карточек: {e}")

# --- Форматирование карточки ---

def format_card_text(card):
    return (
    f"<b>{card['name']}</b>\n"
    f"💡 Суперспособность: <i>{card.get('skill', '—')}</i>\n"
    f"🏷 Звание: <i>{card.get('work', '—')}</i>\n"
    f"⭐ Редкость: <b>{card.get('rarity', '—')}</b>"
    )

def find_image_file(name_without_ext: str, folder: str):
    # ищем файл изображения в папке (без рангов, только основное)
    for ext in ['.jpg', '.jpeg', '.png', '.webp']:
        path = os.path.join(folder, f"{name_without_ext}{ext}")
        if os.path.exists(path):
            return path
    # fallback
    return os.path.join(folder, f"{name_without_ext}.jpg")

# --- Отправка карточки с навигацией ---

async def send_member_card(message_or_cb, index: int, edit_mode=False):
    cards = load_member_cards()
    total = len(cards)
    if index < 0 or index >= total:
        if hasattr(message_or_cb, "answer"):
            await message_or_cb.answer("Карточка не найдена.")
        else:
            await message_or_cb.answer("Карточка не найдена.", show_alert=True)
        return

    card = cards[index]
    image_path = find_image_file(card["image"].split(".")[0], IMAGES_PATH)
    if not os.path.exists(image_path):
        if hasattr(message_or_cb, "answer"):
            await message_or_cb.answer("Изображение карточки не найдено.")
        else:
            await message_or_cb.answer("Изображение карточки не найдено.", show_alert=True)
        return

    photo = FSInputFile(image_path)
    caption = format_card_text(card)

    # При показе карточки внизу клавиатура с навигацией и кнопкой "Редактировать" или без
    keyboard = get_edit_mode_member_keyboard(index, total) if edit_mode else get_list_member_keyboard(index, total, prefix="edit_member_cards")

    # Чтобы реализовать нажатие по центру (index/total) - callback "show_member_list:{page}"
    # Мы просто заменим центральную кнопку на callback с префиксом "show_member_list"

    # Исправим клавиатуру под центральную кнопку (делается в клавиатуре, предположу, что уже сделано)

    if isinstance(message_or_cb, Message):
        await message_or_cb.answer_photo(photo=photo, caption=caption, reply_markup=keyboard)
    else:
        try:
            await message_or_cb.message.edit_media(
                media=types.InputMediaPhoto(media=photo, caption=caption),
                reply_markup=keyboard
            )
        except TelegramBadRequest:
            await message_or_cb.message.answer_photo(photo=photo, caption=caption, reply_markup=keyboard)








# --- Обработка команды /members ---

@router.message(Command("members"))
async def cmd_members(message: Message):
    if not await is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к этой команде.")
        return
    cards = load_member_cards()
    if not cards:
        await message.answer("Список карточек пуст.")
        return
    await send_member_card(message, 0, edit_mode=False)








# --- Навигация по карточкам (следующая, предыдущая) ---

@router.callback_query(lambda c: c.data and c.data.startswith("edit_member_cards:navigate"))
async def navigate_cards(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    parts = callback.data.split(":")
    if len(parts) != 4:
        await callback.answer("⚠️ Некорректные данные", show_alert=True)
        return

    _, _, direction, current_index_str = parts
    current_index = int(current_index_str)

    cards = load_member_cards()
    if direction == "next":
        new_index = current_index + 1 if current_index + 1 < len(cards) else current_index
    elif direction == "prev":
        new_index = current_index - 1 if current_index - 1 >= 0 else current_index
    else:
        new_index = current_index

    await send_member_card(callback, new_index)









# --- При нажатии на центральную кнопку с номером показываем список карточек постранично ---

@router.callback_query(lambda c: c.data and c.data.startswith("show_member_list:"))
async def show_member_list(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    page = int(callback.data.split(":")[1])
    cards = load_member_cards()
    total = len(cards)
    per_page = 10
    total_pages = (total + per_page - 1) // per_page

    # Корректируем страницу
    if page < 0:
        page = 0
    if page >= total_pages:
        page = total_pages - 1

    keyboard = get_member_list_page_keyboard(page, per_page, total, cards, prefix="select_member_card")

    text = f"Список карточек, страница {page+1}/{total_pages}:"
    # Можно вывести список названий карт, но они уже в кнопках — необязательно повторять

    # Отправляем или редактируем сообщение
    try:
        await safe_edit_message(callback.message, text, reply_markup=keyboard)
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=keyboard)

# --- Навигация по страницам списка карт ---

@router.callback_query(lambda c: c.data and c.data.startswith("navigate_member_page:"))
async def navigate_member_page(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    page = int(callback.data.split(":")[1])
    cards = load_member_cards()
    total = len(cards)
    per_page = 10
    total_pages = (total + per_page - 1) // per_page

    if page < 0:
        page = 0
    if page >= total_pages:
        page = total_pages - 1

    keyboard = get_member_list_page_keyboard(page, per_page, total, cards, prefix="select_member_card")
    text = f"Список карточек, страница {page+1}/{total_pages}:"
    try:
        await safe_edit_message(callback.message, text, reply_markup=keyboard)
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=keyboard)

# --- При выборе карты из списка возвращаемся к просмотру карты ---

@router.callback_query(lambda c: c.data and c.data.startswith("select_member_card:"))
async def select_member_card(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    index = int(callback.data.split(":")[1])
    await send_member_card(callback, index, edit_mode=False)








# --- Вход в режим редактирования карты ---

@router.callback_query(lambda c: c.data and c.data.startswith("edit_mode_member_cards"))
async def enter_member_edit_mode(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    _, index_str = callback.data.split(":")
    index = int(index_str)
    await send_member_card(callback, index, edit_mode=True)

# --- Редактирование имени ---

@router.callback_query(lambda c: c.data and c.data.startswith("edit_member_name:"))
async def handle_edit_member_name(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    index = int(callback.data.split(":")[1])
    await callback.message.answer(f"Введите новое имя для карточки #{index + 1}:")
    await state.update_data(edit_index=index)
    await state.set_state(EditMemberCardStates.waiting_for_member_name)

@router.message(EditMemberCardStates.waiting_for_member_name)
async def process_new_member_name(message: Message, state: FSMContext):
    data = await state.get_data()
    index = data.get("edit_index")
    cards = load_member_cards()
    if index is None or index >= len(cards):
        await message.answer("Ошибка: карточка не найдена.")
        await state.clear()
        return
    cards[index]["name"] = message.text.strip()
    save_member_cards(cards)
    await message.answer("Имя успешно изменено.")
    await send_member_card(message, index, edit_mode=True)
    await state.clear()




# --- Редактирование способности ---

@router.callback_query(lambda c: c.data and c.data.startswith("edit_member_skill:"))
async def handle_edit_member_skill(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    index = int(callback.data.split(":")[1])
    await callback.message.answer(f"Введите новую суперспособность для карточки #{index + 1}:")
    await state.update_data(edit_index=index)
    await state.set_state(EditMemberCardStates.waiting_for_member_skill)

@router.message(EditMemberCardStates.waiting_for_member_skill)
async def process_new_member_skill(message: Message, state: FSMContext):
    data = await state.get_data()
    index = data.get("edit_index")
    cards = load_member_cards()
    if index is None or index >= len(cards):
        await message.answer("Ошибка: карточка не найдена.")
        await state.clear()
        return
    cards[index]["skill"] = message.text.strip()
    save_member_cards(cards)
    await message.answer("Суперспособность успешно изменена.")
    await send_member_card(message, index, edit_mode=True)
    await state.clear()

# --- Редактирование редкости ---

@router.callback_query(lambda c: c.data and c.data.startswith("edit_member_rarity:"))
async def handle_edit_member_rarity(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    index = int(callback.data.split(":")[1])
    await callback.message.answer(
        f"Введите новую редкость для карточки #{index + 1}:", reply_markup=get_rarity_keyboard())
    await state.update_data(edit_index=index)
    await state.set_state(EditMemberCardStates.waiting_for_member_rarity)

@router.callback_query(EditMemberCardStates.waiting_for_member_rarity)
async def process_new_member_rarity_callback(callback: CallbackQuery, state: FSMContext):
    rarity = callback.data.strip().capitalize()
    valid_rarities = ["Обычная", "Редкая", "Эпическая", "Легендарная"]

    if rarity not in valid_rarities:
        await callback.answer("⚠ Неверная редкость.", show_alert=True)
        return

    data = await state.get_data()
    index = data.get("edit_index")
    cards = load_member_cards()

    if index is None or index >= len(cards):
        await callback.message.answer("Ошибка: карточка не найдена.")
        await state.clear()
        return

    cards[index]["rarity"] = rarity
    save_member_cards(cards)

    await callback.message.answer(f"✅ Редкость успешно изменена на «{rarity}».")
    await send_member_card(callback, index, edit_mode=True)
    await state.clear()


# --- Изменение звания (work) ---
@router.callback_query(lambda c: c.data and c.data.startswith("edit_member_work:"))
async def handle_edit_member_work(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    index = int(callback.data.split(":")[1])

    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(
            text="Участник объединения",
            callback_data=f"set_work:{index}:Участник объединения"
        ),
        types.InlineKeyboardButton(
            text="Саппортер",
            callback_data=f"set_work:{index}:Саппортер"
        ),
        types.InlineKeyboardButton(
            text="Победитель конкурса",
            callback_data=f"set_work:{index}:Победитель конкурса"
        ),
        width=2
    )
    builder.row(
        types.InlineKeyboardButton(
            text="🔙 Отмена",
            callback_data=f"back_to_edit:{index}"
        )
    )

    await safe_edit_message(callback.message,
        "Выберите новое звание:",
        reply_markup=builder.as_markup()
    )


@router.callback_query(lambda c: c.data and c.data.startswith("set_member_work:"))
async def handle_set_member_work(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    parts = callback.data.split(":", 2)
    if len(parts) != 3:
        await callback.answer("⚠ Некорректные данные", show_alert=True)
        return
    index = int(parts[1])
    new_work = parts[2]

    cards = load_member_cards()
    if index < 0 or index >= len(cards):
        await callback.answer("Карточка не найдена.", show_alert=True)
        return

    cards[index]["work"] = new_work
    save_member_cards(cards)

    await callback.message.answer(f"✅ Звание карточки #{index+1} обновлено: {new_work}")
    # Вернуться в режим редактирования, показывая обновлённую карточку
    await send_member_card(callback, index, edit_mode=True)

# --- Возврат из режима редактирования ---

@router.callback_query(lambda c: c.data and c.data.startswith("back_to_member_list:"))
async def handle_back_to_member_list(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    index = int(callback.data.split(":")[1])
    await send_member_card(callback, index, edit_mode=False)

# --- ПОКАЗ ИЗОБРАЖЕНИЙ РАНГОВ ---

@router.callback_query(lambda c: c.data and c.data.startswith("show_member_rank_images:"))
async def show_member_rank_images(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    parts = callback.data.split(":")
    index = int(parts[1])
    rank = int(parts[2]) if len(parts) > 2 else 1  # <-- вот тут

    cards = load_member_cards()
    if index < 0 or index >= len(cards):
        await callback.answer("Карточка не найдена.", show_alert=True)
        return
    card = cards[index]

    rank_folder = os.path.join(IMAGES_PATH_MAIN, f"rank_{rank}")
    image_file_name = card.get("image", "")
    image_path = find_image_file(os.path.splitext(image_file_name)[0], rank_folder)
    caption = f"Изображение ранга {rank}"

    photo = FSInputFile(image_path) if os.path.exists(image_path) else None

    keyboard = get_rank_images_keyboard(index, rank)
    if photo:
        try:
            await callback.message.edit_media(
                media=types.InputMediaPhoto(media=photo, caption=caption),
                reply_markup=keyboard
            )
        except TelegramBadRequest:
            await callback.message.answer_photo(photo=photo, caption=caption, reply_markup=keyboard)
    else:
        await callback.message.edit_media(
                media=types.InputMediaPhoto(media=photo, caption=f"Изображение ранга {rank} не найдено."),
                reply_markup=keyboard
            )

# --- Добавить изображение ранга (вывод выбора ранга) ---

@router.callback_query(lambda c: c.data and c.data.startswith("add_member_rank_image:"))
async def add_member_rank_image(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    index = int(callback.data.split(":")[1])
    keyboard = get_rank_select_keyboard(index)
    cards = load_member_cards()
    if index < 0 or index >= len(cards):
        await callback.answer("Карточка не найдена.", show_alert=True)
        return
    card = cards[index]

    rank = 1
    rank_folder = os.path.join(IMAGES_PATH_MAIN, f"rank_{rank}")
    image_file_name = card.get("image", "")
    image_path = find_image_file(os.path.splitext(image_file_name)[0], rank_folder)
    photo = FSInputFile(image_path) if os.path.exists(image_path) else None

    await callback.message.edit_media(
                media=types.InputMediaPhoto(media=photo, caption=f"Выберите ранг для загрузки изображения:"),
                reply_markup=keyboard
            )

# --- Выбор ранга для загрузки изображения ---

@router.callback_query(lambda c: c.data and c.data.startswith("upload_rank_image:"))
async def upload_rank_image(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer("⚠ Некорректные данные.", show_alert=True)
        return

    index = int(parts[1])
    rank = int(parts[2])

    # Сохраним в состояние index и rank
    await state.update_data(edit_index=index, upload_rank=rank)
    await state.set_state(EditMemberCardStates.waiting_for_rank_image_upload)
    await callback.message.answer(f"Отправьте изображение для ранга {rank}.")

# --- Получение изображения для ранга ---

@router.message(EditMemberCardStates.waiting_for_rank_image_upload, F.content_type == ContentType.PHOTO)
async def receive_rank_image(message: Message, state: FSMContext):
    data = await state.get_data()
    index = data.get("edit_index")
    rank = data.get("upload_rank")

    if index is None or rank is None:
        await message.answer("Ошибка состояния, повторите попытку.")
        await state.clear()
        return

    cards = load_member_cards()
    if index < 0 or index >= len(cards):
        await message.answer("Карточка не найдена.")
        await state.clear()
        return

    # Сохраняем фото в папку ранга
    rank_folder = os.path.join(IMAGES_PATH_MAIN, f"rank_{rank}")
    os.makedirs(rank_folder, exist_ok=True)

    file_id = message.photo[-1].file_id
    file_info = await message.bot.get_file(file_id)
    ext = os.path.splitext(file_info.file_path)[1] or ".jpg"
    filename = cards[index]["image"]  # сохраняем под тем же именем (чтобы найти потом)

    save_path = os.path.join(rank_folder, filename)

    await message.bot.download_file(file_info.file_path, save_path)

    await message.answer(f"Изображение для ранга {rank} успешно сохранено.")

    # Возвращаем в просмотр изображений рангов
    await state.clear()
    await show_member_rank_images(await message.answer(" "), CallbackQuery(
        data=f"show_member_rank_images:{index}",
        from_user=message.from_user,
        message=message
    ))

# --- Кнопка "Назад" из просмотра изображений рангов в редактор карты ---

@router.callback_query(lambda c: c.data and c.data.startswith("back_to_edit:"))
async def back_to_edit(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    index = int(callback.data.split(":")[1])
    await send_member_card(callback, index, edit_mode=True)

@router.callback_query(lambda c: c.data and c.data.startswith("delete_member:"))
async def prompt_delete_member(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    try:
        index = int(callback.data.split(":")[1])
    except Exception:
        await callback.answer("⚠ Некорректные данные", show_alert=True)
        return

    cards = load_member_cards()
    if index < 0 or index >= len(cards):
        await callback.answer("Карточка не найдена.", show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="✅ Удалить", callback_data=f"confirm_delete:{index}"),
        types.InlineKeyboardButton(text="❌ Отмена", callback_data=f"back_to_edit:{index}"),
        width=2
    )


    text = (
    f"Вы уверены, что хотите удалить карточку участника #{index + 1} "
    f"— «{cards[index].get('name','—')}»?\nЭто действие нельзя отменить."
    )

    try:
        await safe_edit_message(callback.message, text, reply_markup=builder.as_markup())
    except TelegramBadRequest:
        # Если нет текста в сообщении (например, карточка с фото)
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=builder.as_markup())



@router.callback_query(lambda c: c.data and c.data.startswith("confirm_delete:"))
async def confirm_delete_member(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    try:
        index = int(callback.data.split(":")[1])
    except Exception:
        await callback.answer("⚠ Некорректные данные", show_alert=True)
        return

    cards = load_member_cards()
    if index < 0 or index >= len(cards):
        await callback.answer("Карточка не найдена.", show_alert=True)
        return

    removed = cards.pop(index)
    save_member_cards(cards)

    filename = removed.get("image", "")
    for r in range(1, 5):
        path = os.path.join(IMAGES_PATH_MAIN, f"rank_{r}", filename)
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception as e:
            logging.warning(f"Не удалось удалить файл {path}: {e}")

    main_path = os.path.join(IMAGES_PATH, filename)
    try:
        if os.path.exists(main_path):
            os.remove(main_path)
    except Exception as e:
        logging.warning(f"Не удалось удалить файл {main_path}: {e}")

    await callback.message.answer(f"✅ Карточка #{index + 1} «{removed.get('name','—')}» удалена.")

    if cards:
        new_index = index if index < len(cards) else len(cards) - 1
        await send_member_card(callback, new_index, edit_mode=False)
    else:
        try:
            await safe_edit_message(callback.message, "Список карточек пуст.")
        except TelegramBadRequest:
            await callback.message.answer("Список карточек пуст.")














# === EDIT SKILL ===
SKILL_CARDS_PATH = "data/cards/skills.json"
SKILL_IMAGES_PATH = "data/images/skills"

# FSM states
class EditSkillCardStates(StatesGroup):
    waiting_for_new_skill_name = State()
    waiting_for_skill_rarity = State()


# === Загрузка/сохранение скилл-карт ===

def load_skill_cards():
    if not os.path.exists(SKILL_CARDS_PATH):
        return []
    with open(SKILL_CARDS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_skill_cards(cards):
    try:
        with open(SKILL_CARDS_PATH, "w", encoding="utf-8") as f:
            json.dump(cards, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"Ошибка при сохранении суперспособностей: {e}")



# --- Форматирование текста скилл-карты ---

def format_skill_text(card):
    return (
        f"<b>{card['name']}</b>\n"
        f"⭐ Редкость: <b>{card.get('rarity','—')}</b>"
    )



# --- Отправка скилл-карты с навигацией ---

async def send_skill_card(message_or_cb, index: int, edit_mode=False):
    cards = load_skill_cards()
    total = len(cards)
    if index < 0 or index >= total:
        if hasattr(message_or_cb, "answer"):
            await message_or_cb.answer("Карточка не найдена.")
        else:
            await message_or_cb.message.answer("Карточка не найдена.")
        return

    card = cards[index]
    image_path = find_image_file(os.path.splitext(card.get('image',''))[0], SKILL_IMAGES_PATH)
    photo = FSInputFile(image_path) if os.path.exists(image_path) else None
    caption = format_skill_text(card)

    # Клавиатура навигации для скиллов (похожая на member list) - reuse get_list_member_keyboard but prefix changed
    keyboard = get_edit_mode_skill_keyboard(index, total) if edit_mode else get_list_skill_keyboard(index, total, prefix="edit_skill_cards")

    if isinstance(message_or_cb, Message):
        if photo:
            await message_or_cb.answer_photo(photo=photo, caption=caption, reply_markup=keyboard)
        else:
            await message_or_cb.answer(caption, reply_markup=keyboard)
    else:
        try:
            if photo:
                await message_or_cb.message.edit_media(media=types.InputMediaPhoto(media=photo, caption=caption), reply_markup=keyboard)
            else:
                await message_or_cb.message.edit_text(caption, reply_markup=keyboard)
        except TelegramBadRequest:
            # fallback to sending message
            if photo:
                await message_or_cb.message.answer_photo(photo=photo, caption=caption, reply_markup=keyboard)
            else:
                await message_or_cb.message.answer(caption, reply_markup=keyboard)





# --- Обработка команды /skills ---
@router.message(Command("skills"))
async def cmd_skills(message: Message):
    if not await is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к этой команде.")
        return
    cards = load_skill_cards()
    if not cards:
        await message.answer("Список суперспособностей пуст.")
        return
    await send_skill_card(message, 0, edit_mode=False)






# --- Возврат из режима редактирования ---

@router.callback_query(lambda c: c.data and c.data.startswith("back_to_skill_list:"))
async def handle_back_to_skill_list(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    index = int(callback.data.split(":")[1])
    await send_skill_card(callback, index, edit_mode=False)

# --- Навигация по карточкам скиллов (следующая, предыдущая) ---
@router.callback_query(lambda c: c.data and c.data.startswith("edit_skill_cards:navigate"))
async def navigate_skill_cards(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    parts = callback.data.split(":" )
    if len(parts) != 4:
        await callback.answer("⚠️ Некорректные данные", show_alert=True)
        return

    _, _, direction, current_index_str = parts
    current_index = int(current_index_str)

    cards = load_skill_cards()
    if direction == "next":
        new_index = current_index + 1 if current_index + 1 < len(cards) else current_index
    elif direction == "prev":
        new_index = current_index - 1 if current_index - 1 >= 0 else current_index
    else:
        new_index = current_index

    await send_skill_card(callback, new_index)



# --- При нажатии на центральную кнопку с номером показываем список скиллов постранично ---
@router.callback_query(lambda c: c.data and c.data.startswith("show_skill_list:"))
async def show_skill_list(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    page = int(callback.data.split(":")[1])
    cards = load_skill_cards()
    total = len(cards)
    per_page = 10
    total_pages = (total + per_page - 1) // per_page

    if page < 0:
        page = 0
    if page >= total_pages:
        page = total_pages - 1

    builder = InlineKeyboardBuilder()
    start = page * per_page
    end = min(start + per_page, total)
    for i in range(start, end):
        card_name = cards[i].get("name", "Без имени")
        builder.row(
            types.InlineKeyboardButton(text=f"{i + 1}. {card_name}", callback_data=f"select_skill:{i}")
        )

    prev_page = max(0, page - 1)
    next_page = min(total_pages - 1, page + 1)
    builder.row(
        types.InlineKeyboardButton(text="◀️", callback_data=f"navigate_skill_page:{prev_page}"),
        types.InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"),
        types.InlineKeyboardButton(text="▶️", callback_data=f"navigate_skill_page:{next_page}")
    )
    builder.row(
        types.InlineKeyboardButton(text="↪️ Назад", callback_data="go_back_menu")
    )

    text = f"Список суперспособностей, страница {page+1}/{total_pages}:"
    try:
        await safe_edit_message(callback.message, text, reply_markup=builder.as_markup())
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=builder.as_markup())


@router.callback_query(lambda c: c.data and c.data.startswith("navigate_skill_page:"))
async def navigate_skill_page(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    page = int(callback.data.split(":")[1])
    cards = load_skill_cards()
    total = len(cards)
    per_page = 10
    total_pages = (total + per_page - 1) // per_page

    if page < 0:
        page = 0
    if page >= total_pages:
        page = total_pages - 1

    builder = InlineKeyboardBuilder()
    start = page * per_page
    end = min(start + per_page, total)
    for i in range(start, end):
        card_name = cards[i].get("name", "Без имени")
        builder.row(
            types.InlineKeyboardButton(text=f"{i + 1}. {card_name}", callback_data=f"select_skill:{i}")
        )

    prev_page = max(0, page - 1)
    next_page = min(total_pages - 1, page + 1)
    builder.row(
        types.InlineKeyboardButton(text="◀️", callback_data=f"navigate_skill_page:{prev_page}"),
        types.InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"),
        types.InlineKeyboardButton(text="▶️", callback_data=f"navigate_skill_page:{next_page}")
    )
    builder.row(
        types.InlineKeyboardButton(text="↪️ Назад", callback_data="go_back_menu")
    )

    text = f"Список суперспособностей, страница {page+1}/{total_pages}:"
    try:
        await safe_edit_message(callback.message, text, reply_markup=builder.as_markup())
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=builder.as_markup())

@router.callback_query(lambda c: c.data and c.data.startswith("select_skill:"))
async def select_skill(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    index = int(callback.data.split(":")[1])
    await send_skill_card(callback, index, edit_mode=False)










# --- SKILL EDITING: enter edit mode for skills ---
@router.callback_query(lambda c: c.data and c.data.startswith("edit_skill_card:"))
async def enter_skill_edit_mode(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    _, index_str = callback.data.split(":")
    index = int(index_str)
    await send_skill_card(callback, index, edit_mode=True)


@router.callback_query(lambda c: c.data and c.data.startswith("edit_skill_name:"))
async def handle_edit_skill_name(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    index = int(callback.data.split(":")[1])
    await callback.message.answer(f"Введите новое имя суперспособности для карточки #{index + 1}:" )
    await state.update_data(edit_skill_index=index)
    await state.set_state(EditSkillCardStates.waiting_for_new_skill_name)


@router.callback_query(lambda c: c.data and c.data.startswith("edit_skill_rarity:"))
async def handle_edit_skill_rarity(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    index = int(callback.data.split(":")[1])
    await callback.message.answer(f"Введите новую редкость для суперспособности #{index + 1}:", reply_markup=get_rarity_keyboard())
    await state.update_data(edit_skill_index=index)
    await state.set_state(EditSkillCardStates.waiting_for_skill_rarity)


@router.message(EditSkillCardStates.waiting_for_new_skill_name)
async def process_new_skill_name(message: Message, state: FSMContext):
    data = await state.get_data()
    index = data.get("edit_skill_index")
    cards = load_skill_cards()
    if index is None or index >= len(cards):
        await message.answer("Карточка не найдена.")
        await state.clear()
        return
    cards[index]["name"] = message.text.strip()
    save_skill_cards(cards)
    await message.answer("Имя суперспособности успешно изменено.")
    await send_skill_card(message, index, edit_mode=True)
    await state.clear()


@router.callback_query(EditSkillCardStates.waiting_for_skill_rarity)
async def process_new_skill_rarity_callback(callback: CallbackQuery, state: FSMContext):
    rarity = callback.data.strip().capitalize()
    valid_rarities = ["Обычная", "Редкая", "Эпическая", "Легендарная"]
    if rarity not in valid_rarities:
        await callback.answer("Некорректная редкость.", show_alert=True)
        return
    data = await state.get_data()
    index = data.get("edit_skill_index")
    cards = load_skill_cards()
    if index is None or index >= len(cards):
        await callback.answer("Карточка не найдена.", show_alert=True)
        await state.clear()
        return
    cards[index]["rarity"] = rarity
    save_skill_cards(cards)
    await callback.message.answer(f"✅ Редкость суперспособности успешно изменена на «{rarity}».")
    await send_skill_card(callback, index, edit_mode=True)
    await state.clear()


@router.callback_query(lambda c: c.data and c.data.startswith("delete_skill:"))
async def prompt_delete_skill(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    try:
        index = int(callback.data.split(":")[1])
    except Exception:
        await callback.answer("⚠ Некорректные данные", show_alert=True)
        return
    cards = load_skill_cards()
    if index < 0 or index >= len(cards):
        await callback.answer("Карточка не найдена.", show_alert=True)
        return
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="✅ Удалить", callback_data=f"confirm_delete_skill:{index}"),
        types.InlineKeyboardButton(text="❌ Отмена", callback_data=f"back_to_list_skill:{index}"),
        width=2
    )

    text = (
    f"Вы уверены, что хотите удалить суперспособность #{index + 1} "
    f"— «{cards[index].get('name','—')}»?\nЭто действие нельзя отменить."
    )

    try:
        await safe_edit_message(callback.message, text, reply_markup=builder.as_markup())
    except TelegramBadRequest:
        # Если нет текста в сообщении (например, карточка с фото)
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=builder.as_markup())

@router.callback_query(lambda c: c.data and c.data.startswith("confirm_delete_skill:"))
async def confirm_delete_skill(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    try:
        index = int(callback.data.split(":")[1])
    except Exception:
        await callback.answer("⚠ Некорректные данные", show_alert=True)
        return
    cards = load_skill_cards()
    if index < 0 or index >= len(cards):
        await callback.answer("Карточка не найдена.", show_alert=True)
        return
    removed = cards.pop(index)
    save_skill_cards(cards)
    filename = removed.get("image", "")
    path = os.path.join(SKILL_IMAGES_PATH, filename)
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception as e:
        logging.warning(f"Не удалось удалить файл {path}: {e}")
    await callback.message.answer(f"✅ Суперспособность #{index + 1} «{removed.get('name','—')}» удалена.")
    if cards:
        new_index = index if index < len(cards) else len(cards) - 1
        await send_skill_card(callback, new_index, edit_mode=False)
    else:
        try:
            await safe_edit_message(callback.message, "Список суперспособностей пуст.")
        except TelegramBadRequest:
            await callback.message.answer("Список суперспособностей пуст.")



















# === ADD KAZINO UPGRADES ===
KAZINO_UPGRADES_PATH = "data/cards/kazin_upgrades.json"




# FSM states
class EditSkillCardStates(StatesGroup):
    waiting_for_new_kazino_upgrade_name = State()
    waiting_for_kazino_upgrade_rarity = State()
    waiting_for_new_kazino_upgrade_effect = State()


# --- ADD KAZIN UPGRADE FLOW ---
class AddKazinUpgrade(StatesGroup):
    waiting_for_upgrade_name = State()
    waiting_for_upgrade_rarity = State()
    waiting_for_upgrade_effect = State()


@router.message(Command("add_kazin_upgrade"))
async def cmd_add_kazin_upgrade(message: Message, state: FSMContext):
    if not await is_admin(message.from_user.id):
        await message.answer("🚫 Только админы могут использовать эту команду.")
        return
    await message.answer("Введите название нового улучшения:")
    await state.set_state(AddKazinUpgrade.waiting_for_upgrade_name)


@router.message(AddKazinUpgrade.waiting_for_upgrade_name)
async def kazin_upgrade_get_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await message.answer("Выберите редкость улучшения:", reply_markup=get_rarity_keyboard())
    await state.set_state(AddKazinUpgrade.waiting_for_upgrade_rarity)


@router.callback_query(AddKazinUpgrade.waiting_for_upgrade_rarity)
async def kazin_upgrade_get_rarity(callback: CallbackQuery, state: FSMContext):
    rarity = callback.data
    if rarity not in RARITY_CHANCES:
        await callback.answer("Неверная редкость", show_alert=True)
        return

    await state.update_data(rarity=rarity)
    await callback.message.answer("Введите эффект улучшения (краткое описание):")
    await state.set_state(AddKazinUpgrade.waiting_for_upgrade_effect)


@router.message(AddKazinUpgrade.waiting_for_upgrade_effect)
async def kazin_upgrade_get_effect(message: Message, state: FSMContext):
    data = await state.get_data()
    name = data.get("name")
    rarity = data.get("rarity")
    effect = message.text.strip()

    upgrades = load_kazin_upgrades()

    # Prevent duplicate names (case-insensitive)
    if any(u.get('name','').lower() == name.lower() for u in upgrades):
        await message.answer("❗ Улучшение с таким названием уже существует!")
        await state.clear()
        return

    new_upgrade = {"name": name, "rarity": rarity, "effect": effect}
    upgrades.append(new_upgrade)
    save_kazin_upgrades(upgrades)

    await message.answer(f"✅ Улучшение '{name}' добавлено.")
    await send_kazino_upgrade(message, len(upgrades) - 1)
    await state.clear()


# --- EDIT/DELETE HANDLERS FOR KAZIN UPGRADE ---
@router.callback_query(lambda c: c.data and c.data.startswith("edit_kazin_upgrade:"))
async def enter_kazin_edit_mode(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    parts = callback.data.split(":")
    if len(parts) != 2:
        await callback.answer("⚠ Некорректные данные", show_alert=True)
        return
    index = int(parts[1])
    upgrades = load_kazin_upgrades()
    if index < 0 or index >= len(upgrades):
        await callback.answer("Апгрейд не найден.", show_alert=True)
        return

    # show edit-mode keyboard
    keyboard = get_edit_mode_kazin_keyboard(index, len(upgrades))
    text = format_kazin_upgrade_text(upgrades[index])
    try:
        await safe_edit_message(callback.message, text, reply_markup=keyboard)
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=keyboard)


@router.callback_query(lambda c: c.data and c.data.startswith("edit_kazin_name:"))
async def handle_edit_kazin_name(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    index = int(callback.data.split(":")[1])
    await callback.message.answer(f"Введите новое название улучшения для #{index+1}:")
    await state.update_data(edit_kazin_index=index)
    await state.set_state(EditSkillCardStates.waiting_for_new_kazino_upgrade_name)


@router.message(EditSkillCardStates.waiting_for_new_kazino_upgrade_name)
async def process_new_kazin_name(message: Message, state: FSMContext):
    data = await state.get_data()
    index = data.get("edit_kazin_index")
    if index is None:
        await message.answer("Ошибка состояния.")
        await state.clear()
        return
    upgrades = load_kazin_upgrades()
    if index < 0 or index >= len(upgrades):
        await message.answer("Апгрейд не найден.")
        await state.clear()
        return
    new_name = message.text.strip()
    # check duplicate
    if any(i != index and u.get('name','').lower() == new_name.lower() for i,u in enumerate(upgrades)):
        await message.answer("❗ Улучшение с таким названием уже существует!")
        await state.clear()
        return
    upgrades[index]['name'] = new_name
    save_kazin_upgrades(upgrades)
    await message.answer("✅ Название успешно обновлено.")
    await send_kazino_upgrade(message, index)
    await state.clear()


@router.callback_query(lambda c: c.data and c.data.startswith("edit_kazin_rarity:"))
async def handle_edit_kazin_rarity(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    index = int(callback.data.split(":")[1])
    await callback.message.answer(f"Введите новую редкость для апгрейда #{index + 1}:", reply_markup=get_rarity_keyboard())
    await state.update_data(edit_kazin_index=index)
    await state.set_state(EditSkillCardStates.waiting_for_kazino_upgrade_rarity)


@router.callback_query(lambda c: c.data and c.data.startswith("edit_kazin_effect:"))
async def handle_edit_kazin_effect(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    index = int(callback.data.split(":")[1])
    await callback.message.answer(f"Введите новый эффект для апгрейда #{index + 1}:")
    await state.update_data(edit_kazin_index=index)
    await state.set_state(EditSkillCardStates.waiting_for_new_kazino_upgrade_effect)


@router.message(EditSkillCardStates.waiting_for_kazino_upgrade_rarity)
async def process_new_kazin_rarity_callback(message: Message, state: FSMContext):
    # this handler receives a Message because get_rarity_keyboard sends callback data as text; support both
    rarity = message.text.strip() if isinstance(message, Message) else None
    # attempt to read from message text or callback data via state
    data = await state.get_data()
    index = data.get('edit_kazin_index')
    if rarity not in RARITY_CHANCES:
        await message.answer("Некорректная редкость.")
        await state.clear()
        return
    upgrades = load_kazin_upgrades()
    if index is None or index >= len(upgrades):
        await message.answer("Апгрейд не найден.")
        await state.clear()
        return
    upgrades[index]['rarity'] = rarity
    save_kazin_upgrades(upgrades)
    await message.answer(f"✅ Редкость успешно изменена на «{rarity}».")
    await send_kazino_upgrade(message, index)
    await state.clear()


@router.message(EditSkillCardStates.waiting_for_new_kazino_upgrade_effect)
async def process_new_kazin_effect(message: Message, state: FSMContext):
    data = await state.get_data()
    index = data.get('edit_kazin_index')
    upgrades = load_kazin_upgrades()
    if index is None or index >= len(upgrades):
        await message.answer("Апгрейд не найден.")
        await state.clear()
        return
    upgrades[index]['effect'] = message.text.strip()
    save_kazin_upgrades(upgrades)
    await message.answer("✅ Эффект успешно изменён.")
    await send_kazino_upgrade(message, index)
    await state.clear()


@router.callback_query(lambda c: c.data and c.data.startswith("delete_kazin:"))
async def prompt_delete_kazin(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    try:
        index = int(callback.data.split(":")[1])
    except Exception:
        await callback.answer("⚠ Некорректные данные", show_alert=True)
        return
    upgrades = load_kazin_upgrades()
    if index < 0 or index >= len(upgrades):
        await callback.answer("Апгрейд не найден.", show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="✅ Удалить", callback_data=f"confirm_delete_kazin:{index}"),
        types.InlineKeyboardButton(text="❌ Отмена", callback_data=f"back_to_kazin_list:{index}"),
        width=2
    )

    text = (
        f"Вы уверены, что хотите удалить апгрейд #{index + 1} — «{upgrades[index].get('name','—')}»?\nЭто действие нельзя отменить."
    )
    try:
        await safe_edit_message(callback.message, text, reply_markup=builder.as_markup())
    except TelegramBadRequest:
        await callback.message.delete()
        await callback.message.answer(text, reply_markup=builder.as_markup())


@router.callback_query(lambda c: c.data and c.data.startswith("confirm_delete_kazin:"))
async def confirm_delete_kazin(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    try:
        index = int(callback.data.split(":")[1])
    except Exception:
        await callback.answer("⚠ Некорректные данные", show_alert=True)
        return
    upgrades = load_kazin_upgrades()
    if index < 0 or index >= len(upgrades):
        await callback.answer("Апгрейд не найден.", show_alert=True)
        return
    removed = upgrades.pop(index)
    save_kazin_upgrades(upgrades)
    await callback.message.answer(f"✅ Апгрейд #{index + 1} «{removed.get('name','—')}» удалён.")
    if upgrades:
        new_index = index if index < len(upgrades) else len(upgrades) - 1
        await send_kazino_upgrade(callback, new_index)
    else:
        try:
            await safe_edit_message(callback.message, "Список апгрейдов пуст.")
        except TelegramBadRequest:
            await callback.message.answer("Список апгрейдов пуст.")


# === Загрузка/сохранение казин-апгрейдов ===
def load_kazin_upgrades():
    if not os.path.exists(KAZINO_UPGRADES_PATH):
        return []
    with open(KAZINO_UPGRADES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_kazin_upgrades(data):
    with open(KAZINO_UPGRADES_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# --- Форматирование текста казин-апгрейда ---
def format_kazin_upgrade_text(upgrade):
    return (
        f"<b>{upgrade['name']}</b>\n"
        f"⭐ Редкость: <b>{upgrade.get('rarity','—')}</b>\n"
        f"🔧 Эффект: <b>{upgrade.get('effect','—')}</b>"
    )
# --- Отправка казин-апгрейда с навигацией ---
async def send_kazino_upgrade(message_or_cb, index: int):
    upgrades = load_kazin_upgrades()
    total = len(upgrades)
    if index < 0 or index >= total:
        if hasattr(message_or_cb, "answer"):
            await message_or_cb.answer("Апгрейд не найден.")
        else:
            await message_or_cb.message.answer("Апгрейд не найден.")
        return

    upgrade = upgrades[index]
    caption = format_kazin_upgrade_text(upgrade)

    keyboard = get_list_kazin_keyboard(index, total, prefix="edit_kazin_upgrades")

    if isinstance(message_or_cb, Message):
        await message_or_cb.answer(caption, reply_markup=keyboard)
    else:
        try:
            await safe_edit_message(message_or_cb.message, caption, reply_markup=keyboard)
        except TelegramBadRequest:
            await message_or_cb.message.answer(caption, reply_markup=keyboard)

# --- Обработка команды /kazino_upgrades ---
@router.message(Command("add_kazino_upgrades"))
async def handle_add_kazino_upgrades(message: Message):
    if not await is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к этой команде.")
        return
    upgrades = load_kazin_upgrades()
    new_upgrade = {
        "name": "Новое улучшение",
        "rarity": "Обычная",
        "effect": "Описание эффекта"
    }
    upgrades.append(new_upgrade)
    save_kazin_upgrades(upgrades)
    await message.answer(f"✅ Новое улучшение добавлено. Всего улучшений: {len(upgrades)}.")
    await send_kazino_upgrade(message, len(upgrades) - 1)

# --- Обработка команды /kazino_upgrades ---
@router.message(Command("kazino_upgrades"))
async def handle_kazino_upgrades(message: Message):
    await send_kazino_upgrade(message, 0)

# --- Навигация по казино-апгрейдам (следующая, предыдущая) ---
@router.callback_query(lambda c: c.data and c.data.startswith("edit_kazino_upgrades:navigate"))
async def navigate_kazino_upgrades(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    parts = callback.data.split(":")
    if len(parts) != 4:
        await callback.answer("⚠️ Некорректные данные", show_alert=True)
        return

    _, _, direction, current_index_str = parts
    current_index = int(current_index_str)

    upgrades = load_kazin_upgrades()
    if direction == "next":
        new_index = current_index + 1 if current_index + 1 < len(upgrades) else current_index
    elif direction == "prev":
        new_index = current_index - 1 if current_index - 1 >= 0 else current_index
    else:
        new_index = current_index

    await send_kazino_upgrade(callback, new_index)

# --- При нажатии на центральную кнопку с номером показываем список казин-апгрейдов постранично ---
@router.callback_query(lambda c: c.data and c.data.startswith("show_kazin_upgrade_list:"))
async def show_kazin_upgrade_list(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return

    page = int(callback.data.split(":")[1])
    upgrades = load_kazin_upgrades()
    total = len(upgrades)
    per_page = 10
    total_pages = (total + per_page - 1) // per_page

    if page < 0:
        page = 0
    if page >= total_pages:
        page = total_pages - 1

    builder = InlineKeyboardBuilder()
    start = page * per_page
    end = min(start + per_page, total)
    for i in range(start, end):
        upgrade_name = upgrades[i].get("name", "Без имени")
        builder.row(
            types.InlineKeyboardButton(text=f"{i + 1}. {upgrade_name}", callback_data=f"select_kazin_upgrade:{i}")
        )

    prev_page = max(0, page - 1)
    next_page = min(total_pages - 1, page + 1)
    builder.row(
        types.InlineKeyboardButton(text="◀️", callback_data=f"navigate_kazin_upgrade_page:{prev_page}"),
        types.InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"),
        types.InlineKeyboardButton(text="▶️", callback_data=f"navigate_kazin_upgrade_page:{next_page}")
    )
    builder.row(
        types.InlineKeyboardButton(text="↪️ Назад", callback_data="go_back_menu")
    )

    text = f"Список казин-апгрейдов, страница {page+1}/{total_pages}:"
    try:
        await callback.message.edit_text(text, reply_markup=builder.as_markup())
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=builder.as_markup())

@router.callback_query(lambda c: c.data and c.data.startswith("navigate_kazin_upgrade_page:"))
async def navigate_kazin_upgrade_page(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    page = int(callback.data.split(":")[1])
    upgrades = load_kazin_upgrades()
    total = len(upgrades)
    per_page = 10
    total_pages = (total + per_page - 1) // per_page

    if page < 0:
        page = 0
    if page >= total_pages:
        page = total_pages - 1

    builder = InlineKeyboardBuilder()
    start = page * per_page
    end = min(start + per_page, total)
    for i in range(start, end):
        upgrade_name = upgrades[i].get("name", "Без имени")
        builder.row(
            types.InlineKeyboardButton(text=f"{i + 1}. {upgrade_name}", callback_data=f"select_kazin_upgrade:{i}")
        )

    prev_page = max(0, page - 1)
    next_page = min(total_pages - 1, page + 1)
    builder.row(
        types.InlineKeyboardButton(text="◀️", callback_data=f"navigate_kazin_upgrade_page:{prev_page}"),
        types.InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"),
        types.InlineKeyboardButton(text="▶️", callback_data=f"navigate_kazin_upgrade_page:{next_page}")
    )
    builder.row(
        types.InlineKeyboardButton(text="↪️ Назад", callback_data="go_back_menu")
    )

    text = f"Список казин-апгрейдов, страница {page+1}/{total_pages}:"
    try:
        await callback.message.edit_text(text, reply_markup=builder.as_markup())
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=builder.as_markup())

@router.callback_query(lambda c: c.data and c.data.startswith("select_kazin_upgrade:"))
async def select_kazin_upgrade(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    index = int(callback.data.split(":")[1])
    await send_kazino_upgrade(callback, index)

# --- KAZIN UPGRADE EDITING: enter edit mode for kazin upgrades ---
@router.callback_query(lambda c: c.data and c.data.startswith("edit_kazin_upgrade:"))
async def enter_kazin_upgrade_edit_mode(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    _, index_str = callback.data.split(":")
    index = int(index_str)
    await send_kazino_upgrade(callback, index)

@router.callback_query(lambda c: c.data and c.data.startswith("edit_kazin_name:"))
async def handle_edit_kazin_name(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    index = int(callback.data.split(":")[1])
    await callback.message.answer(f"Введите новое имя апгрейда для карточки #{index + 1}:" )
    await state.update_data(edit_kazin_index=index)
    await state.set_state(EditSkillCardStates.waiting_for_new_kazino_upgrade_name)

@router.callback_query(lambda c: c.data and c.data.startswith("edit_kazin_rarity:"))
async def handle_edit_kazin_rarity(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    index = int(callback.data.split(":")[1])
    await callback.message.answer(f"Введите новую редкость для апгрейда #{index + 1}:", reply_markup=get_rarity_keyboard())
    await state.update_data(edit_kazin_index=index)
    await state.set_state(EditSkillCardStates.waiting_for_new_kazino_upgrade_rarity)

@router.callback_query(lambda c: c.data and c.data.startswith("edit_kazin_effect:"))
async def handle_edit_kazin_effect(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    index = int(callback.data.split(":")[1])
    await callback.message.answer(f"Введите новый эффект для апгрейда #{index + 1}:" )
    await state.update_data(edit_kazin_index=index)
    await state.set_state(EditSkillCardStates.waiting_for_new_kazino_upgrade_effect)