import asyncio, json, os, random, datetime

from aiogram import Router, types, F, Bot, Dispatcher
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton
from aiogram.exceptions import TelegramBadRequest
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from database.db import add_skill_bonus, add_member_bonus, load_roulette_data, save_roulette_data, append_roulette_history
from utils.helpers import format_time_left, get_combo_text, safe_edit_message, safe_delete
from utils.config import TOKEN

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

router = Router()

# Config/constants
MAX_SPINS = 10
INCREMENT = 2  # сколько круток выдаётся
INTERVAL = 3600  # раз в час

active_spins = {}

# --- Улучшения казика за 🔥 ---
CASINO_UPGRADES_POOL = [
    # Обычные улучшения (вес 70%)
    {"id": "spin_per_hour_plus", "name": "+1 крутка в час", "rarity": "common", "weight": 15, "max_count": None},
    {"id": "max_spins_plus", "name": "+1 к максимальному накапливаемому количеству круток", "rarity": "common", "weight": 15, "max_count": None},
    {"id": "jopa_fire_2", "name": "Выпадение поджопника дает 2🔥", "rarity": "common", "weight": 12, "max_count": None},
    {"id": "ghost_spins_plus5", "name": "Выпадение призраков дает на 5 больше круток", "rarity": "common", "weight": 12, "max_count": None},
    {"id": "meow_fire", "name": "При мяуканьи больше 5 раз дается 1🔥", "rarity": "common", "weight": 10, "max_count": None},
    {"id": "kiss_kiss_kiss_fire", "name": "При выпадении 💋💋💋 дается 300 🔥", "rarity": "common", "weight": 6, "max_count": None},
    {"id": "dopa_mechanic", "name": "Открыта механика ДОДЕПА - ставьте 🔥 и получайте x10 при любой комбинации", "rarity": "common", "weight": 10, "max_count": None},
    # Редкие улучшения (вес 20%)
    {"id": "timer_reduce_10min", "name": "Минус 10 минут к таймеру пополнения круток", "rarity": "rare", "weight": 20, "max_count": 3},
    # Эпическое улучшение (вес 7%)
    {"id": "double_casino", "name": "Можно крутить сразу два казика", "rarity": "epic", "weight": 7, "max_count": 1},
    # Легендарное улучшение (вес 3%)
    {"id": "fast_spin", "name": "Появляется возможность быстрой прокрутки", "rarity": "legendary", "weight": 3, "max_count": 1},
]

def get_user_upgrades_dict(kazino_upgrades_raw) -> dict:
    """
    Преобразует сырые данные kazino_upgrades (это может быть список словарей или словарь {id: count})
    в единый словарь {upgrade_id: count}.
    """
    if not kazino_upgrades_raw:
        return {}
    
    # Если это уже словарь {id: count}
    if isinstance(kazino_upgrades_raw, dict):
        clean_upgrades = {}
        for k, v in kazino_upgrades_raw.items():
            if isinstance(v, dict):
                clean_upgrades[k] = clean_upgrades.get(k, 0) + 1
            elif isinstance(v, int):
                clean_upgrades[k] = v
            else:
                try:
                    clean_upgrades[k] = int(v)
                except Exception:
                    clean_upgrades[k] = 1
        return clean_upgrades
        
    # Если это список словарей (из Shop)
    if isinstance(kazino_upgrades_raw, list):
        upgrades_dict = {}
        for item in kazino_upgrades_raw:
            if isinstance(item, dict):
                upgrade_id = item.get("id")
                if upgrade_id:
                    upgrades_dict[upgrade_id] = upgrades_dict.get(upgrade_id, 0) + 1
            elif isinstance(item, str):
                upgrades_dict[item] = upgrades_dict.get(item, 0) + 1
        return upgrades_dict
        
    return {}

def get_user_kazino_limits(kazino_upgrades: dict) -> tuple[int, int, int]:
    """
    Возвращает (increment, max_spins, interval_seconds) для пользователя
    с учетом его улучшений казино.
    """
    user_upgrades = get_user_upgrades_dict(kazino_upgrades)
    spin_per_hour = user_upgrades.get("spin_per_hour_plus", 0)
    max_spins_plus = user_upgrades.get("max_spins_plus", 0)
    timer_reduce = user_upgrades.get("timer_reduce_10min", 0)
    timer_reduce = min(3, timer_reduce)

    increment = 2 + spin_per_hour
    max_spins = 10 + max_spins_plus
    interval = 3600 - (timer_reduce * 600)  # минус 10 минут за каждый уровень

    return increment, max_spins, interval

def get_available_upgrades(user_data: dict) -> list:
    """Возвращает список доступных улучшений с учетом уже полученных"""
    available = []
    upgrades_raw = user_data.get("kazino_upgrades", {})
    upgrades = get_user_upgrades_dict(upgrades_raw)
    
    for upgrade in CASINO_UPGRADES_POOL:
        current_count = upgrades.get(upgrade["id"], 0)
        max_count = upgrade.get("max_count")
        
        # Если есть лимит и он достигнут - пропускаем
        if max_count is not None and current_count >= max_count:
            continue
        
        available.append(upgrade)
    
    return available

