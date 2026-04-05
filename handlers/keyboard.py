from aiogram import Router, F
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, CallbackQuery, Message, LabeledPrice

import json, os, datetime, sqlite3

router = Router()

DB_FILE = "database/users.db"


def connect():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row  # Позволяет обращаться по ключам, а не по индексам
    return conn

async def get_main_keyboard(spins, user_id) -> InlineKeyboardMarkup:

#    conn = sqlite3.connect(DB_FILE)
#    c = conn.cursor()
#
#    # Получаем значение доната
#    c.execute("SELECT all_amount FROM user_donations WHERE user_id=?", (user_id,))
#    row = c.fetchone()
#    donate = row[0] if row else 0  # если записи нет, считаем 0
#
#    conn.close()

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=f"📙 Открыть карточки",callback_data="main_open_cards"),
    )
    builder.row(
        InlineKeyboardButton(text="📦 Коллекции", callback_data="main_card_collection"),
    )
    builder.row(
        InlineKeyboardButton(text="🛒 Магазин", callback_data="shop_menu"),
    )
    builder.row(
        InlineKeyboardButton(text=f"🎰 Казик — круток: {spins} ", callback_data="roulette_button"),
    )
    builder.row(
        InlineKeyboardButton(text="👤 Профиль", callback_data="main_profile"),
    )
    builder.row(
        InlineKeyboardButton(text="🏆 ЛИДЕРЫ", callback_data="top_menu"),
    )

#    if donate > 0:
    builder.row(
        InlineKeyboardButton(text="⭐️ Матюкнуться", callback_data="word_random"),
    )
    builder.row(
        InlineKeyboardButton(text="🙏 Мотивация", callback_data="motivation_menu"),
    )
    return builder.as_markup()

def get_back_menu_button():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="↪️ Назад", callback_data="go_back_menu"),
    )
    return builder.as_markup()

# === START ===
def get_start_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="start")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )


def get_persistent_bottom_keyboard():
    """Reply keyboard that stays at the bottom of the chat on /start.
    Shows primary actions as large buttons for easy access.
    """
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Меню")]],
        resize_keyboard=True,
        one_time_keyboard=False,
    input_field_placeholder="Нажмите 'Меню'"
    )


# === REFERAL CARD ===
def bonus_member_card_open():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="👥 Карточка участника", callback_data="draw_member"),
    )
    return builder.as_markup()



# === CARD OPEN UI ===
def get_card_open_ui_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="👥 Карточка участника", callback_data="draw_member"),
    )
    builder.row(
        InlineKeyboardButton(text="🃏 Суперспособность", callback_data="draw_skill"),
    )
    builder.row(
        InlineKeyboardButton(text="↪️ Назад", callback_data="go_back_menu"),
    )
    return builder.as_markup()



# === CARD COLLECTION UI ===
def get_card_collection_ui_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📦 Мои участники", callback_data="my_member_cards"),
    )
    builder.row(
        InlineKeyboardButton(text="📦 Мои суперспособности", callback_data="my_skill_cards"),
    )
    builder.row(
        InlineKeyboardButton(text="⭐️ Мои матюки", callback_data="word_collection"),
    )
    builder.row(
        InlineKeyboardButton(text="↪️ Назад", callback_data="go_back_menu"),
    )
    return builder.as_markup()

# === CARD COLLECTION UI ===
def get_card_member_ui():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📦 Назад", callback_data="my_member_cards"),
    )
    return builder.as_markup()

def get_back_menu_colletion_button():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="↪️ Назад", callback_data="main_card_collection"),
    )
    return builder.as_markup()



def get_card_skill_ui():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📦 Назад", callback_data="my_skill_cards"),
    )
    return builder.as_markup()





# === CARD NAVIGATION ===
def get_member_card_navigation_keyboard(index: int, total: int, prefix: str = "my_member_cards"):
    builder = InlineKeyboardBuilder()

    # Стрелка влево
    prev_index = (index - 1) % total
    builder.add(
        InlineKeyboardButton(
            text="⬅",
            callback_data=f"{prefix}:{prev_index}"
        )
    )
    # Текущий номер
    builder.add(
        InlineKeyboardButton(
            text=f"{index + 1}/{total}",
            callback_data="noop"
        )
    )
    # Стрелка вправо
    next_index = (index + 1) % total
    builder.add(
        InlineKeyboardButton(
            text="➡",
            callback_data=f"{prefix}:{next_index}"
        )
    )
    builder.row(
        InlineKeyboardButton(text="🔥 Продать карту", callback_data=f"sell_member_card:{index}"),
    )
    builder.row(
        InlineKeyboardButton(text="↪️ Назад", callback_data="go_back_menu"),
    )
    return builder.as_markup()

