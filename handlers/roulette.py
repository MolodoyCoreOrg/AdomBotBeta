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

active_spins = {}

# --- Улучшения казика за 🔥 ---
CASINO_UPGRADES_POOL = [
    {"id": "spin_per_hour_plus", "name": "+1 крутка в час", "rarity": "common", "weight": 15, "max_count": None},
    {"id": "max_spins_plus", "name": "+1 к максимальному накапливаемому количеству круток", "rarity": "common", "weight": 15, "max_count": None},
    {"id": "jopa_fire_2", "name": "Выпадение поджопника дает 2🔥", "rarity": "common", "weight": 12, "max_count": None},
    {"id": "ghost_spins_plus5", "name": "Выпадение призраков дает на 5 больше круток", "rarity": "common", "weight": 12, "max_count": None},
    {"id": "meow_fire", "name": "При мяуканьи больше 5 раз дается 1🔥", "rarity": "common", "weight": 10, "max_count": None},
    {"id": "kiss_kiss_kiss_fire", "name": "При выпадении 💋💋💋 дается 300 🔥", "rarity": "common", "weight": 6, "max_count": None},
    {"id": "dopa_mechanic", "name": "Открыта механика ДОДЕПА - ставьте 🔥 и получайте x10 при любой комбинации", "rarity": "common", "weight": 10, "max_count": None},
    {"id": "timer_reduce_10min", "name": "Минус 10 минут к таймеру пополнения круток", "rarity": "rare", "weight": 20, "max_count": 3},
    {"id": "double_casino", "name": "Можно крутить сразу два казика", "rarity": "epic", "weight": 7, "max_count": 1},
    {"id": "fast_spin", "name": "Появляется возможность быстрой прокрутки", "rarity": "legendary", "weight": 3, "max_count": 1},
]

def get_available_upgrades(user_data: dict) -> list:
    """Возвращает список доступных улучшений с учетом уже полученных"""
    available = []
    upgrades = user_data.get("kazino_upgrades", {})
    
    for upgrade in CASINO_UPGRADES_POOL:
        current_count = upgrades.get(upgrade["id"], 0)
        max_count = upgrade.get("max_count")
        
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
    upgrades = user_data.get("kazino_upgrades", {})
    upgrade_id = upgrade["id"]
    current_count = upgrades.get(upgrade_id, 0)
    upgrades[upgrade_id] = current_count + 1
    user_data["kazino_upgrades"] = upgrades
    
    description = f"🎁 Получено улучшение: {upgrade['name']} ({upgrade['rarity']})"
    
    if upgrade_id == "timer_reduce_10min":
        user_data["upgrade_timer_reduce"] = user_data.get("upgrade_timer_reduce", 0) + 1
    elif upgrade_id == "double_casino":
        user_data["has_double_casino"] = True
    elif upgrade_id == "fast_spin":
        user_data["has_fast_spin"] = True
    
    return description, user_data

# --- Inline клавиатура под сообщением рулетки ---
def get_roulette_inline_keyboard(user_data=None):
    builder = InlineKeyboardBuilder()
    
    spin_callback = "spin_fast_roulette" if user_data and user_data.get("has_fast_spin") else "spin_roulette"
    
    builder.row(
        types.InlineKeyboardButton(text="🎰 Крутить казик", callback_data=spin_callback),
    )
    if user_data:
        fire_points = user_data.get("fire_points", 0)
        upgrades = user_data.get("kazino_upgrades", {})
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
    spin_callback = "spin_fast_roulette" if user_data and user_data.get("has_fast_spin") else "spin_roulette"
    builder.row(
        types.InlineKeyboardButton(text="🎰 Крутить ещё раз", callback_data=spin_callback)
    )
    builder.row(
        types.InlineKeyboardButton(text="Назад", callback_data="go_back_button"),
    )
    return builder.as_markup()

def get_roulette_again_fast_keyboard(user_data=None):
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

