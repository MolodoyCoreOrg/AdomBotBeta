import sqlite3
import json
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.exceptions import TelegramBadRequest

from handlers.keyboard import top_leaderboard_ui, top_roulette_ui, top_meow_ui, top_mat_ui, top_jopa_ui, top_cards_ui, top_balance_ui
from utils.config import DB_FILE  # путь к твоей базе данных

router = Router()

@router.callback_query(F.data == "top_cards_count")
async def show_top_cards_count(callback: CallbackQuery):
    await callback.message.answer("Выберите категорию в меню ниже.", reply_markup=top_cards_ui())

@router.callback_query(F.data == "top_member_card_count")
async def show_top_member_cards(callback: CallbackQuery):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # Получаем user_id, username и поле member_cards (JSON) для всех пользователей
    c.execute(
        "SELECT user_id, username, member_cards FROM users"
    )
    rows = c.fetchall()
    conn.close()

    counts = []
    for user_id, username, member_cards_json in rows:
        try:
            cards = json.loads(member_cards_json or "{}")
        except Exception:
            cards = {}

        if isinstance(cards, dict):
            cnt = len(cards)
        elif isinstance(cards, list):
            cnt = len(cards)
        else:
            cnt = 0

        counts.append((user_id, username, cnt))

    # сортируем по количеству карточек по убыванию и берём топ-10
    counts.sort(key=lambda x: x[2], reverse=True)
    top_list = counts[:10]

    if not top_list or all(item[2] == 0 for item in top_list):
        await callback.message.answer("📭 Список владельцев карточек пуст")
        await callback.answer()
        return

    text_lines = ["🏆 <b>Топ по количеству карточек участников</b> 🏆\n"]
    for i, (user_id, username, member_card_count) in enumerate(top_list, start=1):
        display_name = username if username else "Пользователь"
        if username and not username.startswith("@"):
            display_name = "@" + username
        # use medal emoji for top-3
        medal = {1: '🥇', 2: '🥈', 3: '🥉'}.get(i, f"{i}.")
        text_lines.append(
            f"{medal} {display_name}\n"
            f"Карточек: {member_card_count}\n"
        )

    try:
        await callback.message.edit_text("\n".join(text_lines), reply_markup=top_cards_ui())
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            # Игнорируем ситуацию, когда ничего не изменилось
            pass
        else:
            raise

@router.callback_query(F.data == "top_skill_card_count")
async def show_top_skill_cards(callback: CallbackQuery):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # Получаем user_id, username и поле skill_cards (JSON) для всех пользователей
    c.execute(
        "SELECT user_id, username, skill_cards FROM users"
    )
    rows = c.fetchall()
    conn.close()

    counts = []
    for user_id, username, skill_cards_json in rows:
        try:
            cards = json.loads(skill_cards_json or "{}")
        except Exception:
            cards = {}

        if isinstance(cards, dict):
            cnt = len(cards)
        elif isinstance(cards, list):
            cnt = len(cards)
        else:
            cnt = 0

        counts.append((user_id, username, cnt))

    # сортируем по количеству карточек по убыванию и берём топ-10
    counts.sort(key=lambda x: x[2], reverse=True)
    top_list = counts[:10]

    if not top_list or all(item[2] == 0 for item in top_list):
        await callback.message.answer("📭 Список владельцев карточек пуст")
        await callback.answer()
        return

    text_lines = ["🏆 <b>Топ по количеству суперспособностей</b> 🏆\n"]
    for i, (user_id, username, skill_card_count) in enumerate(top_list, start=1):
        display_name = username if username else "Пользователь"
        if username and not username.startswith("@"):
            display_name = "@" + username
        medal = {1: '🥇', 2: '🥈', 3: '🥉'}.get(i, f"{i}.")
        text_lines.append(
            f"{medal} {display_name}\n"
            f"Карточек: {skill_card_count}\n"
        )

    try:
        await callback.message.edit_text("\n".join(text_lines), reply_markup=top_cards_ui())
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            # Игнорируем ситуацию, когда ничего не изменилось
            pass
        else:
            raise

















