import json
import random
import datetime
import re
import os
import sqlite3

from aiogram import Router, F, types
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest

from database.db import connect
from utils.config import DB_FILE
from utils.helpers import safe_edit_message
from handlers.keyboard import get_back_menu_button

router = Router()

KAZINO_FILE = os.path.join("data", "cards", "kazino_upgrades.json")


def shop_menu_kb():
    kb = InlineKeyboardBuilder()
    kb.row(
        types.InlineKeyboardButton(text="❇️ Улучшение казика. Цена: 30🔥", callback_data="shop_upgrade_kazino")
    )
    kb.row(
        types.InlineKeyboardButton(text="🎰 Покупка спинов. Цена: 10🔥 = 5🎰", callback_data="shop_buy_spins")
    )
    kb.row(
        types.InlineKeyboardButton(text="↪️ Назад", callback_data="go_back_menu")
    )
    return kb.as_markup()

def kazino_upgrades_menu_kb():
    kb = InlineKeyboardBuilder()
    kb.row(
        types.InlineKeyboardButton(text="❇️ Улучшение казика. Цена: 30🔥", callback_data="shop_upgrade_kazino")
    )
    kb.row(
        types.InlineKeyboardButton(text="🎰 Покупка спинов. Цена: 10🔥 = 5🎰", callback_data="shop_buy_spins")
    )
    kb.row(
        types.InlineKeyboardButton(text="↪️ Назад", callback_data="main_profile")
    )
    return kb.as_markup()


def confirm_kb(confirm_cb: str, cancel_cb: str = "go_back_button"):
    kb = InlineKeyboardBuilder()
    kb.row(
        types.InlineKeyboardButton(text="Купить", callback_data=confirm_cb),
        types.InlineKeyboardButton(text="Отмена", callback_data=cancel_cb),
    )
    return kb.as_markup()