def get_random_upgrade(user_data: dict) -> dict | None:
    """Выбирает случайное улучшение из доступных с учетом весов"""
    available = get_available_upgrades(user_data)
    if not available:
        return None
    
    total_weight = sum(u["weight"] for u in available)
    if total_weight == 0:
        return None
    
    r = random.uniform(0, total_weight)
    cumulative = 0
    for upgrade in available:
        cumulative += upgrade["weight"]
        if r <= cumulative:
            return upgrade
    
    return available[-1]

def apply_upgrade(user_data: dict, upgrade: dict) -> tuple[str, dict]:
    """Применяет улучшение и возвращает описание и обновленные данные"""
    upgrades_raw = user_data.get("kazino_upgrades", {})
    upgrades = get_user_upgrades_dict(upgrades_raw)
    upgrade_id = upgrade["id"]
    current_count = upgrades.get(upgrade_id, 0)
    new_count = current_count + 1
    
    upgrades[upgrade_id] = new_count
    user_data["kazino_upgrades"] = upgrades
    
    description = f"🎁 Получено улучшение: {upgrade['name']} ({upgrade['rarity']})"
    
    # Применяем эффекты улучшений
    if upgrade_id == "spin_per_hour_plus":
        pass
    elif upgrade_id == "max_spins_plus":
        pass
    elif upgrade_id == "timer_reduce_10min":
        user_data["upgrade_timer_reduce"] = user_data.get("upgrade_timer_reduce", 0) + 1
    elif upgrade_id == "double_casino":
        user_data["has_double_casino"] = True
    elif upgrade_id == "fast_spin":
        user_data["has_fast_spin"] = True
    elif upgrade_id == "dopa_mechanic":
        pass
    
    return description, user_data

# --- Inline клавиатура под сообщением рулетки ---
def get_roulette_inline_keyboard(user_data=None):
    builder = InlineKeyboardBuilder()
    
    # Если есть быстрая прокрутка, показываем две кнопки в один ряд
    if user_data:
        upgrades = get_user_upgrades_dict(user_data.get("kazino_upgrades", {}))
        if upgrades.get("fast_spin", 0) > 0:
            builder.row(
                types.InlineKeyboardButton(text="🎰 Обычный прокрут", callback_data="spin_roulette"),
                types.InlineKeyboardButton(text="⚡ Быстрый прокрут", callback_data="spin_fast_roulette")
            )
        else:
            builder.row(
                types.InlineKeyboardButton(text="🎰 Крутить казик", callback_data="spin_roulette")
            )
    else:
        builder.row(
            types.InlineKeyboardButton(text="🎰 Крутить казик", callback_data="spin_roulette"),
        )
        
    # Добавляем переключатель ставки ДОДЕПА
    if user_data:
        upgrades = get_user_upgrades_dict(user_data.get("kazino_upgrades", {}))
        dopa_bet = user_data.get("dopa_bet", 0)
        if "dopa_mechanic" in upgrades:
            dopa_text = f"🔥 ДОДЕП: {dopa_bet} 🔥" if dopa_bet > 0 else "🔥 ДОДЕП: ВЫКЛ"
            builder.row(
                types.InlineKeyboardButton(text=dopa_text, callback_data="toggle_dopa_bet")
            )

        fire_points = user_data.get("fire_points", 0)
        if fire_points > 0 or "dopa_mechanic" in upgrades:
            builder.row(
                types.InlineKeyboardButton(text="🔥 Магазин улучшений", callback_data="casino_upgrades_shop"),
            )
            
    builder.row(
        types.InlineKeyboardButton(text="📜 Список последних 10 наград", callback_data="show_history"),
    )
    builder.row(
        types.InlineKeyboardButton(text="↪️ Назад", callback_data="go_back_menu"),
    )
    return builder.as_markup()

def get_roulette_again_keyboard(user_data=None):
    builder = InlineKeyboardBuilder()
    spin_callback = "spin_fast_roulette"
    if user_data:
        upgrades = get_user_upgrades_dict(user_data.get("kazino_upgrades", {}))
        if upgrades.get("fast_spin", 0) == 0:
            spin_callback = "spin_roulette"
    else:
        spin_callback = "spin_roulette"
        
    builder.row(
        types.InlineKeyboardButton(text="🎰 Крутить ещё раз", callback_data=spin_callback)
    )
    builder.row(
        types.InlineKeyboardButton(text="Назад", callback_data="go_back_button"),
    )
    return builder.as_markup()

def get_roulette_again_fast_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="🎰 Крутить ещё раз", callback_data="spin_fast_roulette")
    )
    builder.row(
        types.InlineKeyboardButton(text="Назад", callback_data="go_back_button"),
    )
    return builder.as_markup()

def get_roulette_notify_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="🎰 Крутить казик", callback_data="spin_roulette"),
    )
    return builder.as_markup()

def get_roulette_inline_keyboard_2():
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="Назад", callback_data="go_back_button"),
    )
    return builder.as_markup()

def get_roulette_SDVG_button():
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="Мяу", callback_data="SDVG_meow"),
    )
    return builder.as_markup()