@router.callback_query(F.data == "top_donators")
async def show_top_donators(callback: CallbackQuery):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute("""
        SELECT username, all_amount, biggest_amount 
        FROM user_donations
        ORDER BY all_amount DESC
        LIMIT 10
    """)
    top_list = c.fetchall()
    conn.close()

    if not top_list:
        await callback.message.answer("📭 Список донатеров пуст")
        await callback.answer()
        return

    text_lines = ["🏆 <b>Топ донатеров</b> 🏆\n"]
    for i, (username, all_amount, biggest_amount) in enumerate(top_list, start=1):
        display_name = username if username else "Пользователь"
        if username and not username.startswith("@"):
            display_name = "@" + username
        medal = {1: '🥇', 2: '🥈', 3: '🥉'}.get(i, f"{i}.")
        text_lines.append(
            f"{medal} {display_name}\n"
            f"Всего: {all_amount} 💰\n"
            f"Наибольший: {biggest_amount} 💰\n"
        )

    await callback.message.answer("\n".join(text_lines), reply_markup=top_leaderboard_ui())
    await callback.answer()
























@router.callback_query(F.data == "top_jopa_roulette")
async def show_top_meow_roulette(callback: CallbackQuery):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute("""
        SELECT ru.user_id, u.username, ru.jopa_count
        FROM roulette_user ru
        LEFT JOIN users u ON ru.user_id = u.user_id
        ORDER BY ru.jopa_count DESC
        LIMIT 10
    """)
    top_list = c.fetchall()
    conn.close()

    if not top_list:
        await callback.message.answer("📭 Список поджопников пуст")
        await callback.answer()
        return

    text_lines = ["🏆 <b>Топ по поджопникам</b> 🏆\n"]
    for i, (user_id, username, meow_count) in enumerate(top_list, start=1):
        display_name = username if username else "Пользователь"
        if username and not username.startswith("@"):
            display_name = "@" + username
        medal = {1: '🥇', 2: '🥈', 3: '🥉'}.get(i, f"{i}.")
        text_lines.append(
            f"{medal} {display_name}\n"
            f"Поджопников: {meow_count} \n"
        )

    try:
        await callback.message.edit_text("\n".join(text_lines), reply_markup=top_jopa_ui())
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
        # Игнорируем ситуацию, когда ничего не изменилось
            pass
        else:
            raise

@router.callback_query(F.data == "top_meow_roulette_alltime")
async def show_top_meow_roulette_alltime(callback: CallbackQuery):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute("""
        SELECT ru.user_id, u.username, ru.meow_count_all
        FROM roulette_user ru
        LEFT JOIN users u ON ru.user_id = u.user_id
        ORDER BY ru.meow_count_all DESC
        LIMIT 10
    """)
    top_list = c.fetchall()
    conn.close()

    if not top_list:
        await callback.message.answer("📭 Список мяукольщиков пуст")
        await callback.answer()
        return

    text_lines = ["🏆 <b>Топ мяуканий по количеству</b> 🏆\n"]
    for i, (user_id, username, meow_count_all) in enumerate(top_list, start=1):
        display_name = username if username else "Пользователь"
        if username and not username.startswith("@"):
            display_name = "@" + username
        medal = {1: '🥇', 2: '🥈', 3: '🥉'}.get(i, f"{i}.")
        text_lines.append(
            f"{medal} {display_name}\n"
            f"Количество: {meow_count_all} \n"
        )

    try:
        await callback.message.edit_text("\n".join(text_lines), reply_markup=top_meow_ui())
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
        # Игнорируем ситуацию, когда ничего не изменилось
            pass
        else:
            raise