def load_kazino_upgrades():
    if not os.path.exists(KAZINO_FILE):
        return []
    try:
        with open(KAZINO_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def pick_upgrade(upgrades: list):
    # Determine weights from 'rarity' field. If rarity is numeric, use it; otherwise map known strings.
    mapping = {
        "common": 70,
        "uncommon": 20,
        "rare": 8,
        "epic": 2,
        "legendary": 0.5,
    }
    weights = []
    for u in upgrades:
        r = u.get("rarity")
        try:
            w = float(r)
        except Exception:
            w = mapping.get(str(r).lower(), 1.0)
        weights.append(max(0.0, w))

    if not upgrades:
        return None
    try:
        return random.choices(upgrades, weights=weights, k=1)[0]
    except Exception:
        return random.choice(upgrades)


def ensure_purchase_log_table():
    with connect() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS purchase_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                item TEXT,
                detail TEXT,
                date TEXT
            )
            """
        )
        conn.commit()

# Create purchase_log table on module import to avoid creating it during request handling
try:
    ensure_purchase_log_table()
except Exception:
    # ignore failures at import time; handlers will still function and table can be created later
    pass


@router.callback_query(F.data == "shop_menu")
async def shop_menu(callback: CallbackQuery):
    user_id = int(callback.from_user.id)
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        if not row:
            await callback.answer("❌ Профиль не найден.", show_alert=True)
            return
        balance = row[0]
    await safe_edit_message(callback.message, f"🛒 Добро пожаловать в магазин! Здесь вы можете приобрести различные улучшения для казика и бонусные крутки.\n Выберите интересующую вас категорию:\n\n"
                                     f"Ваш баланс: {balance}🔥", reply_markup=shop_menu_kb())


# --- Улучшение казика: показываем подтверждение ---
@router.callback_query(F.data == "shop_upgrade_kazino")
async def shop_upgrade_kazino(callback: CallbackQuery):
    text = (
    "В данный момент улучшения для казино временно недоступны.\n"
    )
#    text = (
#        "После покупки вы получите случайное улучшение для казино.\n"
#        "Вы точно хотите купить?\n\nЦена: 30🔥"
#    )
    await safe_edit_message(callback.message, text, reply_markup=get_back_menu_button())
# confirm_kb("shop_confirm_buy_upgrade", "shop_menu")

@router.callback_query(F.data == "shop_confirm_buy_upgrade")
async def shop_confirm_buy_upgrade(callback: CallbackQuery):
    user_id = int(callback.from_user.id)
    username = callback.from_user.username or ""

    # check balance
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        if not row:
            await callback.answer("❌ Профиль не найден.", show_alert=True)
            return
        balance = row[0]

        if balance < 30:
            await callback.answer("❌ Недостаточно средств (нужно 30).", show_alert=True)
            return

        # debit
        cur.execute("UPDATE users SET balance = balance - 30 WHERE user_id = ?", (user_id,))

        # ensure roulette_user exists
        cur.execute("SELECT user_id, kazino_upgrades, roulette_count FROM roulette_user WHERE user_id = ?", (user_id,))
        ru = cur.fetchone()
        now_iso = datetime.datetime.utcnow().isoformat()
        if not ru:
            # create with defaults
            cur.execute("INSERT INTO roulette_user (user_id, last_increment, kazino_upgrades) VALUES (?, ?, ?)", (user_id, now_iso, json.dumps([])))
            kazino_list = []
            roulette_count = 0
        else:
            kazino_list = json.loads(ru[1]) if ru[1] else []
            roulette_count = ru[2] or 0

        # pick upgrade
        upgrades = load_kazino_upgrades()
        chosen = pick_upgrade(upgrades)
        if not chosen:
            await callback.answer("❌ В магазине пока нет улучшений.", show_alert=True)
            conn.commit()
            return

        # append chosen (store name/effect/rarity and timestamp)
        entry = {
            "name": chosen.get("name"),
            "effect": chosen.get("effect"),
            "rarity": chosen.get("rarity"),
            "ts": now_iso
        }
        kazino_list.append(entry)

        cur.execute("UPDATE roulette_user SET kazino_upgrades = ? WHERE user_id = ?", (json.dumps(kazino_list, ensure_ascii=False), user_id))

        # log purchase
        cur.execute(
            "INSERT INTO purchase_log (user_id, username, item, detail, date) VALUES (?, ?, ?, ?, ?)",
            (user_id, username, "kazino_upgrade", entry["name"], now_iso)
        )

        conn.commit()

    await safe_edit_message(callback.message, f"🎉 Куплено: {entry['name']} ({entry['effect']}).\nСтоимость: 30🔥", reply_markup=shop_menu_kb())


@router.callback_query(F.data == "shop_buy_spins")
async def shop_buy_spins(callback: CallbackQuery):
    # Show confirmation message for buying spins
    text = (
        "Покупка пакета круток: +5 круток за 10🔥.\n"
        "Вы точно хотите купить?"
    )
    await safe_edit_message(callback.message, text, reply_markup=confirm_kb("shop_confirm_buy_spins", "shop_menu"))


@router.callback_query(F.data == "shop_confirm_buy_spins")
async def shop_confirm_buy_spins(callback: CallbackQuery):
    user_id = int(callback.from_user.id)
    username = callback.from_user.username or ""

    with connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        if not row:
            await callback.answer("❌ Профиль не найден.", show_alert=True)
            return
        balance = row[0]
        if balance < 10:
            await callback.answer("❌ Недостаточно средств (нужно 10).", show_alert=True)
            return

        # debit
        cur.execute("UPDATE users SET balance = balance - 10 WHERE user_id = ?", (user_id,))

        # ensure roulette_user exists and add spins (roulette_count)
        cur.execute("SELECT roulette_count FROM roulette_user WHERE user_id = ?", (user_id,))
        ru = cur.fetchone()
        if not ru:
            cur.execute("INSERT INTO roulette_user (user_id, last_increment, roulette_count) VALUES (?, ?, ?)", (user_id, datetime.datetime.utcnow().isoformat(), 5 + 5))
            new_count = 5 + 5
        else:
            cur.execute("UPDATE roulette_user SET roulette_count = roulette_count + 5 WHERE user_id = ?", (user_id,))
            cur.execute("SELECT roulette_count FROM roulette_user WHERE user_id = ?", (user_id,))
            new_count = cur.fetchone()[0]

        # log purchase
        cur.execute(
            "INSERT INTO purchase_log (user_id, username, item, detail, date) VALUES (?, ?, ?, ?, ?)",
            (user_id, username, "spins", "+5 spins", datetime.datetime.utcnow().isoformat())
        )

        conn.commit()

    await safe_edit_message(callback.message, f"✅ Куплено: +5 круток. Сейчас у тебя {new_count} круток.", reply_markup=shop_menu_kb())


@router.callback_query(F.data == "shop_my_upgrades")
async def shop_my_upgrades(callback: CallbackQuery):
    user_id = int(callback.from_user.id)

    with connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT kazino_upgrades FROM roulette_user WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        if not row or not row[0]:
            await callback.answer()
            await callback.message.edit_text("У тебя пока нет улучшений.", reply_markup=kazino_upgrades_menu_kb())
            return

        try:
            upgrades = json.loads(row[0])
        except Exception:
            upgrades = []

    # aggregate by name
    agg = {}
    for u in upgrades:
        name = u.get("name") or str(u.get("effect") or "unknown")
        effect = u.get("effect") or ""
        # attempt to extract numeric value from effect
        m = re.search(r"([+-]?\d+)", effect)
        num = int(m.group(1)) if m else None
        key = (name, effect)
        if key not in agg:
            agg[key] = {"count": 0, "num_total": 0, "effect": effect}
        agg[key]["count"] += 1
        if num is not None:
            agg[key]["num_total"] += num

    lines = ["🏬 Мои улучшения:\n"]
    for (name, effect), data in agg.items():
        if data["num_total"] != 0:
            # show aggregated numeric effect
            lines.append(f"{name}: {data['num_total']}")
        else:
            if data["count"] > 1:
                lines.append(f"{name}: {data['count']}× {effect}")
            else:
                lines.append(f"{name}: {effect}")

    try:
        await callback.message.edit_text("\n".join(lines), reply_markup=shop_menu_kb())
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            pass
        else:
            raise