def get_skill_card_navigation_keyboard(index: int, total: int, prefix: str = "my_skill_cards"):
    builder = InlineKeyboardBuilder()

    # Стрелка влево
    prev_index = (index - 1) % total
    builder.add(
        InlineKeyboardButton(
            text="⬅",
            callback_data=f"{prefix}:{prev_index}"
        )
    )
    # Текущий номер
    builder.add(
        InlineKeyboardButton(
            text=f"{index + 1}/{total}",
            callback_data="noop"
        )
    )
    # Стрелка вправо
    next_index = (index + 1) % total
    builder.add(
        InlineKeyboardButton(
            text="➡",
            callback_data=f"{prefix}:{next_index}"
        )
    )
    builder.row(
        InlineKeyboardButton(text="🔥 Продать карту", callback_data=f"sell_skill_card:{index}"),
    )
    builder.row(
        InlineKeyboardButton(text="↪️ Назад", callback_data="go_back_menu"),
    )
    return builder.as_markup()





















# === СОРТИРОВКА ===

def get_sort_member_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="По редкости", callback_data="sort_by_rarity"),
        InlineKeyboardButton(text="По алфавиту", callback_data="sort_by_name")
    )
    return builder.as_markup()

def get_sort_skill_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="По редкости", callback_data="sort_by_rarity"),
        InlineKeyboardButton(text="По алфавиту", callback_data="sort_by_name")
    )
    return builder.as_markup()





def get_rarity_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Обычная", callback_data="Обычная"),
        InlineKeyboardButton(text="Редкая", callback_data="Редкая"),
    )
    builder.row(
        InlineKeyboardButton(text="Эпическая", callback_data="Эпическая"),
        InlineKeyboardButton(text="Легендарная", callback_data="Легендарная"),
    )
    return builder.as_markup()


# === ADD_MEMBER_RARITY ===

def get_list_member_keyboard(index: int, total: int, prefix: str = "edit_member_cards") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    prev_index = (index - 1) % total
    next_index = (index + 1) % total

    builder.row(
        InlineKeyboardButton(text="⬅", callback_data=f"{prefix}:navigate:prev:{index}"),
        InlineKeyboardButton(text=f"{index + 1}/{total}", callback_data=f"show_member_list:{index}"),
        InlineKeyboardButton(text="➡", callback_data=f"{prefix}:navigate:next:{index}"),
    )

    builder.row(
        InlineKeyboardButton(text="Редактировать", callback_data=f"edit_mode_member_cards:{index}")
    )

    return builder.as_markup()

def get_member_list_page_keyboard(
    page: int, per_page: int, total: int, cards: list, prefix: str = "select_card"
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    start = page * per_page
    end = min(start + per_page, total)

    for i in range(start, end):
        card_name = cards[i]["name"] if i < len(cards) else "Без имени"
        builder.row(
            InlineKeyboardButton(text=f"{i + 1}. {card_name}", callback_data=f"{prefix}:{i}")
        )

    total_pages = (total + per_page - 1) // per_page
    prev_page = max(0, page - 1)
    next_page = min(total_pages - 1, page + 1)

    builder.row(
        InlineKeyboardButton(text="◀️", callback_data=f"navigate_page:{prev_page}"),
        InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"),
        InlineKeyboardButton(text="▶️", callback_data=f"navigate_page:{next_page}")
    )

    builder.row(
        InlineKeyboardButton(text="Сортировать", callback_data="sort_menu")
    )

    return builder.as_markup()


def get_edit_mode_member_keyboard(index: int, total: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="✏ Изменить имя", callback_data=f"edit_name:{index}"),
        InlineKeyboardButton(text="💥 Изменить суперспособность", callback_data=f"edit_skill:{index}")
    )
    # Добавляем кнопку для изменения звания
    builder.row(
        InlineKeyboardButton(text="🏷 Поменять Звание", callback_data=f"edit_work:{index}")
    )
    builder.row(
        InlineKeyboardButton(text="⭐ Изменить редкость", callback_data=f"edit_rarity:{index}")
    )
    builder.row(
        InlineKeyboardButton(text="🖼 Показать изображения по рангам", callback_data=f"show_rank_images:{index}")
    )
    builder.row(
        InlineKeyboardButton(text="🗑 Удалить карту", callback_data=f"delete_member:{index}")
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data=f"back_to_member_list:{index}")
    )

    return builder.as_markup()

def get_rank_images_keyboard(index: int, current_rank: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    # Кнопка "назад"
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data=f"back_to_edit:{index}")
    )

    # Перелистывание между рангами
    prev_rank = (current_rank - 2) % 4 + 1  # ранги от 1 до 4
    next_rank = current_rank % 4 + 1

    builder.row(
        InlineKeyboardButton(text="⬅", callback_data=f"show_rank_images:{index}:{prev_rank}"),
        InlineKeyboardButton(text=f"Ранг {current_rank}", callback_data="noop"),
        InlineKeyboardButton(text="➡", callback_data=f"show_rank_images:{index}:{next_rank}")
    )

    builder.row(
        InlineKeyboardButton(text="Добавить изображение ранга", callback_data=f"add_member_rank_image:{index}:{current_rank}")
    )

    return builder.as_markup()