# безопасная отправка
async def _safe_send(user_id: int, text: str, reply_markup=None):
    from aiogram.exceptions import TelegramRetryAfter, TelegramForbiddenError, TelegramBadRequest

    try:
        await bot.send_message(user_id, text, reply_markup=reply_markup)
        return True
    except (TelegramForbiddenError, TelegramBadRequest) as e:
        print(f"[safe_send] Не удалось отправить {user_id}: {e}")
    except TelegramRetryAfter as e:
        print(f"[safe_send] Flood control: ждем {e.retry_after} секунд")
        await asyncio.sleep(e.retry_after)
        return await _safe_send(user_id, text, reply_markup=reply_markup)
    except Exception as e:
        print(f"[safe_send] Ошибка {user_id}: {e}")
    return False

# объединённая задача: инкремент + уведомление
async def roulette_increment_task():
    from database.db import connect
    while True:
        now = datetime.datetime.utcnow()

        conn = connect()
        cursor = conn.cursor()

        cursor.execute("SELECT user_id, roulette_count, last_increment, notified_max, kazino_upgrades FROM roulette_user")
        rows = cursor.fetchall()

        for user_id, roulette_count, last_increment, notified_max, kazino_upgrades_json in rows:
            try:
                last_inc = datetime.datetime.fromisoformat(last_increment)
            except Exception:
                last_inc = now

            upgrades = json.loads(kazino_upgrades_json) if kazino_upgrades_json else {}
            user_increment, user_max_spins, user_interval = get_user_kazino_limits(upgrades)

            seconds_passed = (now - last_inc).total_seconds()
            increments_passed = seconds_passed // user_interval
            
            if increments_passed >= 1:
                if roulette_count < user_max_spins:
                    new_count = min(user_max_spins, roulette_count + user_increment * int(increments_passed))
                    next_iso = (last_inc + datetime.timedelta(seconds=increments_passed * user_interval)).isoformat()
                    cursor.execute(
                        "UPDATE roulette_user SET roulette_count = ?, last_increment = ? WHERE user_id = ?",
                        (new_count, next_iso, user_id),
                    )

                    # уведомляем, если накопилось максимум
                    if new_count >= user_max_spins and not notified_max:
                        sent = await _safe_send(
                            user_id,
                            f"🎰 У тебя накопилось {new_count} круток! Самое время испытать удачу!", reply_markup=get_roulette_notify_keyboard()
                        )
                        if sent:
                            cursor.execute(
                                "UPDATE roulette_user SET notified_max = 1 WHERE user_id = ?",
                                (user_id,)
                            )
                else:
                    # если уже был максимум — сбрасываем дату на сейчас
                    cursor.execute(
                        "UPDATE roulette_user SET last_increment = ? WHERE user_id = ?",
                        (now.isoformat(), user_id)
                    )

        conn.commit()
        conn.close()

        await asyncio.sleep(60)  # Спим каждую минуту для быстрой точности!

def seconds_until_next_increment(last_increment_iso: str, interval: int = 3600) -> int:
    last_increment = datetime.datetime.fromisoformat(last_increment_iso)
    now = datetime.datetime.utcnow()
    seconds_passed = (now - last_increment).total_seconds()
    seconds_until_next = interval - (seconds_passed % interval)
    return int(seconds_until_next)