# объединённая задача: инкремент + уведомление с учетом улучшений
async def roulette_increment_task():
    from database.db import connect
    while True:
        now = datetime.datetime.utcnow()
        conn = connect()
        cursor = conn.cursor()

        cursor.execute("SELECT user_id, roulette_count, last_increment, notified_max, kazino_upgrades FROM roulette_user")
        rows = cursor.fetchall()

        for user_id, roulette_count, last_increment, notified_max, kazino_upgrades_json in rows:
            upgrades = json.loads(kazino_upgrades_json) if kazino_upgrades_json else {}
            
            # Применяем эффекты улучшений
            max_spins = 10 + upgrades.get("max_spins_plus", 0)
            increment = 2 + upgrades.get("spin_per_hour_plus", 0)
            interval = 3600 - (upgrades.get("timer_reduce_10min", 0) * 600)
            if interval < 600: 
                interval = 600

            try:
                last_inc = datetime.datetime.fromisoformat(last_increment)
            except Exception:
                last_inc = now

            intervals_passed = (now - last_inc).total_seconds() // interval
            
            if intervals_passed >= 1:
                if roulette_count < max_spins:
                    new_count = min(max_spins, roulette_count + increment * int(intervals_passed))
                    cursor.execute(
                        "UPDATE roulette_user SET roulette_count = ?, last_increment = ? WHERE user_id = ?",
                        (new_count, now.isoformat(), user_id),
                    )

                    if new_count >= max_spins and not notified_max:
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
                    cursor.execute(
                        "UPDATE roulette_user SET last_increment = ? WHERE user_id = ?",
                        (now.isoformat(), user_id)
                    )

        conn.commit()
        conn.close()

        await asyncio.sleep(600)  # Спим меньше, чтобы чаще проверять таймеры, если у кого-то он сокращен


def seconds_until_next_increment(last_increment_iso: str, interval: int = 3600) -> int:
    last_increment = datetime.datetime.fromisoformat(last_increment_iso)
    now = datetime.datetime.utcnow()
    seconds_passed = (now - last_increment).total_seconds()
    return int(interval - (seconds_passed % interval))