def get_rank_select_keyboard(index: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for n in range(1, 5):
        builder.row(
            InlineKeyboardButton(text=f"Ранг {n}", callback_data=f"upload_rank_image:{index}:{n}")
        )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data=f"show_rank_images:{index}")
    )
    return builder.as_markup()




# === РЕДАКТИРОВАНИЕ СУПЕРСПОСОБНОСТЕЙ ===

def get_list_skill_keyboard(index: int, total: int, prefix: str = "edit_skill_cards") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    prev_index = (index - 1) % total
    next_index = (index + 1) % total

    builder.row(
        InlineKeyboardButton(text="⬅", callback_data=f"{prefix}:navigate:prev:{index}"),
        InlineKeyboardButton(text=f"{index + 1}/{total}", callback_data=f"show_skill_list:{index}"),
        InlineKeyboardButton(text="➡", callback_data=f"{prefix}:navigate:next:{index}"),
    )

    builder.row(
        InlineKeyboardButton(text="Редактировать", callback_data=f"edit_skill_card:{index}")
    )

    return builder.as_markup()


def get_skill_list_page_keyboard(
    page: int, per_page: int, total: int, cards: list, prefix: str = "select_skill_card"
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    start = page * per_page
    end = min(start + per_page, total)

    for i in range(start, end):
        card_name = cards[i]["name"] if i < len(cards) else "Без имени"
        builder.row(
            InlineKeyboardButton(text=f"{i + 1}. {card_name}", callback_data=f"{prefix}:{i}")
        )

    total_pages = (total + per_page - 1) // per_page
    prev_page = max(0, page - 1)
    next_page = min(total_pages - 1, page + 1)

    builder.row(
        InlineKeyboardButton(text="◀️", callback_data=f"navigate_page:{prev_page}"),
        InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"),
        InlineKeyboardButton(text="▶️", callback_data=f"navigate_page:{next_page}")
    )

    builder.row(
        InlineKeyboardButton(text="Сортировать", callback_data="sort_menu")
    )

    return builder.as_markup()





def get_edit_mode_skill_keyboard(index: int, total: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="✏ Изменить имя", callback_data=f"edit_skill_name:{index}"),
    )
    builder.row(
        InlineKeyboardButton(text="⭐ Изменить редкость", callback_data=f"edit_skill_rarity:{index}")
    )
    builder.row(
        InlineKeyboardButton(text="🗑 Удалить карту", callback_data=f"delete_skill:{index}")
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data=f"back_to_skill_list:{index}")
    )

    return builder.as_markup()


def get_list_kazin_keyboard(index: int, total: int, prefix: str = "edit_kazin_upgrades") -> InlineKeyboardMarkup:
    """Navigation keyboard for kazin upgrades (list view)."""
    builder = InlineKeyboardBuilder()

    prev_index = (index - 1) % total
    next_index = (index + 1) % total

    builder.row(
        InlineKeyboardButton(text="⬅", callback_data=f"{prefix}:navigate:prev:{index}"),
        InlineKeyboardButton(text=f"{index + 1}/{total}", callback_data=f"show_kazin_upgrade_list:{index}"),
        InlineKeyboardButton(text="➡", callback_data=f"{prefix}:navigate:next:{index}"),
    )

    builder.row(
        InlineKeyboardButton(text="Редактировать", callback_data=f"edit_kazin_upgrade:{index}")
    )

    return builder.as_markup()


def get_edit_mode_kazin_keyboard(index: int, total: int) -> InlineKeyboardMarkup:
    """Edit-mode keyboard for a single kazin upgrade."""
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="✏ Изменить название", callback_data=f"edit_kazin_name:{index}"),
    )
    builder.row(
        InlineKeyboardButton(text="⭐ Изменить редкость", callback_data=f"edit_kazin_rarity:{index}")
    )
    builder.row(
        InlineKeyboardButton(text="🔧 Изменить эффект", callback_data=f"edit_kazin_effect:{index}")
    )
    builder.row(
        InlineKeyboardButton(text="🗑 Удалить улучшение", callback_data=f"delete_kazin:{index}")
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data=f"back_to_kazin_list:{index}")
    )

    return builder.as_markup()































