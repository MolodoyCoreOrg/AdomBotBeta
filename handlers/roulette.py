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

def get_available_upgrades(user_data: dict) -> list:
    """Возвращает список доступных улучшений с учетом уже полученных"""
    available = []
    upgrades = user_data.get("kazino_upgrades", {})
    
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
    upgrades = user_data.get("kazino_upgrades", {})
    upgrade_id = upgrade["id"]
    current_count = upgrades.get(upgrade_id, 0)
    new_count = current_count + 1
    upgrades[upgrade_id] = new_count
    user_data["kazino_upgrades"] = upgrades
    
    description = f"🎁 Получено улучшение: {upgrade['name']} ({upgrade['rarity']})"
    
    # Применяем эффекты улучшений
    if upgrade_id == "spin_per_hour_plus":
        # Это будет учитываться в roulette_increment_task
        pass
    elif upgrade_id == "max_spins_plus":
        # Увеличиваем MAX_SPINS для пользователя
        pass
    elif upgrade_id == "timer_reduce_10min":
        user_data["upgrade_timer_reduce"] = user_data.get("upgrade_timer_reduce", 0) + 1
    elif upgrade_id == "double_casino":
        user_data["has_double_casino"] = True
    elif upgrade_id == "fast_spin":
        user_data["has_fast_spin"] = True
    elif upgrade_id == "dopa_mechanic":
        # Механика ДОДЕПА доступна
        pass
    
    return description, user_data

# --- Inline клавиатура под сообщением рулетки ---
def get_roulette_inline_keyboard(user_data=None):
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="🎰 Крутить казик", callback_data="spin_roulette"),
    )
    # Добавляем кнопку магазина улучшений, если есть 🔥 или доступна механика ДОДЕПА
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
    # Проверяем, доступна ли быстрая прокрутка
    spin_callback = "spin_fast_roulette" if user_data and user_data.get("has_fast_spin") else "spin_roulette"
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

        cursor.execute("SELECT user_id, roulette_count, last_increment, notified_max FROM roulette_user")
        rows = cursor.fetchall()

        for user_id, roulette_count, last_increment, notified_max in rows:
            try:
                last_inc = datetime.datetime.fromisoformat(last_increment)
            except Exception:
                last_inc = now

            hours_passed = (now - last_inc).total_seconds() // 3600
            if hours_passed >= 1:
                if roulette_count < MAX_SPINS:
                    new_count = min(MAX_SPINS, roulette_count + INCREMENT * int(hours_passed))
                    cursor.execute(
                        "UPDATE roulette_user SET roulette_count = ?, last_increment = ? WHERE user_id = ?",
                        (new_count, now.isoformat(), user_id),
                    )

                    # уведомляем, если накопилось максимум
                    if new_count >= MAX_SPINS and not notified_max:
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
                    # если уже был максимум — сбрасываем дату
                    cursor.execute(
                        "UPDATE roulette_user SET last_increment = ? WHERE user_id = ?",
                        (now.isoformat(), user_id)
                    )

        conn.commit()
        conn.close()

        await asyncio.sleep(INTERVAL)  # ждём заданный интервал (например, 3600)







def seconds_until_next_increment(last_increment_iso: str) -> int:
    last_increment = datetime.datetime.fromisoformat(last_increment_iso)
    now = datetime.datetime.utcnow()
    seconds_passed = (now - last_increment).total_seconds()
    seconds_until_next = 3600 - (seconds_passed % 3600)
    return int(seconds_until_next)