@router.callback_query(F.data == "top_meow_roulette")
async def show_top_meow_roulette(callback: CallbackQuery):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute("""
        SELECT ru.user_id, u.username, ru.meow_count
        FROM roulette_user ru
        LEFT JOIN users u ON ru.user_id = u.user_id
        ORDER BY ru.meow_count DESC
        LIMIT 10
    """)
    top_list = c.fetchall()
    conn.close()

    if not top_list:
        await callback.message.answer("📭 Список мяукольщиков пуст")
        await callback.answer()
        return

    text_lines = ["🏆 <b>Топ стрик по мяуканиям</b> 🏆\n"]
    for i, (user_id, username, meow_count) in enumerate(top_list, start=1):
        display_name = username if username else "Пользователь"
        if username and not username.startswith("@"):
            display_name = "@" + username
        medal = {1: '🥇', 2: '🥈', 3: '🥉'}.get(i, f"{i}.")
        text_lines.append(
            f"{medal} {display_name}\n"
            f"Стрик: {meow_count} \n"
        )

    try:
        await callback.message.edit_text("\n".join(text_lines), reply_markup=top_meow_ui())
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
        # Игнорируем ситуацию, когда ничего не изменилось
            pass
        else:
            raise

@router.callback_query(F.data == "top_roulette_alltime")
async def show_top_roulette_alltime(callback: CallbackQuery):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # Делаем JOIN, чтобы взять username из users
    c.execute("""
        SELECT ru.user_id, u.username, ru.total_opened
        FROM roulette_user ru
        LEFT JOIN users u ON ru.user_id = u.user_id
        ORDER BY ru.total_opened DESC
        LIMIT 10
    """)
    top_list = c.fetchall()
    conn.close()

    if not top_list:
        await callback.message.answer("📭 Список казиношников пуст")
        await callback.answer()
        return

    text_lines = ["🏆 <b>Топ казиношников</b> 🏆\n"]
    for i, (user_id, username, total_opened) in enumerate(top_list, start=1):
        display_name = username if username else f"Пользователь"
        if username and not username.startswith("@"):
            display_name = "@" + username
        medal = {1: '🥇', 2: '🥈', 3: '🥉'}.get(i, f"{i}.")

        text_lines.append(
            f"{medal} {display_name}\n"
            f"Всего: {total_opened} 🎰\n"
        )

    try:
        await callback.message.edit_text("\n".join(text_lines), reply_markup=top_roulette_ui())
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
        # Игнорируем ситуацию, когда ничего не изменилось
            pass
        else:
            raise



@router.callback_query(F.data == "top_roulette_today")
async def show_top_roulette_today(callback: CallbackQuery):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # Делаем JOIN, чтобы взять username из users
    c.execute("""
        SELECT ru.user_id, u.username, ru.opened_today
        FROM roulette_user ru
        LEFT JOIN users u ON ru.user_id = u.user_id
        ORDER BY ru.opened_today DESC
        LIMIT 10
    """)
    top_list = c.fetchall()
    conn.close()

    if not top_list:
        await callback.message.answer("📭 Список казиношников пуст")
        await callback.answer()
        return

    text_lines = ["🏆 <b>Топ казиношников (За сутки)</b> 🏆\n"]
    for i, (user_id, username, opened_today) in enumerate(top_list, start=1):
        display_name = username if username else f"Пользователь"
        if username and not username.startswith("@"):
            display_name = "@" + username
        medal = {1: '🥇', 2: '🥈', 3: '🥉'}.get(i, f"{i}.")

        text_lines.append(
            f"{medal} {display_name}\n"
            f"Открыто: {opened_today} 🎰\n"
        )

    try:
        await callback.message.edit_text("\n".join(text_lines), reply_markup=top_roulette_ui())
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
        # Игнорируем ситуацию, когда ничего не изменилось
            pass
        else:
            raise
