async def send_roulette_status_message(target: Message | CallbackQuery, user_id: str, edit: bool = False):
    from database.db import connect
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("SELECT roulette_count, last_increment, total_opened, meow_count, meow_count_all, jopa_count, fire_points, kazino_upgrades, has_fast_spin FROM roulette_user WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return

    roulette_count, last_increment, total_opened, meow_count, meow_count_all, jopa_count, fire_points, kazino_upgrades_json, has_fast_spin = row
    kazino_upgrades = json.loads(kazino_upgrades_json) if kazino_upgrades_json else {}

    # Применяем эффекты улучшений
    max_spins = 10 + kazino_upgrades.get("max_spins_plus", 0)
    increment = 2 + kazino_upgrades.get("spin_per_hour_plus", 0)
    interval = 3600 - (kazino_upgrades.get("timer_reduce_10min", 0) * 600)
    if interval < 600:
        interval = 600

    seconds_left = seconds_until_next_increment(last_increment, interval)
    formatted_time_left = format_time_left(seconds_left)

    upgrades_count = len(kazino_upgrades)
    fire_text = f"🔥 Огоньки: {fire_points}\n" if fire_points > 0 else ""
    upgrades_text = f"🎁 Улучшений: {upgrades_count}\n" if upgrades_count > 0 else ""

    text = (
        f"🎰 У тебя есть {roulette_count} круток.\n"
        f"⏳ До следующей крутки: <b>{formatted_time_left}</b>\n"
        f"📊 Всего круток открыто: {total_opened}\n\n"
        f"{fire_text}"
        f"{upgrades_text}"
        f"😹 Мяу ^_^\n"
        f"Наибольший стрик : {meow_count}\n"
        f"Всего мяуканий: {meow_count_all}\n\n"
        f"💣 Всего поджопников: {jopa_count}\n\n"
        f"Каждые {interval//60} мин. бот выдаёт {increment} круток. Максимум может быть {max_spins}."
    )

    user_data = {
        "fire_points": fire_points,
        "kazino_upgrades": kazino_upgrades,
        "has_fast_spin": bool(has_fast_spin)
    }

    if isinstance(target, CallbackQuery):
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
    with open(STATS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_stats(stats: dict):
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

def ensure_day(stats: dict, today: str):
    if today not in stats["daily"]:
        stats["daily"][today] = {
            "roulette_opened": 0,
            "roulette_prizes": DEFAULT_PRIZES.copy()
        }

def update_stats(prize_key: str):
    stats = load_stats()
    today = datetime.datetime.now().strftime("%Y-%m-%d")

    ensure_day(stats, today)

    stats["global"]["roulette_opened"] += 1
    if prize_key in stats["global"]["roulette_prizes"]:
        stats["global"]["roulette_prizes"][prize_key] += 1

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

def _get_symbols_and_weights():
    symbols = list(SLOT_CHANCES.keys())
    weights = [max(0.0, float(SLOT_CHANCES[s])) for s in symbols]
    if sum(weights) == 0:
        weights = [1.0] * len(symbols)
    return symbols, weights

meow_stats = {}

# --- Обработка нажатия кнопки "Крутить рулетку" ---
@router.callback_query(F.data == "spin_roulette")
async def spin_roulette(callback: CallbackQuery):
    user_id = str(callback.from_user.id)

    if active_spins.get(user_id):
        await callback.answer("⏳ Подожди, текущая крутка ещё идёт.", show_alert=True)
        return
    active_spins[user_id] = True

    try:
        data = load_roulette_data(user_id)
        upgrades = data.get("kazino_upgrades", {})
        now = datetime.datetime.utcnow()
        today_str = now.strftime("%Y-%m-%d")
        
        # Характеристики казика с учетом апгрейдов
        max_spins = 10 + upgrades.get("max_spins_plus", 0)
        increment = 2 + upgrades.get("spin_per_hour_plus", 0)
        interval = 3600 - (upgrades.get("timer_reduce_10min", 0) * 600)
        if interval < 600:
            interval = 600

        # --- Сброс дневного лимита ---
        if data["last_reset"] != today_str:
            data["opened_today"] = 0
            data["last_reset"] = today_str

        # --- Авто-прибавка рулеток с новыми правилами ---
        last_increment = datetime.datetime.fromisoformat(data["last_increment"])
        intervals_passed = (now - last_increment).total_seconds() // interval
        if intervals_passed >= 1:
            if data["roulette_count"] < max_spins:
                data["roulette_count"] = min(max_spins, data["roulette_count"] + increment * int(intervals_passed))
            data["last_increment"] = now.isoformat()

        if data["roulette_count"] <= 0:
            await callback.answer("🎰 У тебя нет круток.", show_alert=True)
            return

        if data.get("opened_today", 0) >= 100000:
            await callback.answer("🎰 Ты уже открыл 100000 круток сегодня.", show_alert=True)
            return

        # --- Уменьшаем рулетку ---
        data["roulette_count"] -= 1
        data["opened_today"] = data.get("opened_today", 0) + 1
        data["total_opened"] = data.get("total_opened", 0) + 1
        data["notified_max"] = False
        save_roulette_data(user_id, data)

        # --- Сообщение со слотами ---
        await safe_delete(callback)
        slot_msg = await callback.message.answer("🎰 Крутим...\n⬛ ⬛ ⬛", reply_markup=get_roulette_SDVG_button())

        # --- Анимация ---
        symbols, weights = _get_symbols_and_weights()
        result = random.choices(symbols, weights=weights, k=3)

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
            data["roulette_count"] = data.get("roulette_count", 0) + 1
            data["opened_today"] = max(0, data.get("opened_today", 1) - 1)
            data["total_opened"] = max(0, data.get("total_opened", 1) - 1)
            save_roulette_data(user_id, data)
            raise

        await asyncio.sleep(0.6)

        # Обновляем инфу (могла измениться во время анимации)
        data = load_roulette_data(user_id)
        upgrades = data.get("kazino_upgrades", {})
        
        # --- Подсчет мяуканий (Mяу апгрейд) ---
        stats = meow_stats.pop(int(user_id), None)
        meow_str = ""
        if stats and stats.get("count", 0) > 0:
            stats_old = data.get("meow_count", 0)
            stats_old_all = data.get("meow_count_all", 0)
            stats_new = stats.get("count", 0)

            if stats_new > stats_old:
                data["meow_count"] = stats_new
            data["meow_count_all"] = stats_old_all + stats_new
            
            # Апгрейд meow_fire
            meow_fire_bonus = 0
            if stats_new > 5 and "meow_fire" in upgrades:
                meow_fire_bonus = 1 * upgrades["meow_fire"]
                data["fire_points"] = data.get("fire_points", 0) + meow_fire_bonus
                
            save_roulette_data(user_id, data)

            for msg_id in stats["messages"]:
                try:
                    await slot_msg.bot.delete_message(callback.message.chat.id, msg_id)
                except Exception:
                    pass

            meow_str = f"\n😺 Вы мяукнули {stats_new} раз"
            if meow_fire_bonus > 0:
                meow_str += f" (+{meow_fire_bonus}🔥 за улучшение)"

        # --- Проверка результата ---
        if result[0] == result[1] == result[2]:
            symbol = result[0]
            reward_text = None

            if symbol == "😹":
                add_member_bonus(user_id)
                update_stats("members_bonus")
                reward_text = "🎁 Возможность открыть карточку участника"
                await slot_msg.edit_text(f"🎉 3 кота! Ты получил возможность открыть карточку участника 😺\n🎰 У тебя осталось {data['roulette_count']} круток.{meow_str}", reply_markup=get_roulette_again_keyboard(data))

            elif symbol == "✅":
                add_skill_bonus(user_id)
                update_stats("skills_bonus")
                reward_text = "🎁 Возможность открыть суперспособность"
                await slot_msg.edit_text(f"🎉 3 галочки! Ты получил возможность открыть суперспособность ✅\n🎰 У тебя осталось {data['roulette_count']} круток.{meow_str}", reply_markup=get_roulette_again_keyboard(data))

            elif symbol == "👻":
                # Апгрейд ghost_spins_plus5
                base_spins = 10
                bonus_spins = 5 * upgrades.get("ghost_spins_plus5", 0)
                total_spins = base_spins + bonus_spins
                
                data["roulette_count"] += total_spins
                save_roulette_data(user_id, data)
                update_stats("+10")
                
                reward_text = f"🎁 +{total_spins} Круток"
                ghost_str = f" (+{bonus_spins} от улучшения)" if bonus_spins > 0 else ""
                
                await slot_msg.edit_text(f"👻 3 призрака! +{total_spins} круток!{ghost_str}\n🎰 У тебя осталось {data['roulette_count']} круток.{meow_str}", reply_markup=get_roulette_again_keyboard(data))
                
            elif symbol == "💣":
                data["jopa_count"] = data.get("jopa_count", 0) + 1
                
                # Апгрейд jopa_fire_2
                fire_bonus = 2 * upgrades.get("jopa_fire_2", 0)
                fire_text = ""
                if fire_bonus > 0:
                    data["fire_points"] = data.get("fire_points", 0) + fire_bonus
                    fire_text = f" (+{fire_bonus}🔥)"
                
                save_roulette_data(user_id, data)
                update_stats("JOPA")
                reward_text = f"💣 Поджопник ^_^{fire_text}"
                await slot_msg.edit_text(f"💣 Ты чертовски крут! Ты выиграл поджопник!{fire_text}\n🎰 У тебя осталось {data['roulette_count']} круток.{meow_str}", reply_markup=get_roulette_again_keyboard(data))

            elif symbol == "💋":
                # Апгрейд kiss_kiss_kiss_fire (ТОТ САМЫЙ БОНУС НА ОГОНЬКИ!)
                fire_bonus = 300 * upgrades.get("kiss_kiss_kiss_fire", 0)
                fire_text = ""
                if fire_bonus > 0:
                    data["fire_points"] = data.get("fire_points", 0) + fire_bonus
                    fire_text = f"\n🔥 Бонус улучшения: +{fire_bonus} огоньков!"

                save_roulette_data(user_id, data)
                update_stats("POCELUI")
                reward_text = f"💋 Пранк — ничего не удалено (+1 крутка){fire_text}"

                await slot_msg.edit_text(f"💋 ТОТАЛЬНОЕ УНИЧТОЖЕНИЕ! ВСЕ ТВОИ КАРТЫ УДАЛЕНЫ!\n🎰 У тебя осталось {data['roulette_count']} круток.{meow_str}", reply_markup=None)

                await asyncio.sleep(2.0)
                
                data["roulette_count"] += 1
                save_roulette_data(user_id, data)
                await slot_msg.edit_text(f"😈 Пранк! Ничего не удалено — всё в безопасности.\n🎁 В качестве компенсации: +1 крутка.{fire_text}\n🎰 У тебя теперь {data['roulette_count']} круток.{meow_str}", reply_markup=get_roulette_again_keyboard(data))

            if reward_text:
                append_roulette_history(int(user_id), reward_text)

        else:
            update_stats("nothing")
            fail_msg = f"😿 Увы, ничего не выпало.\nУ тебя было: {' '.join(result)}\n🎰 У тебя осталось {data['roulette_count']} круток.{meow_str}"
            await slot_msg.edit_text(fail_msg, reply_markup=get_roulette_again_keyboard(data))

    finally:
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

# --- Быстрая верcия крутилки: мгновенно показываем результат ---
@router.callback_query(F.data == "spin_fast_roulette")
async def spin_fast_roulette(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    data = load_roulette_data(user_id)
    upgrades = data.get("kazino_upgrades", {})

    now = datetime.datetime.utcnow()
    today_str = now.strftime("%Y-%m-%d")

    max_spins = 10 + upgrades.get("max_spins_plus", 0)
    increment = 2 + upgrades.get("spin_per_hour_plus", 0)
    interval = 3600 - (upgrades.get("timer_reduce_10min", 0) * 600)
    if interval < 600:
        interval = 600

    if data["last_reset"] != today_str:
        data["opened_today"] = 0
        data["last_reset"] = today_str

    last_increment = datetime.datetime.fromisoformat(data["last_increment"])
    intervals_passed = (now - last_increment).total_seconds() // interval
    if intervals_passed >= 1:
        if data["roulette_count"] < max_spins:
            data["roulette_count"] = min(max_spins, data["roulette_count"] + increment * int(intervals_passed))
        data["last_increment"] = now.isoformat()

    if data["roulette_count"] <= 0:
        await callback.answer("🎰 У тебя нет круток.", show_alert=True)
        return

    if data.get("opened_today", 0) >= 100000:
        await callback.answer("🎰 Ты уже открыл 100000 круток сегодня.", show_alert=True)
        return

    data["roulette_count"] -= 1
    data["opened_today"] = data.get("opened_today", 0) + 1
    data["total_opened"] = data.get("total_opened", 0) + 1
    data["notified_max"] = False
    save_roulette_data(user_id, data)

    symbols, weights = _get_symbols_and_weights()
    try:
        result = random.choices(symbols, weights=weights, k=3)

        if result[0] == result[1] == result[2]:
            symbol = result[0]
            reward_text = None

            if symbol == "😹":
                add_member_bonus(user_id)
                reward_text = "🎁 Возможность открыть карточку участника"
                await callback.message.edit_text(f"🎉 3 кота! Ты получил возможность открыть карточку участника 😺\n🎰 У тебя осталось {data['roulette_count']} круток.", reply_markup=get_roulette_again_fast_keyboard(data))

            elif symbol == "✅":
                add_skill_bonus(user_id)
                reward_text = "🎁 Возможность открыть суперспособность"
                await callback.message.edit_text(f"🎉 3 галочки! Ты получил возможность открыть суперспособность ✅\n🎰 У тебя осталось {data['roulette_count']} круток.", reply_markup=get_roulette_again_fast_keyboard(data))

            elif symbol == "👻":
                # Апгрейд на призраков
                base_spins = 10
                bonus_spins = 5 * upgrades.get("ghost_spins_plus5", 0)
                total_spins = base_spins + bonus_spins
                
                data["roulette_count"] += total_spins
                save_roulette_data(user_id, data)
                
                reward_text = f"🎁 +{total_spins} Круток"
                ghost_str = f" (+{bonus_spins} от улучшения)" if bonus_spins > 0 else ""
                
                await callback.message.edit_text(f"👻 3 призрака! +{total_spins} круток!{ghost_str}\n🎰 У тебя осталось {data['roulette_count']} круток.", reply_markup=get_roulette_again_fast_keyboard(data))

            elif symbol == "💣":
                data["jopa_count"] = data.get("jopa_count", 0) + 1
                fire_bonus = 2 * upgrades.get("jopa_fire_2", 0)
                fire_text = ""
                if fire_bonus > 0:
                    data["fire_points"] = data.get("fire_points", 0) + fire_bonus
                    fire_text = f" (+{fire_bonus}🔥)"
                
                save_roulette_data(user_id, data)
                update_stats("JOPA")
                reward_text = f"💣 Поджопник ^_^{fire_text}"
                await callback.message.edit_text(f"💣 Ты чертовски крут! Ты выиграл поджопник!{fire_text}\n🎰 У тебя осталось {data['roulette_count']} круток.", reply_markup=get_roulette_again_fast_keyboard(data))

            elif symbol == "💋":
                # Апгрейд на поцелуи (+300🔥)
                fire_bonus = 300 * upgrades.get("kiss_kiss_kiss_fire", 0)
                fire_text = ""
                if fire_bonus > 0:
                    data["fire_points"] = data.get("fire_points", 0) + fire_bonus
                    fire_text = f"\n🔥 Бонус улучшения: +{fire_bonus} огоньков!"
                
                data["roulette_count"] += 1
                save_roulette_data(user_id, data)
                reward_text = f"💋 Пранк — ничего не удалено (+1 крутка){fire_text}"
                await callback.message.edit_text(f"😈 Пранк! Ничего не удалено — всё в безопасности.\n🎁 В качестве компенсации: +1 крутка.{fire_text}\n🎰 У тебя теперь {data['roulette_count']} круток.", reply_markup=get_roulette_again_fast_keyboard(data))

            if reward_text:
                append_roulette_history(int(user_id), reward_text)

        else:
            fail_msg = f"😿 Увы, ничего не выпало.\nУ тебя было: {' '.join(result)}\n🎰 У тебя осталось {data['roulette_count']} круток."
            await callback.message.edit_text(fail_msg, reply_markup=get_roulette_again_fast_keyboard(data))

    except Exception:
        data["roulette_count"] = data.get("roulette_count", 0) + 1
        data["opened_today"] = max(0, data.get("opened_today", 1) - 1)
        data["total_opened"] = max(0, data.get("total_opened", 1) - 1)
        save_roulette_data(user_id, data)
        raise

# --- Обработка списка наград и магазина ---
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
async def trigger_roulette_status_msg(message: Message):
    user_id = str(message.from_user.id)
    await send_roulette_status_message(message, user_id)

@router.callback_query(F.data == "roulette_button")
async def trigger_roulette_status_cb(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    await send_roulette_status_message(callback, user_id)

@router.callback_query(F.data == "go_back_button")
async def go_back(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    await send_roulette_status_message(callback, user_id, edit=True)

# --- Магазин улучшений казика за 🔥 ---
@router.callback_query(F.data == "casino_upgrades_shop")
async def casino_upgrades_shop(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    data = load_roulette_data(user_id)
    
    fire_points = data.get("fire_points", 0)
    upgrades = data.get("kazino_upgrades", {})
    
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
    
    data["fire_points"] = fire_points - upgrade_price
    
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