async def send_roulette_status_message(target: Message | CallbackQuery, user_id: str, edit: bool = False):
    from database.db import connect
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("SELECT roulette_count, last_increment, total_opened, meow_count, meow_count_all, jopa_count, fire_points, kazino_upgrades FROM roulette_user WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return

    roulette_count, last_increment, total_opened, meow_count, meow_count_all, jopa_count, fire_points, kazino_upgrades_json = row
    kazino_upgrades = json.loads(kazino_upgrades_json) if kazino_upgrades_json else {}

    seconds_left = seconds_until_next_increment(last_increment)
    formatted_time_left = format_time_left(seconds_left)

    # Учитываем улучшения
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
        "Каждый час бот выдаёт 2 крутки. Максимум может быть 10."
    )

    user_data = {
        "fire_points": fire_points,
        "kazino_upgrades": kazino_upgrades
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
    with open(STATS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_stats(stats: dict):
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

def ensure_day(stats: dict, today: str):
    """Создаёт блок для дня, если его ещё нет"""
    if today not in stats["daily"]:
        stats["daily"][today] = {
            "roulette_opened": 0,
            "roulette_prizes": DEFAULT_PRIZES.copy()
        }

def update_stats(prize_key: str):
    stats = load_stats()
    today = datetime.datetime.now().strftime("%Y-%m-%d")

    # создаём блок для сегодняшнего дня
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
        now = datetime.datetime.utcnow()
        today_str = now.strftime("%Y-%m-%d")

        # --- Сброс дневного лимита ---
        if data["last_reset"] != today_str:
            data["opened_today"] = 0
            data["last_reset"] = today_str

        # --- Авто-прибавка рулеток ---
        last_increment = datetime.datetime.fromisoformat(data["last_increment"])
        hours_passed = (now - last_increment).total_seconds() // 3600
        if hours_passed >= 1:
            if data["roulette_count"] < MAX_SPINS:
                data["roulette_count"] = min(MAX_SPINS, data["roulette_count"] + 2 * int(hours_passed))
            data["last_increment"] = now.isoformat()

        if data["roulette_count"] == 0:
            await callback.answer("🎰 У тебя нет круток.", show_alert=True)
            return

        if data["opened_today"] >= 100000:
            await callback.answer("🎰 Ты уже открыл 100000 круток сегодня.", show_alert=True)
            return

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
                            reply_markup=get_roulette_SDVG_button()  # <<< всегда передаём клавиатуру
                        )
                        last_text = interim_text
                    except TelegramBadRequest as e:
                        if "message is not modified" not in str(e):
                            raise

                await asyncio.sleep(0.04 + (i / (rounds - 1)) * 0.46)  # от 0.04 до 0.5 сек

            # финальный результат
            final_text = " ".join(result)
            if final_text != last_text:
                await slot_msg.edit_text(final_text)

        try:
            await asyncio.wait_for(animate(), timeout=7.0)
        except asyncio.TimeoutError:
            await slot_msg.edit_text(" ".join(result))
        except Exception:
            # если во время анимации краш — вернем крутку пользователю
            data["roulette_count"] = data.get("roulette_count", 0) + 1
            data["opened_today"] = max(0, data.get("opened_today", 1) - 1)
            data["total_opened"] = max(0, data.get("total_opened", 1) - 1)
            save_roulette_data(user_id, data)
            raise


        # ждём гарантированного окончания
        await asyncio.sleep(0.6)


        stats = meow_stats.pop(int(user_id), None)
        if stats and stats.get("count", 0) > 0:
            data = load_roulette_data(user_id)

            stats_old = data.get("meow_count") or 0
            stats_old_all = data.get("meow_count_all") or 0
            stats_new = stats.get("count", 0)

            # сохраняем только если новое больше старого
            if stats_new > stats_old:
                data["meow_count"] = stats_new
                save_roulette_data(user_id, data)

            data["meow_count_all"] = stats_old_all + stats_new
            save_roulette_data(user_id, data)

            # удаляем все "Мяу"-сообщения
            for msg_id in stats["messages"]:
                try:
                    await slot_msg.bot.delete_message(callback.message.chat.id, msg_id)
                except Exception:
                    pass  # если сообщение уже удалено

            if result[0] == result[1] == result[2]:
                symbol = result[0]
                reward_text = None

                if symbol == "😹":
                    add_member_bonus(user_id)
                    update_stats("members_bonus")
                    reward_text = "🎁 Возможность открыть карточку участника"
                    await slot_msg.edit_text("🎉 3 кота! Ты получил возможность открыть карточку участника 😺\n"
                                            f"🎰 У тебя осталось {data['roulette_count']} круток.\n"
                                            f"😺 Вы мяукнули {stats['count']} раз", reply_markup=get_roulette_again_keyboard())

                elif symbol == "✅":
                    add_skill_bonus(user_id)
                    update_stats("skills_bonus")
                    reward_text = "🎁 Возможность открыть суперспособность"
                    await slot_msg.edit_text("🎉 3 галочки! Ты получил возможность открыть суперспособность ✅\n"
                                            f"🎰 У тебя осталось {data['roulette_count']} круток.\n"
                                            f"😺 Вы мяукнули {stats['count']} раз", reply_markup=get_roulette_again_keyboard())

                elif symbol == "👻":
                    data["roulette_count"] += 10
                    save_roulette_data(user_id, data)
                    update_stats("+10")
                    reward_text = "🎁 +10 Круток"
                    await slot_msg.edit_text("👻 3 призрака! +10 круток!\n"
                                            f"🎰 У тебя осталось {data['roulette_count']} круток.\n"
                                            f"😺 Вы мяукнули {stats['count']} раз", reply_markup=get_roulette_again_keyboard())
                    
                elif symbol == "💣":
                    # increment jopa_count in roulette_user
                    data["jopa_count"] = data.get("jopa_count", 0) + 1
                    
                    # Проверяем улучшение: выпадение поджопника дает 2🔥
                    upgrades = data.get("kazino_upgrades", {})
                    if "jopa_fire_2" in upgrades:
                        data["fire_points"] = data.get("fire_points", 0) + 2
                        fire_text = " (+2🔥)"
                    else:
                        fire_text = ""
                    
                    save_roulette_data(user_id, data)
                    update_stats("JOPA")
                    reward_text = f"💣 Поджопник ^_^{fire_text}"
                    await slot_msg.edit_text(f"💣 Ты чертовски крут! Ты выиграл поджопник!{fire_text}\n"
                                            f"🎰 У тебя осталось {data['roulette_count']} круток.\n"
                                            f"😺 Вы мяукнули {stats['count']} раз", reply_markup=get_roulette_again_keyboard(data))

                elif symbol == "💋":
                    # Пранк: ничего не удаляем, но сначала пугаем пользователя, затем успокаиваем и даём небольшую компенсацию
                    save_roulette_data(user_id, data)
                    update_stats("POCELUI")
                    reward_text = "💋 Пранк — ничего не удалено (+1 крутка)"

                    # Сначала пугающее сообщение (без reply_markup, чтобы внимание было на тексте)
                    await slot_msg.edit_text("💋 ТОТАЛЬНОЕ УНИЧТОЖЕНИЕ! ВСЕ ТВОИ КАРТЫ УДАЛЕНЫ!\n"
                                            f"🎰 У тебя осталось {data['roulette_count']} круток.\n"
                                            f"😺 Вы мяукнули {stats['count']} раз", reply_markup=None)

                    await asyncio.sleep(2.0)
                    data["roulette_count"] += 1
                    save_roulette_data(user_id, data)
                    await slot_msg.edit_text("😈 Пранк! Ничего не удалено — всё в безопасности.\n"
                                            f"🎁 В качестве компенсации: +1 крутка.\n"
                                            f"🎰 У тебя теперь {data['roulette_count']} круток.\n"
                                            f"😺 Вы мяукнули {stats['count']} раз", reply_markup=get_roulette_again_keyboard())

                    # Добавляем награду в историю
                if reward_text:
                    append_roulette_history(int(user_id), reward_text)

            else:
                update_stats("nothing")
                fail_msg = (f"😿 Увы, ничего не выпало.\nУ тебя было: {' '.join(result)}\n"
                        f"🎰 У тебя осталось {data['roulette_count']} круток.\n"
                        f"😺 Вы мяукнули {stats['count']} раз")
                await slot_msg.edit_text(fail_msg, reply_markup=get_roulette_again_keyboard())

        else:            
            if result[0] == result[1] == result[2]:
                symbol = result[0]
                reward_text = None

                if symbol == "😹":
                    add_member_bonus(user_id)
                    update_stats("members_bonus")
                    reward_text = "🎁 Возможность открыть карточку участника"
                    await slot_msg.edit_text("🎉 3 кота! Ты получил возможность открыть карточку участника 😺\n"
                                            f"🎰 У тебя осталось {data['roulette_count']} круток.", reply_markup=get_roulette_again_keyboard())

                elif symbol == "✅":
                    add_skill_bonus(user_id)
                    update_stats("skills_bonus")
                    reward_text = "🎁 Возможность открыть суперспособность"
                    await slot_msg.edit_text("🎉 3 галочки! Ты получил возможность открыть суперспособность ✅\n"
                                            f"🎰 У тебя осталось {data['roulette_count']} круток.", reply_markup=get_roulette_again_keyboard())

                elif symbol == "👻":
                    data["roulette_count"] += 10
                    save_roulette_data(user_id, data)
                    update_stats("+10")
                    reward_text = "🎁 +10 Круток"
                    await slot_msg.edit_text("👻 3 призрака! +10 круток!\n"
                                            f"🎰 У тебя осталось {data['roulette_count']} круток.", reply_markup=get_roulette_again_keyboard())
                    
                elif symbol == "💣":
                    data["jopa_count"] = data.get("jopa_count", 0) + 1
        
                    # Проверяем улучшение: выпадение поджопника дает 2🔥
                    upgrades = data.get("kazino_upgrades", {})
                    if "jopa_fire_2" in upgrades:
                        data["fire_points"] = data.get("fire_points", 0) + 2
                        fire_text = " (+2🔥)"
                    else:
                        fire_text = ""
        
                    save_roulette_data(user_id, data)
                    update_stats("JOPA")
                    fire_text = " (+2🔥)" if "jopa_fire_2" in upgrades else ""
                    await slot_msg.edit_text(f"💣 Ты чертовски крут! Ты выиграл поджопник!{fire_text}\n"
                                            f"🎰 У тебя осталось {data['roulette_count']} круток.", reply_markup=get_roulette_again_keyboard(data))

                elif symbol == "💋":
                    # Пранк: ничего не удаляем, но сначала пугаем пользователя, затем успокаиваем и даём небольшую компенсацию
                    save_roulette_data(user_id, data)
                    update_stats("POCELUI")
                    reward_text = "💋 Пранк — ничего не удалено (+1 крутка)"

                    # Сначала пугающее сообщение (без reply_markup, чтобы внимание было на тексте)
                    await slot_msg.edit_text("💋 ТОТАЛЬНОЕ УНИЧТОЖЕНИЕ! ВСЕ ТВОИ КАРТЫ УДАЛЕНЫ!\n"
                                            f"🎰 У тебя осталось {data['roulette_count']} круток.", reply_markup=None)

                    await asyncio.sleep(2.0)
                    data["roulette_count"] += 1
                    save_roulette_data(user_id, data)
                    await slot_msg.edit_text("😈 Пранк! Ничего не удалено — всё в безопасности.\n"
                                            f"🎁 В качестве компенсации: +1 крутка.\n"
                                            f"🎰 У тебя теперь {data['roulette_count']} круток.", reply_markup=get_roulette_again_keyboard())

                # Добавляем награду в истории
                if reward_text:
                    append_roulette_history(int(user_id), reward_text)

            else:
                update_stats("nothing")
                fail_msg = (f"😿 Увы, ничего не выпало.\nУ тебя было: {' '.join(result)}\n"
                        f"🎰 У тебя осталось {data['roulette_count']} круток.")
                await slot_msg.edit_text(fail_msg, reply_markup=get_roulette_again_keyboard())

    finally:
        # снимаем блокировку
        active_spins.pop(user_id, None)



@router.callback_query(F.data == "SDVG_meow")
async def sdvg_meow(callback: CallbackQuery):
    user_id = callback.from_user.id
    msg = await callback.message.answer("Мяу ^_^")

    # инициализируем, если первый раз
    if user_id not in meow_stats:
        meow_stats[user_id] = {"count": 0, "messages": []}

    # увеличиваем счётчик и запоминаем сообщение
    meow_stats[user_id]["count"] += 1
    meow_stats[user_id]["messages"].append(msg.message_id)

    await callback.answer()  # чтобы кнопка не "висела"








# --- Быстрая верcия крутилки: мгновенно показываем результат (без анимации) ---
@router.callback_query(F.data == "spin_fast_roulette")
async def spin_fast_roulette(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    data = load_roulette_data(user_id)

    now = datetime.datetime.utcnow()
    today_str = now.strftime("%Y-%m-%d")

    if data["last_reset"] != today_str:
        data["opened_today"] = 0
        data["last_reset"] = today_str

    last_increment = datetime.datetime.fromisoformat(data["last_increment"])
    hours_passed = (now - last_increment).total_seconds() // 3600
    if hours_passed >= 1:
        if data["roulette_count"] < MAX_SPINS:
            data["roulette_count"] = min(MAX_SPINS, data["roulette_count"] + 2 * int(hours_passed))
        data["last_increment"] = now.isoformat()

    if data["roulette_count"] == 0:
        await callback.answer("🎰 У тебя нет круток.", show_alert=True)
        return

    if data.get("opened_today", 0) >= 100000:
        await callback.answer("🎰 Ты уже открыл 100000 круток сегодня.", show_alert=True)
        return

    # Снимаем крутку и сохраняем состояние
    data["roulette_count"] -= 1
    data["opened_today"] = data.get("opened_today", 0) + 1
    data["total_opened"] = data.get("total_opened", 0) + 1
    data["notified_max"] = False
    save_roulette_data(user_id, data)

    # Моментальный выбор результата
    symbols, weights = _get_symbols_and_weights()
    try:
        result = random.choices(symbols, weights=weights, k=3)

        if result[0] == result[1] == result[2]:
            symbol = result[0]
            reward_text = None

            if symbol == "😹":
                add_member_bonus(user_id)
                reward_text = "🎁 Возможность открыть карточку участника"
                await callback.message.edit_text(
                    "🎉 3 кота! Ты получил возможность открыть карточку участника 😺\n"
                    f"🎰 У тебя осталось {data['roulette_count']} круток.",
                    reply_markup=get_roulette_again_fast_keyboard()
                )

            elif symbol == "✅":
                add_skill_bonus(user_id)
                reward_text = "🎁 Возможность открыть суперспособность"
                await callback.message.edit_text(
                    "🎉 3 галочки! Ты получил возможность открыть суперспособность ✅\n"
                    f"🎰 У тебя осталось {data['roulette_count']} круток.",
                    reply_markup=get_roulette_again_fast_keyboard()
                )

            elif symbol == "👻":
                data["roulette_count"] += 10
                save_roulette_data(user_id, data)
                reward_text = "🎁 +10 Круток"
                await callback.message.edit_text(
                    "👻 3 призрака! +10 круток!\n"
                    f"🎰 У тебя осталось {data['roulette_count']} круток.",
                    reply_markup=get_roulette_again_fast_keyboard()
                )

            elif symbol == "💣":
                    # increment jopa_count in roulette_user
                    data["jopa_count"] = data.get("jopa_count", 0) + 1
                    
                    # Проверяем улучшение: выпадение поджопника дает 2🔥
                    upgrades = data.get("kazino_upgrades", {})
                    if "jopa_fire_2" in upgrades:
                        data["fire_points"] = data.get("fire_points", 0) + 2
                        fire_text = " (+2🔥)"
                    else:
                        fire_text = ""
                    
                    save_roulette_data(user_id, data)
                    update_stats("JOPA")
                    reward_text = f"💣 Поджопник ^_^{fire_text}"
                    await slot_msg.edit_text(f"💣 Ты чертовски крут! Ты выиграл поджопник!{fire_text}\n"
                                            f"🎰 У тебя осталось {data['roulette_count']} круток.\n"
                                            f"😺 Вы мяукнули {stats['count']} раз", reply_markup=get_roulette_again_keyboard(data))

            elif symbol == "💋":
                # Для быстрой версии пропускаем драму — сразу даём компенсацию
                data["roulette_count"] += 1
                save_roulette_data(user_id, data)
                reward_text = "💋 Пранк — ничего не удалено (+1 крутка)"
                await callback.message.edit_text(
                    "😈 Пранк! Ничего не удалено — всё в безопасности.\n"
                    f"🎁 В качестве компенсации: +1 крутка.\n"
                    f"🎰 У тебя теперь {data['roulette_count']} круток.",
                    reply_markup=get_roulette_again_fast_keyboard()
                )

            if reward_text:
                append_roulette_history(int(user_id), reward_text)

        else:
            fail_msg = (f"😿 Увы, ничего не выпало.\nУ тебя было: {' '.join(result)}\n"
                       f"🎰 У тебя осталось {data['roulette_count']} круток.")
            await callback.message.edit_text(fail_msg, reply_markup=get_roulette_again_fast_keyboard())

    except Exception:
        # Откатываем списание при ошибке
        data["roulette_count"] = data.get("roulette_count", 0) + 1
        data["opened_today"] = max(0, data.get("opened_today", 1) - 1)
        data["total_opened"] = max(0, data.get("total_opened", 1) - 1)
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

    await callback.answer() # закрыть "часики"
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
    upgrades = data.get("kazino_upgrades", {})
    
    # Формируем текст с текущими улучшениями
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
    
    # Выбираем случайное улучшение
    upgrade = get_random_upgrade(data)
    if not upgrade:
        await callback.answer("❌ Все доступные улучшения уже получены!", show_alert=True)
        return
    
    # Списываем огоньки
    data["fire_points"] = fire_points - upgrade_price
    
    # Применяем улучшение
    description, data = apply_upgrade(data, upgrade)
    save_roulette_data(user_id, data)
    
    # Добавляем в историю
    append_roulette_history(int(user_id), f"🎁 Улучшение: {upgrade['name']}")
    
    # Показываем результат
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