@router.callback_query(F.data == "top_mat_send")
async def show_top_donators(callback: CallbackQuery):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute("""
        SELECT username, word_send_count 
        FROM user_donations
        ORDER BY word_send_count DESC
        LIMIT 10
    """)
    top_list = c.fetchall()
    conn.close()

    if not top_list:
        await callback.message.answer("📭 Список донатеров пуст")
        await callback.answer()
        return

    text_lines = ["🏆 <b>Топ по количеству отправленных матов</b> 🏆\n"]
    for i, (username, word_send_count) in enumerate(top_list, start=1):
        display_name = username if username else "Пользователь"
        if username and not username.startswith("@"):
            display_name = "@" + username

        medal = {1: '🥇', 2: '🥈', 3: '🥉'}.get(i, f"{i}.")

        text_lines.append(
            f"{medal} {display_name}\n"
            f"Матюкнулся: {word_send_count}\n"
        )

    try:
        await callback.message.edit_text("\n".join(text_lines), reply_markup=top_mat_ui())
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
        # Игнорируем ситуацию, когда ничего не изменилось
            pass
        else:
            raise

@router.callback_query(F.data == "top_mat_count")
async def show_top_donators(callback: CallbackQuery):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute("""
        SELECT username, word_count 
        FROM user_donations
        ORDER BY word_count DESC
        LIMIT 10
    """)
    top_list = c.fetchall()
    conn.close()

    if not top_list:
        await callback.message.answer("📭 Список донатеров пуст")
        await callback.answer()
        return

    text_lines = ["🏆 <b>Топ по количеству матюков</b> 🏆\n"]
    for i, (username, word_count) in enumerate(top_list, start=1):
        display_name = username if username else "Пользователь"
        if username and not username.startswith("@"):
            display_name = "@" + username

        medal = {1: '🥇', 2: '🥈', 3: '🥉'}.get(i, f"{i}.")

        text_lines.append(
            f"{medal} {display_name}\n"
            f"Матюков: {word_count}\n"
        )

    try:
        await callback.message.edit_text("\n".join(text_lines), reply_markup=top_mat_ui())
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
        # Игнорируем ситуацию, когда ничего не изменилось
            pass
        else:
            raise




















@router.callback_query(F.data == "top_balance")
async def show_top_meow_roulette(callback: CallbackQuery):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute("""
        SELECT user_id, username, balance 
        FROM users
        ORDER BY balance DESC
        LIMIT 10
    """)
    top_list = c.fetchall()
    conn.close()

    if not top_list:
        await callback.message.answer("📭 Список богачей пуст")
        await callback.answer()
        return

    text_lines = ["🏆 <b>Валюта прямо сейчас</b> 🏆\n"]
    for i, (user_id, username, balance) in enumerate(top_list, start=1):
        display_name = username if username else "Пользователь"
        if username and not username.startswith("@"):
            display_name = "@" + username

        medal = {1: '🥇', 2: '🥈', 3: '🥉'}.get(i, f"{i}.")

        text_lines.append(
            f"{medal} {display_name}\n"
            f"Баланс: {balance} 🔥\n"
        )

    try:
        await callback.message.edit_text("\n".join(text_lines), reply_markup=top_balance_ui())
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
        # Игнорируем ситуацию, когда ничего не изменилось
            pass
        else:
            raise

@router.callback_query(F.data == "top_balance_all_time")
async def show_top_meow_roulette(callback: CallbackQuery):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute("""
        SELECT user_id, username, balance_all_time
        FROM users
        ORDER BY balance_all_time DESC
        LIMIT 10
    """)
    top_list = c.fetchall()
    conn.close()

    if not top_list:
        await callback.message.answer("📭 Список богачей пуст")
        await callback.answer()
        return

    text_lines = ["🏆 <b>Валюта за все время</b> 🏆\n"]
    for i, (user_id, username, balance_all_time) in enumerate(top_list, start=1):
        display_name = username if username else "Пользователь"
        if username and not username.startswith("@"):
            display_name = "@" + username

        medal = {1: '🥇', 2: '🥈', 3: '🥉'}.get(i, f"{i}.")

        text_lines.append(
            f"{medal} {display_name}\n"
            f"Заработано: {balance_all_time} 🔥\n"
        )

    try:
        await callback.message.edit_text("\n".join(text_lines), reply_markup=top_balance_ui())
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
        # Игнорируем ситуацию, когда ничего не изменилось
            pass
        else:
            raise