async def send_roulette_status_message(target: Message | CallbackQuery, user_id: str, edit: bool = False):
    from database.db import connect
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("SELECT roulette_count, last_increment, total_opened, meow_count, meow_count_all, jopa_count, fire_points, kazino_upgrades, dopa_bet FROM roulette_user WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return

    roulette_count, last_increment, total_opened, meow_count, meow_count_all, jopa_count, fire_points, kazino_upgrades_json, dopa_bet = row
    kazino_upgrades = json.loads(kazino_upgrades_json) if kazino_upgrades_json else {}

    user_increment, user_max_spins, user_interval = get_user_kazino_limits(kazino_upgrades)
    seconds_left = seconds_until_next_increment(last_increment, user_interval)
    formatted_time_left = format_time_left(seconds_left)

    user_upgrades_dict = get_user_upgrades_dict(kazino_upgrades)
    upgrades_count = len(user_upgrades_dict)
    
    fire_text = f"🔥 Огоньки: {fire_points}\n" if fire_points > 0 else ""
    upgrades_text = f"🎁 Улучшений: {upgrades_count}\n" if upgrades_count > 0 else ""
    dopa_text = f"🎲 Ставка ДОДЕПА: <b>{dopa_bet} 🔥</b>\n" if dopa_bet > 0 else ""

    text = (
        f"🎰 У тебя есть {roulette_count} круток.\n"
        f"⏳ До следующей крутки: <b>{formatted_time_left}</b>\n"
        f"📊 Всего круток открыто: {total_opened}\n\n"
        f"{fire_text}"
        f"{upgrades_text}"
        f"{dopa_text}"
        f"😹 Мяу ^_^\n"
        f"Наибольший стрик : {meow_count}\n"
        f"Всего мяуканий: {meow_count_all}\n\n"
        f"💣 Всего поджопников: {jopa_count}\n\n"
        f"Каждый час бот выдаёт {user_increment} круток. Максимум может быть {user_max_spins}."
    )

    user_data = {
        "fire_points": fire_points,
        "kazino_upgrades": kazino_upgrades,
        "dopa_bet": dopa_bet
    }

    if isinstance(target, CallbackQuery):
        if edit:
            await target.message.edit_text(text, reply_markup=get_roulette_inline_keyboard(user_data))
        else:
            await target.answer()
            await target.message.edit_text(text, reply_markup=get_roulette_inline_keyboard(user_data))
    else:
        await safe_delete(target)
        await target.answer(text, reply_markup=get_roulette_inline_keyboard(user_data))

# ДАТА РУЛЕТКИ
STATS_FILE = "data/table/stats.json"

DEFAULT_PRIZES = {
    "JOPA": 0,
    "+10": 0,
    "skills_bonus": 0,
    "members_bonus": 0,
    "POCELUI": 0,
    "nothing": 0
}

def load_stats() -> dict:
    if not os.path.exists(STATS_FILE):
        return {"global": {"roulette_opened": 0, "roulette_prizes": DEFAULT_PRIZES.copy()},
                "daily": {}}
    try:
        with open(STATS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"global": {"roulette_opened": 0, "roulette_prizes": DEFAULT_PRIZES.copy()},
                "daily": {}}

def save_stats(stats: dict):
    os.makedirs(os.path.dirname(STATS_FILE), exist_ok=True)
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

def ensure_day(stats: dict, today: str):
    """Создаёт блок для дня, если его ещё нет"""
    if "daily" not in stats:
        stats["daily"] = {}
    if today not in stats["daily"]:
        stats["daily"][today] = {
            "roulette_opened": 0,
            "roulette_prizes": DEFAULT_PRIZES.copy()
        }

def update_stats(prize_key: str):
    stats = load_stats()
    today = datetime.datetime.now().strftime("%Y-%m-%d")

    ensure_day(stats, today)

    # глобальная статистика
    stats["global"]["roulette_opened"] += 1
    if prize_key in stats["global"]["roulette_prizes"]:
        stats["global"]["roulette_prizes"][prize_key] += 1

    # статистика за день
    stats["daily"][today]["roulette_opened"] += 1
    if prize_key in stats["daily"][today]["roulette_prizes"]:
        stats["daily"][today]["roulette_prizes"][prize_key] += 1

    save_stats(stats)

# --- Настройка шансов выпадения символов (в процентах) ---
SLOT_CHANCES = {
    "💣": 23.9,
    "👻": 25.0,
    "✅": 19.0,
    "😹": 12.0,
    "💋": 5.0,
}

SPECIAL_REWARDS = {
    "😹": "draw_member",
    "✅": "draw_skill",
    "👻": "add_spins",
    "💣": "die_spins",
    "💋": "full_die"
}

def _get_symbols_and_weights():
    symbols = list(SLOT_CHANCES.keys())
    weights = [max(0.0, float(SLOT_CHANCES[s])) for s in symbols]
    if sum(weights) == 0:
        weights = [1.0] * len(symbols)
    return symbols, weights

meow_stats = {}

@router.callback_query(F.data == "toggle_dopa_bet")
async def toggle_dopa_bet(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    data = load_roulette_data(user_id)
    
    current_bet = data.get("dopa_bet", 0)
    fire_points = data.get("fire_points", 0)
    
    if current_bet > 0:
        new_bet = 0
        await callback.answer("🔥 ДОДЕП выключен.")
    else:
        if fire_points < 10:
            await callback.answer("❌ Недостаточно 🔥 для ставки! Нужно минимум 10 🔥", show_alert=True)
            return
        new_bet = 10
        await callback.answer("🔥 ДОДЕП включен на ставку 10 🔥!")
        
    data["dopa_bet"] = new_bet
    save_roulette_data(user_id, data)
    await send_roulette_status_message(callback, user_id, edit=True)

# --- Обработка нажатия кнопки "Крутить рулетку" ---
@router.callback_query(F.data == "spin_roulette")
async def spin_roulette(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    data = load_roulette_data(user_id)
    upgrades = get_user_upgrades_dict(data.get("kazino_upgrades", {}))

    # Лимиты параллельного казика
    max_allowed = 2 if "double_casino" in upgrades else 1
    current_active = active_spins.get(user_id, 0)
    if current_active >= max_allowed:
        await callback.answer("⏳ Подожди, другие прокруты казика ещё идут.", show_alert=True)
        return
    active_spins[user_id] = current_active + 1

    try:
        now = datetime.datetime.utcnow()
        today_str = now.strftime("%Y-%m-%d")

        # --- Сброс дневного лимита ---
        if data["last_reset"] != today_str:
            data["opened_today"] = 0
            data["last_reset"] = today_str

        # --- Авто-прибавка рулеток ---
        user_increment, user_max_spins, user_interval = get_user_kazino_limits(data.get("kazino_upgrades", {}))
        last_increment = datetime.datetime.fromisoformat(data["last_increment"])
        increments_passed = (now - last_increment).total_seconds() // user_interval
        if increments_passed >= 1:
            if data["roulette_count"] < user_max_spins:
                data["roulette_count"] = min(user_max_spins, data["roulette_count"] + user_increment * int(increments_passed))
            data["last_increment"] = now.isoformat()

        if data["roulette_count"] == 0:
            await callback.answer("🎰 У тебя нет круток.", show_alert=True)
            return

        if data["opened_today"] >= 100000:
            await callback.answer("🎰 Ты уже открыл 100000 круток сегодня.", show_alert=True)
            return

        # Проверяем ставку ДОДЕПА
        is_dopa_active = False
        dopa_bet = data.get("dopa_bet", 0)
        if dopa_bet > 0:
            if data["fire_points"] < dopa_bet:
                data["dopa_bet"] = 0
                save_roulette_data(user_id, data)
                await callback.answer("❌ Ставка ДОДЕПА отключена из-за нехватки 🔥!", show_alert=True)
                return
            else:
                data["fire_points"] -= dopa_bet
                is_dopa_active = True

        # --- Уменьшаем рулетку ---
        data["roulette_count"] -= 1
        data["opened_today"] += 1
        data["total_opened"] += 1
        data["notified_max"] = False
        save_roulette_data(user_id, data)

        # --- Сообщение со слотами ---
        await safe_delete(callback)
        slot_msg = await callback.message.answer("🎰 Крутим...\n⬛ ⬛ ⬛")

        # --- Символы ---
        symbols, weights = _get_symbols_and_weights()
        result = random.choices(symbols, weights=weights, k=3)

        # --- Анимация ---
        async def animate():
            last_text = None
            rounds = 12
            for i in range(rounds):
                interim = random.choices(symbols, weights=weights, k=3)
                interim_text = " ".join(interim)

                if interim_text != last_text:
                    try:
                        await slot_msg.edit_text(
                            interim_text,
                            reply_markup=get_roulette_SDVG_button()
                        )
                        last_text = interim_text
                    except TelegramBadRequest as e:
                        if "message is not modified" not in str(e):
                            raise

                await asyncio.sleep(0.04 + (i / (rounds - 1)) * 0.46)

            final_text = " ".join(result)
            if final_text != last_text:
                await slot_msg.edit_text(final_text)

        try:
            await asyncio.wait_for(animate(), timeout=7.0)
        except asyncio.TimeoutError:
            await slot_msg.edit_text(" ".join(result))
        except Exception:
            # откат крутки при ошибке
            data["roulette_count"] = data.get("roulette_count", 0) + 1
            data["opened_today"] = max(0, data.get("opened_today", 1) - 1)
            data["total_opened"] = max(0, data.get("total_opened", 1) - 1)
            if is_dopa_active:
                data["fire_points"] += dopa_bet
            save_roulette_data(user_id, data)
            raise

        await asyncio.sleep(0.6)

        stats = meow_stats.pop(int(user_id), None)
        meow_count_gained = stats.get("count", 0) if stats else 0
        
        # Обновляем мяу-статы
        if meow_count_gained > 0:
            data = load_roulette_data(user_id)
            stats_old = data.get("meow_count") or 0
            stats_old_all = data.get("meow_count_all") or 0

            if meow_count_gained > stats_old:
                data["meow_count"] = meow_count_gained
            data["meow_count_all"] = stats_old_all + meow_count_gained

            # Улучшение meow_fire: если мяукнул > 5 раз, дает 1🔥
            if meow_count_gained > 5 and "meow_fire" in upgrades:
                data["fire_points"] = data.get("fire_points", 0) + 1
                
            save_roulette_data(user_id, data)

            for msg_id in stats["messages"]:
                try:
                    await slot_msg.bot.delete_message(callback.message.chat.id, msg_id)
                except Exception:
                    pass

        # Обработка комбинации
        multiplier = 10 if is_dopa_active else 1
        dopa_text_suffix = f" (🔥 ДОДЕП x10!)" if is_dopa_active else ""

        if result[0] == result[1] == result[2]:
            symbol = result[0]
            reward_text = None

            if symbol == "😹":
                for _ in range(multiplier):
                    add_member_bonus(user_id)
                    update_stats("members_bonus")
                
                reward_text = f"🎁 Возможность открыть карточку участника x{multiplier}{dopa_text_suffix}"
                meow_suffix = f"\n😺 Вы мяукнули {meow_count_gained} раз" if meow_count_gained > 0 else ""
                
                await slot_msg.edit_text(f"🎉 3 кота! Ты получил возможность открыть карточку участника x{multiplier}!{dopa_text_suffix}\n"
                                        f"🎰 У тебя осталось {data['roulette_count']} круток.{meow_suffix}", reply_markup=get_roulette_again_keyboard(data))

            elif symbol == "✅":
                for _ in range(multiplier):
                    add_skill_bonus(user_id)
                    update_stats("skills_bonus")
                
                reward_text = f"🎁 Возможность открыть суперспособность x{multiplier}{dopa_text_suffix}"
                meow_suffix = f"\n😺 Вы мяукнули {meow_count_gained} раз" if meow_count_gained > 0 else ""
                
                await slot_msg.edit_text(f"🎉 3 галочки! Ты получил возможность открыть суперспособность x{multiplier}!{dopa_text_suffix}\n"
                                        f"🎰 У тебя осталось {data['roulette_count']} круток.{meow_suffix}", reply_markup=get_roulette_again_keyboard(data))

            elif symbol == "👻":
                spins_gained = 15 if "ghost_spins_plus5" in upgrades else 10
                total_spins_gained = spins_gained * multiplier
                
                data["roulette_count"] += total_spins_gained
                save_roulette_data(user_id, data)
                
                for _ in range(multiplier):
                    update_stats("+10")
                
                reward_text = f"🎁 +{total_spins_gained} Круток{dopa_text_suffix}"
                meow_suffix = f"\n😺 Вы мяукнули {meow_count_gained} раз" if meow_count_gained > 0 else ""
                
                await slot_msg.edit_text(f"👻 3 призрака! +{total_spins_gained} круток!{dopa_text_suffix}\n"
                                        f"🎰 У тебя осталось {data['roulette_count']} круток.{meow_suffix}", reply_markup=get_roulette_again_keyboard(data))
                
            elif symbol == "💣":
                data["jopa_count"] = data.get("jopa_count", 0) + multiplier
                
                fire_bonus = 2 if "jopa_fire_2" in upgrades else 0
                total_fire_bonus = fire_bonus * multiplier
                if total_fire_bonus > 0:
                    data["fire_points"] = data.get("fire_points", 0) + total_fire_bonus
                    fire_text = f" (+{total_fire_bonus}🔥)"
                else:
                    fire_text = ""
                
                save_roulette_data(user_id, data)
                
                for _ in range(multiplier):
                    update_stats("JOPA")
                    
                reward_text = f"💣 Поджопник ^_^{fire_text}{dopa_text_suffix}"
                meow_suffix = f"\n😺 Вы мяукнули {meow_count_gained} раз" if meow_count_gained > 0 else ""
                
                await slot_msg.edit_text(f"💣 Ты чертовски крут! Ты выиграл поджопник!{fire_text}{dopa_text_suffix}\n"
                                        f"🎰 У тебя осталось {data['roulette_count']} круток.{meow_suffix}", reply_markup=get_roulette_again_keyboard(data))

            elif symbol == "💋":
                reward_spins = 1 * multiplier
                reward_text = f"💋 Пранк — ничего не удалено (+{reward_spins} круток){dopa_text_suffix}"
                meow_suffix = f"\n😺 Вы мяукнули {meow_count_gained} раз" if meow_count_gained > 0 else ""

                if "kiss_kiss_kiss_fire" in upgrades:
                    data["fire_points"] = data.get("fire_points", 0) + 300 * multiplier
                    kiss_fire_text = f" и {300 * multiplier}🔥"
                else:
                    kiss_fire_text = ""

                # Сначала пугающее сообщение
                await slot_msg.edit_text(f"💋 TOТАЛЬНОЕ УНИЧТОЖЕНИЕ! ВСЕ ТВОИ КАРТЫ УДАЛЕНЫ!{dopa_text_suffix}\n"
                                        f"🎰 У тебя осталось {data['roulette_count']} круток.{meow_suffix}", reply_markup=None)

                await asyncio.sleep(2.0)
                data["roulette_count"] += reward_spins
                save_roulette_data(user_id, data)
                
                for _ in range(multiplier):
                    update_stats("POCELUI")
                
                await slot_msg.edit_text(f"😈 Пранк! Ничего не удалено — всё в безопасности.\n"
                                        f"🎁 В качестве компенсации: +{reward_spins} круток{kiss_fire_text}.{dopa_text_suffix}\n"
                                        f"🎰 У тебя теперь {data['roulette_count']} круток.{meow_suffix}", reply_markup=get_roulette_again_keyboard(data))

            if reward_text:
                append_roulette_history(int(user_id), reward_text)

        else:
            update_stats("nothing")
            meow_suffix = f"\n😺 Вы мяукнули {meow_count_gained} раз" if meow_count_gained > 0 else ""
            fail_msg = (f"😿 Увы, ничего не выпало.\nУ тебя было: {' '.join(result)}\n"
                    f"🎰 У тебя осталось {data['roulette_count']} круток.{meow_suffix}")
            await slot_msg.edit_text(fail_msg, reply_markup=get_roulette_again_keyboard(data))

    finally:
        # снимаем блокировку
        current_active = active_spins.get(user_id, 0)
        if current_active > 1:
            active_spins[user_id] = current_active - 1
        else:
            active_spins.pop(user_id, None)

@router.callback_query(F.data == "SDVG_meow")
async def sdvg_meow(callback: CallbackQuery):
    user_id = callback.from_user.id
    msg = await callback.message.answer("Мяу ^_^")

    if user_id not in meow_stats:
        meow_stats[user_id] = {"count": 0, "messages": []}

    meow_stats[user_id]["count"] += 1
    meow_stats[user_id]["messages"].append(msg.message_id)
    await callback.answer()

# --- Быстрая верcия крутилки: мгновенно показываем результат (без анимации) ---
@router.callback_query(F.data == "spin_fast_roulette")
async def spin_fast_roulette(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    data = load_roulette_data(user_id)
    upgrades = get_user_upgrades_dict(data.get("kazino_upgrades", {}))

    now = datetime.datetime.utcnow()
    today_str = now.strftime("%Y-%m-%d")

    if data["last_reset"] != today_str:
        data["opened_today"] = 0
        data["last_reset"] = today_str

    # --- Авто-прибавка рулеток ---
    user_increment, user_max_spins, user_interval = get_user_kazino_limits(data.get("kazino_upgrades", {}))
    last_increment = datetime.datetime.fromisoformat(data["last_increment"])
    increments_passed = (now - last_increment).total_seconds() // user_interval
    if increments_passed >= 1:
        if data["roulette_count"] < user_max_spins:
            data["roulette_count"] = min(user_max_spins, data["roulette_count"] + user_increment * int(increments_passed))
        data["last_increment"] = now.isoformat()

    if data["roulette_count"] == 0:
        await callback.answer("🎰 У тебя нет круток.", show_alert=True)
        return

    if data.get("opened_today", 0) >= 100000:
        await callback.answer("🎰 Ты уже открыл 100000 круток сегодня.", show_alert=True)
        return

    # Проверяем ставку ДОДЕПА
    is_dopa_active = False
    dopa_bet = data.get("dopa_bet", 0)
    if dopa_bet > 0:
        if data["fire_points"] < dopa_bet:
            data["dopa_bet"] = 0
            save_roulette_data(user_id, data)
            await callback.answer("❌ Ставка ДОДЕПА отключена из-за нехватки 🔥!", show_alert=True)
            return
        else:
            data["fire_points"] -= dopa_bet
            is_dopa_active = True

    # Снимаем крутку и сохраняем состояние
    data["roulette_count"] -= 1
    data["opened_today"] = data.get("opened_today", 0) + 1
    data["total_opened"] = data.get("total_opened", 0) + 1
    data["notified_max"] = False
    save_roulette_data(user_id, data)

    symbols, weights = _get_symbols_and_weights()
    try:
        result = random.choices(symbols, weights=weights, k=3)
        multiplier = 10 if is_dopa_active else 1
        dopa_text_suffix = f" (🔥 ДОДЕП x10!)" if is_dopa_active else ""

        if result[0] == result[1] == result[2]:
            symbol = result[0]
            reward_text = None

            if symbol == "😹":
                for _ in range(multiplier):
                    add_member_bonus(user_id)
                    update_stats("members_bonus")
                
                reward_text = f"🎁 Возможность открыть карточку участника x{multiplier}{dopa_text_suffix}"
                await callback.message.edit_text(
                    f"🎰 Результат быстрых слотов: {' '.join(result)}\n\n"
                    f"🎉 3 кота! Ты получил возможность открыть карточку участника x{multiplier}!{dopa_text_suffix}\n"
                    f"🎰 У тебя осталось {data['roulette_count']} круток.",
                    reply_markup=get_roulette_again_fast_keyboard()
                )

            elif symbol == "✅":
                for _ in range(multiplier):
                    add_skill_bonus(user_id)
                    update_stats("skills_bonus")
                
                reward_text = f"🎁 Возможность открыть суперспособность x{multiplier}{dopa_text_suffix}"
                await callback.message.edit_text(
                    f"🎰 Результат быстрых слотов: {' '.join(result)}\n\n"
                    f"🎉 3 галочки! Ты получил возможность открыть суперспособность x{multiplier}!{dopa_text_suffix}\n"
                    f"🎰 У тебя осталось {data['roulette_count']} круток.",
                    reply_markup=get_roulette_again_fast_keyboard()
                )

            elif symbol == "👻":
                spins_gained = 15 if "ghost_spins_plus5" in upgrades else 10
                total_spins_gained = spins_gained * multiplier
                
                data["roulette_count"] += total_spins_gained
                save_roulette_data(user_id, data)
                
                for _ in range(multiplier):
                    update_stats("+10")
                
                reward_text = f"🎁 +{total_spins_gained} Круток{dopa_text_suffix}"
                await callback.message.edit_text(
                    f"🎰 Результат быстрых слотов: {' '.join(result)}\n\n"
                    f"👻 3 призрака! +{total_spins_gained} круток!{dopa_text_suffix}\n"
                    f"🎰 У тебя осталось {data['roulette_count']} круток.",
                    reply_markup=get_roulette_again_fast_keyboard()
                )

            elif symbol == "💣":
                data["jopa_count"] = data.get("jopa_count", 0) + multiplier
                
                fire_bonus = 2 if "jopa_fire_2" in upgrades else 0
                total_fire_bonus = fire_bonus * multiplier
                if total_fire_bonus > 0:
                    data["fire_points"] = data.get("fire_points", 0) + total_fire_bonus
                    fire_text = f" (+{total_fire_bonus}🔥)"
                else:
                    fire_text = ""
                
                save_roulette_data(user_id, data)
                
                for _ in range(multiplier):
                    update_stats("JOPA")
                    
                reward_text = f"💣 Поджопник ^_^{fire_text}{dopa_text_suffix}"
                await callback.message.edit_text(
                    f"🎰 Результат быстрых слотов: {' '.join(result)}\n\n"
                    f"💣 Ты чертовски крут! Ты выиграл поджопник!{fire_text}{dopa_text_suffix}\n"
                    f"🎰 У тебя осталось {data['roulette_count']} круток.",
                    reply_markup=get_roulette_again_fast_keyboard()
                )

            elif symbol == "💋":
                reward_spins = 1 * multiplier
                
                if "kiss_kiss_kiss_fire" in upgrades:
                    data["fire_points"] = data.get("fire_points", 0) + 300 * multiplier
                    kiss_fire_text = f" и {300 * multiplier}🔥"
                else:
                    kiss_fire_text = ""
                    
                data["roulette_count"] += reward_spins
                save_roulette_data(user_id, data)
                
                for _ in range(multiplier):
                    update_stats("POCELUI")
                    
                reward_text = f"💋 Пранк — ничего не удалено (+{reward_spins} круток){dopa_text_suffix}"
                await callback.message.edit_text(
                    f"🎰 Результат быстрых слотов: {' '.join(result)}\n\n"
                    f"😈 Пранк! Ничего не удалено — всё в безопасности.\n"
                    f"🎁 В качестве компенсации: +{reward_spins} круток{kiss_fire_text}.{dopa_text_suffix}\n"
                    f"🎰 У тебя теперь {data['roulette_count']} круток.",
                    reply_markup=get_roulette_again_fast_keyboard()
                )

            if reward_text:
                append_roulette_history(int(user_id), reward_text)

        else:
            update_stats("nothing")
            fail_msg = (f"🎰 Результат быстрых слотов: {' '.join(result)}\n\n"
                       f"😿 Увы, ничего не выпало.\n"
                       f"🎰 У тебя осталось {data['roulette_count']} круток.")
            await callback.message.edit_text(fail_msg, reply_markup=get_roulette_again_fast_keyboard())

    except Exception:
        data["roulette_count"] = data.get("roulette_count", 0) + 1
        data["opened_today"] = max(0, data.get("opened_today", 1) - 1)
        data["total_opened"] = max(0, data.get("total_opened", 1) - 1)
        if is_dopa_active:
            data["fire_points"] += dopa_bet
        save_roulette_data(user_id, data)
        raise

# --- Обработка нажатия кнопки "Список последних 10 наград" ---
@router.callback_query(F.data == "show_history")
async def show_history(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    data = load_roulette_data(user_id)
    history = data.get("history", [])

    if not history:
        text = "📜 История наград пуста."
    else:
        text = "📜 Последние 10 наград:\n" + "\n".join(f"{idx+1}. {prize}" for idx, prize in enumerate(history))

    await callback.answer()
    await callback.message.edit_text(text, reply_markup=get_roulette_inline_keyboard_2())

@router.message(F.text == "🎰 Крутить казик")
async def show_roulette_status(message: Message):
    user_id = str(message.from_user.id)
    await send_roulette_status_message(message, user_id)

@router.callback_query(F.data == "roulette_button")
async def show_roulette_status(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    await send_roulette_status_message(callback.message, user_id)

@router.callback_query(F.data == "go_back_button")
async def go_back(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    await send_roulette_status_message(callback.message, user_id, edit=True)

# --- Магазин улучшений казика за 🔥 ---
@router.callback_query(F.data == "casino_upgrades_shop")
async def casino_upgrades_shop(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    data = load_roulette_data(user_id)
    
    fire_points = data.get("fire_points", 0)
    upgrades_raw = data.get("kazino_upgrades", {})
    upgrades = get_user_upgrades_dict(upgrades_raw)
    
    upgrades_text = ""
    if upgrades:
        upgrades_text = "<b>🎁 Твои улучшения:</b>\n"
        for upgrade_id, count in upgrades.items():
            upgrade_info = next((u for u in CASINO_UPGRADES_POOL if u["id"] == upgrade_id), None)
            if upgrade_info:
                upgrades_text += f"• {upgrade_info['name']} x{count}\n"
        upgrades_text += "\n"
    
    text = (
        f"🔥 <b>Магазин улучшений казика</b>\n\n"
        f"У тебя есть: <b>{fire_points} 🔥</b>\n\n"
        f"{upgrades_text}"
        f"Нажми кнопку ниже, чтобы получить случайное улучшение!\n"
        f"Цена: <b>100 🔥</b> за одно улучшение\n\n"
        f"<i>Улучшения выпадают случайно. Ты не узнаешь, что получишь, до покупки.</i>"
    )
    
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="🎲 Купить случайное улучшение (100🔥)", callback_data="buy_random_upgrade"),
    )
    builder.row(
        types.InlineKeyboardButton(text="↪️ Назад", callback_data="go_back_button"),
    )
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()

@router.callback_query(F.data == "buy_random_upgrade")
async def buy_random_upgrade(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    data = load_roulette_data(user_id)
    
    fire_points = data.get("fire_points", 0)
    upgrade_price = 100
    
    if fire_points < upgrade_price:
        await callback.answer(f"❌ Недостаточно 🔥! Нужно {upgrade_price}, у тебя {fire_points}", show_alert=True)
        return
    
    upgrade = get_random_upgrade(data)
    if not upgrade:
        await callback.answer("❌ Все доступные улучшения уже получены!", show_alert=True)
        return
    
    # Списываем огоньки
    data["fire_points"] = fire_points - upgrade_price
    
    # Применяем улучшение
    description, data = apply_upgrade(data, upgrade)
    save_roulette_data(user_id, data)
    
    append_roulette_history(int(user_id), f"🎁 Улучшение: {upgrade['name']}")
    
    rarity_emoji = {"common": "⚪", "rare": "🔵", "epic": "🟣", "legendary": "🟠"}.get(upgrade["rarity"], "⚪")
    
    text = (
        f"{rarity_emoji} <b>Получено улучшение!</b>\n\n"
        f"{description}\n\n"
        f"Осталось 🔥: {data['fire_points']}"
    )
    
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="🔥 Ещё раз (100🔥)", callback_data="buy_random_upgrade"),
    )
    builder.row(
        types.InlineKeyboardButton(text="↪️ Назад", callback_data="casino_upgrades_shop"),
    )
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()