# === ПРОФИЛЬ МЕНЮ ===
def profile_ui(user_id: int):

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="📨 Пригласить друга",
            url=f"https://t.me/share/url?url=https://t.me/CuCbKu_gg_bot?start={user_id}&text=👋 Заходи в лучшего бота СИСЬКИ!"
        ),
    )
    builder.row(
        InlineKeyboardButton(text="🔧 Поддержка и предложения", callback_data="support_menu_button"),
    )
    builder.row(
        InlineKeyboardButton(text="⭐️ ДОНАТ", callback_data="donate_menu"),
    )
    builder.row(
        InlineKeyboardButton(text="↪️ Назад", callback_data="go_back_menu"),
    )
    return builder.as_markup()

# === ПОДДЕРЖКА МЕНЮ ===
def support_ui():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🚨 Сообщить о проблеме", callback_data="support_problem"),
    )
    builder.row(
        InlineKeyboardButton(text="💡 Предложить свою идею", callback_data="support_idea"),
    )
    builder.row(
        InlineKeyboardButton(text="↪️ Назад", callback_data="main_profile"),
    )
    return builder.as_markup()





# === ДОНАТ ===

def donate_ui():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⭐️ Звездами", callback_data="prikalyimba_donate_svoysumzv_menu"),
        InlineKeyboardButton(text="💸 Рублями", callback_data="prikalyimba_donate_svoysumrub_menu"),
    )
    builder.row(
        InlineKeyboardButton(text="↪️ Назад", callback_data="main_profile"),
    )
    return builder.as_markup()





# === ТОП ===
def top_menu_ui():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Донатеры ⭐️", callback_data="top_donators"),
    )
    builder.row(
        InlineKeyboardButton(text="Количество карт 📦", callback_data="top_cards_count"),
    )
    builder.row(
        InlineKeyboardButton(text="Количество валюты 🔥", callback_data="top_balance"),
    )
    builder.row(
        InlineKeyboardButton(text="Матершинники 😈", callback_data="top_mat_count"),
    )
    builder.row(
        InlineKeyboardButton(text="Казиношники 🎰", callback_data="top_roulette_alltime"),
    )
    builder.row(
        InlineKeyboardButton(text="Мяукальщики 😼", callback_data="top_meow_roulette"),
    )
    builder.row(
        InlineKeyboardButton(text="Поджопники 💣", callback_data="top_jopa_roulette"),
    )
    builder.row(
        InlineKeyboardButton(text="↪️ Назад", callback_data="go_back_menu"),
    )
    return builder.as_markup()

def top_leaderboard_ui():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="↪️ Назад", callback_data="top_menu"),
    )
    return builder.as_markup()

def top_roulette_ui():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="За всё время", callback_data="top_roulette_alltime"),
    )
    builder.row(
        InlineKeyboardButton(text="За сутки", callback_data="top_roulette_today"),
    )
    builder.row(
        InlineKeyboardButton(text="↪️ Назад", callback_data="top_menu"),
    )
    return builder.as_markup()

def top_meow_ui():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="По стрику", callback_data="top_meow_roulette"),
    )
    builder.row(
        InlineKeyboardButton(text="По количеству за всё время", callback_data="top_meow_roulette_alltime"),
    )
    builder.row(
        InlineKeyboardButton(text="↪️ Назад", callback_data="top_menu"),
    )
    return builder.as_markup()

def top_mat_ui():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="По количеству матов", callback_data="top_mat_count"),
    )
    builder.row(
        InlineKeyboardButton(text="По количеству отправленных матов", callback_data="top_mat_send"),
    )
    builder.row(
        InlineKeyboardButton(text="↪️ Назад", callback_data="top_menu"),
    )
    return builder.as_markup()

def top_jopa_ui():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="↪️ Назад", callback_data="top_menu"),
    )
    return builder.as_markup()

def top_cards_ui():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="👥 Участники", callback_data="top_member_card_count"),
    )
    builder.row(
        InlineKeyboardButton(text="🃏 Суперспособности", callback_data="top_skill_card_count"),
    )
    builder.row(
        InlineKeyboardButton(text="↪️ Назад", callback_data="top_menu"),
    )
    return builder.as_markup()

def top_balance_ui():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔥 Количество валюты", callback_data="top_balance"),
    )
    builder.row(
        InlineKeyboardButton(text="🔥 Заработано за всё время", callback_data="top_balance_all_time"),
    )
    builder.row(
        InlineKeyboardButton(text="↪️ Назад", callback_data="top_menu"),
    )
    return builder.as_markup()








# === МАГАЗИН ===
def shop_ui():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="❇️ Улучшения для казика. Цена: 30🔥", callback_data="shop_kazik_upgrades"),
    )
    builder.row(
        InlineKeyboardButton(text="🎰 Бонусные крутки. Цена: 10🔥", callback_data="shop_bonus_spins"),
    )
    builder.row(
        InlineKeyboardButton(text="↪️ Назад", callback_data="go_back_menu"),
    )
    return builder.as_markup()