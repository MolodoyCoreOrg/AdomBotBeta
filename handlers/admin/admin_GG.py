import os, sqlite3, asyncio, random, json, datetime, uuid
from datetime import date

from aiogram import types, Router, F, Bot
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from handlers.notify import send_reminder
from utils.config import ADMINS_LIST
from handlers.cards_handler.members import set_check_member_enabled, load_timers
from handlers.cards_handler.skills import set_check_skill_enabled, load_timers
from database.db import add_member_bonus, add_skill_bonus, load_roulette_data, save_roulette_data, append_roulette_history, add_balance, get_all_user_ids, find_user_by_username
from handlers.donate import get_random_word_for_user, save_donation

router = Router()

DB_PATH = "database/users.db"

# Задержка между отправками в массовых рассылках (2 секунды = 30 сообщений/мин)
BROADCAST_DELAY = 4

def connect():
    return sqlite3.connect(DB_PATH)


# === RELOAD BOT ===

@router.message(Command("reload"))
async def reload_bot(message: Message, bot: Bot):
    if message.from_user.id not in ADMINS_LIST:
        await message.answer("❌ У вас нет доступа к этой команде.")
        return

    await message.answer("🔄 Перезапуск бота. Отправляю уведомления...")

    # Подключение к БД и получение всех tg_id
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users")
        users = cursor.fetchall()
        conn.close()
    except Exception as e:
        await message.answer(f"⚠️ Ошибка при получении пользователей из БД: {e}")
        return

    # Рассылка (здесь пока нет отправки сообщений, только пауза)
    for user in users:
        user_id = user[0]
        try:
            # Если нужно отправить уведомление о перезапуске, раскомментируйте следующую строку:
            # await bot.send_message(chat_id=user_id, text="⚙️ Бот временно перезапускается. Через минуту будет доступен.")
            await asyncio.sleep(BROADCAST_DELAY)  # задержка 2 секунды
        except Exception as e:
            print(f"Не удалось отправить сообщение пользователю {user_id}: {e}")

    await asyncio.sleep(1)
    os._exit(1)  # Завершение процесса


@router.message(Command("say_all"))
async def say_all(message: Message, bot):
    if message.from_user.id not in ADMINS_LIST:
        await message.answer("❌ У вас нет доступа к этой команде.")
        return

    command_text = message.text
    parts = command_text.split(maxsplit=1)

    if len(parts) < 2:
        await message.answer("✉️ Используйте: <code>/say_all текст сообщения</code>")
        return

    broadcast_text = parts[1]

    # Получаем пользователей
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users")
        users = cursor.fetchall()
        conn.close()
    except Exception as e:
        await message.answer(f"⚠️ Ошибка при получении пользователей: {e}")
        return

    success = 0
    failed = 0

    await message.answer(f"📤 Начинаю рассылку ({len(users)} пользователей)...")

    for user in users:
        user_id = user[0]
        try:
            await bot.send_message(chat_id=user_id, text=broadcast_text)
            success += 1
        except Exception as e:
            print(f"❌ Ошибка при отправке {user_id}: {e}")
            failed += 1
        await asyncio.sleep(BROADCAST_DELAY)  # задержка 2 секунды

    await message.answer(f"✅ Сообщение отправлено {success} пользователям.\n❌ Ошибок: {failed}")


# === чат айди ===
@router.message(F.text == "/get_chat_id")
async def get_chat_id(message: Message):
    await message.answer(f"Chat ID: {message.chat.id}")


# АДМИНКИ

def is_admin(user_id: int) -> bool:
    # СНАЧАЛА проверяем наличие пользователя в конфиге ADMINS_LIST
    if user_id in ADMINS_LIST:
        return True
        
    # ЕСЛИ в конфиге нет, проверяем уровень в базе данных
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT admin_lvl FROM users WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        return row is not None and row[0] >= 1

def set_admin_level(user_id: int, lvl: int):
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE users SET admin_lvl = ? WHERE user_id = ?", (lvl, user_id))
        conn.commit()

@router.message(Command("admincheck"))
async def cmd_admincheck(message: types.Message):
    user_id = message.from_user.id
    if is_admin(user_id):
        await message.answer("Ты — админ!")
    else:
        await message.answer("Ты не админ.")

@router.message(Command("setadmin"))
async def cmd_setadmin(message: types.Message):
    if message.from_user.id not in ADMINS_LIST:
        await message.answer("❌ У вас нет доступа к этой команде.")
        return

    # Получаем полный текст команды, например "/setadmin 12345 2"
    text = message.text or ""
    args = text.split(maxsplit=2)  # разделим на максимум 3 части: команда, user_id, lvl

    if len(args) != 3:
        await message.answer("Использование: /setadmin <user_id> <lvl>")
        return

    try:
        target_user_id = int(args[1])
        level = int(args[2])
    except ValueError:
        await message.answer("Параметры должны быть числами.")
        return

    set_admin_level(target_user_id, level)
    await message.answer(f"Права пользователя {target_user_id} обновлены до уровня {level}.")

def get_admins():
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username, first_name, admin_lvl FROM users WHERE admin_lvl > 0")
    admins = cursor.fetchall()
    conn.close()
    return admins


def get_admin_list_keyboard():
    admins = get_admins()
    builder = InlineKeyboardBuilder()

    for user_id, username, first_name, admin_lvl in admins:
        name = f"{first_name} (@{username})" if username else first_name
        builder.button(
            text=f"{name} [lvl {admin_lvl}]",
            callback_data=f"admin_profile:{user_id}"
        )

    builder.adjust(1)
    return builder.as_markup()


@router.message(F.text == "/admin_list")
async def admin_list_handler(message: types.Message):
    await message.answer("👮‍♂️ Список админов:", reply_markup=get_admin_list_keyboard())

@router.callback_query(F.data.startswith("admin_profile:"))
async def show_admin_profile(callback: types.CallbackQuery):
    user_id = int(callback.data.split(":")[1])

    conn = connect()
    cursor = conn.cursor()
    cursor.execute("SELECT username, first_name, last_name, admin_lvl FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()

    if result:
        username, first_name, last_name, admin_lvl = result
        full_name = f"{first_name or ''} {last_name or ''}".strip()
        text = f"""
👤 <b>Профиль админа</b>

🆔 ID: <code>{user_id}</code>
👨‍💼 Имя: {full_name}
🔗 Username: @{username if username else '—'}
🛡 Уровень: {admin_lvl}
"""
        await callback.message.edit_text(text, parse_mode="HTML")
    else:
        await callback.answer("Админ не найден", show_alert=True)


# === ТАЙМЕР ВКЛ ВЫКЛ ===

@router.message(Command(commands=["timer_on"]))
async def enable_timer_check(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к этой команде.")
        return

    set_check_member_enabled(message.from_user.id, True)
    set_check_skill_enabled(message.from_user.id, True)
    await message.answer("✅ Проверка таймера открытий карточек включена для вас.")

@router.message(Command(commands=["timer_on_user"]))
async def enable_timer_check(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к этой команде.")
        return

    # Получаем полный текст команды, например "/timer_on_user 12345 2"
    text = message.text or ""
    args = text.split(maxsplit=1)  # разделим на максимум 2 части: команда, user_id

    if len(args) != 2:
        await message.answer("Использование: /timer_on_user <user_id>")
        return

    try:
        target_user_id = int(args[1])
    except ValueError:
        await message.answer("Параметры должны быть числами.")
        return

    set_check_member_enabled(target_user_id, True)
    set_check_skill_enabled(target_user_id, True)
    await message.answer(f"✅ Проверка таймера открытий карточек включена для пользователя {target_user_id}")

@router.message(Command(commands=["timer_off"]))
async def disable_timer_check(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к этой команде.")
        return

    set_check_member_enabled(message.from_user.id, False)
    set_check_skill_enabled(message.from_user.id, False)
    await message.answer("✅ Проверка таймера открытий карточек отключена для вас.")

@router.message(Command(commands=["timer_off_user"]))
async def enable_timer_check(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к этой команде.")
        return

    # Получаем полный текст команды, например "/timer_off_user 12345 2"
    text = message.text or ""
    args = text.split(maxsplit=1)  # разделим на максимум 2 части: команда, user_id

    if len(args) != 2:
        await message.answer("Использование: /timer_off_user <user_id>")
        return

    try:
        target_user_id = int(args[1])
    except ValueError:
        await message.answer("Параметры должны быть числами.")
        return

    set_check_member_enabled(target_user_id, False)
    set_check_skill_enabled(target_user_id, False)
    await message.answer(f"✅ Проверка таймера открытий карточек выключена для пользователя {target_user_id}")

@router.message(Command(commands=["timer_status"]))
async def timer_status(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к этой команде.")
        return

    timers = load_timers()
    user_timer = timers.get(str(message.from_user.id), {})
    enabled = user_timer.get("check_enabled", True)
    status_text = "включена" if enabled else "отключена"
    await message.answer(f"ℹ️ Проверка таймера открытий карточек сейчас *{status_text}* для вас.", parse_mode="Markdown")


# === Выдать крутки

@router.message(Command(commands=["give_member_bonus"]))
async def give_member_bonus_handler(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к этой команде.")
        return

    text = message.text or ""
    args = text.split(maxsplit=2)  # команда, user_id, количество

    if len(args) != 3:
        await message.answer("Использование: /give_member_bonus <user_id> <количество>")
        return

    try:
        target_user_id = int(args[1])
        bonus_amount = int(args[2])
    except ValueError:
        await message.answer("Параметры должны быть числами.")
        return

    # Выдаём бонусы указанному пользователю
    add_member_bonus(target_user_id, bonus_amount)

    await message.answer(
        f"✅ Пользователю {target_user_id} выдано {bonus_amount} бонусов."
    )


@router.message(Command(commands=["give_skill_bonus"]))
async def give_member_bonus_handler(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к этой команде.")
        return

    text = message.text or ""
    args = text.split(maxsplit=2)  # команда, user_id, количество

    if len(args) != 3:
        await message.answer("Использование: /give_member_bonus <user_id> <количество>")
        return

    try:
        target_user_id = int(args[1])
        bonus_amount = int(args[2])
    except ValueError:
        await message.answer("Параметры должны быть числами.")
        return

    # Выдаём бонусы указанному пользователю
    add_skill_bonus(target_user_id, bonus_amount)

    await message.answer(
        f"✅ Пользователю {target_user_id} выдано {bonus_amount} бонусов."
    )


# === Выдать крутки казика ===
@router.message(Command("give_spins_user"))
async def give_spins_user_cmd(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к этой команде.")
        return

    parts = message.text.split()
    if len(parts) != 3:
        await message.reply("⚠️ Использование: /give_spins_user <user_id> <count>")
        return

    try:
        user_id = int(parts[1])
        count = int(parts[2])
    except ValueError:
        await message.reply("❌ Неверный формат. Пример: /give_spins_user 123456789 2")
        return

    from database.db import load_roulette_data, save_roulette_data

    data = load_roulette_data(user_id)
    data["roulette_count"] += count
    data["last_increment"] = datetime.datetime.utcnow().isoformat()
    save_roulette_data(user_id, data)

    await message.reply(f"✅ Пользователю <b>{user_id}</b> выдано <b>{count}</b> спинов. Теперь у него: <b>{data['roulette_count']}</b>")


@router.message(Command("give_spins_all"))
async def give_spins_all_cmd(message: types.Message):
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет доступа к этой команде.")
        return

    parts = message.text.split()
    if len(parts) != 2:
        await message.reply("⚠️ Использование: /give_spins_all <count>")
        return

    try:
        count = int(parts[1])
    except ValueError:
        await message.reply("❌ Неверный формат. Пример: /give_spins_all 2")
        return

    from database.db import get_all_user_ids, load_roulette_data, save_roulette_data

    user_ids = get_all_user_ids()
    updated = 0

    for uid in user_ids:
        data = load_roulette_data(uid)
        data["roulette_count"] += count
        data["last_increment"] = datetime.datetime.utcnow().isoformat()
        save_roulette_data(uid, data)
        updated += 1

    await message.reply(f"✅ Выдано по <b>{count}</b> спинов <b>{updated}</b> пользователям.")


@router.message(Command("give_money_user"))
async def give_money_user_cmd(message: Message):
    if message.from_user.id not in ADMINS_LIST:
        await message.answer("❌ У вас нет доступа к этой команде.")
        return

    parts = (message.text or "").split()
    if len(parts) != 3:
        await message.reply("⚠️ Использование: /give_money_user <user_id> <amount>")
        return

    try:
        target_user_id = int(parts[1])
        amount = int(parts[2])
    except ValueError:
        await message.reply("❌ Параметры должны быть числами. Пример: /give_money_user 123456789 50")
        return

    try:
        new_balance = add_balance(target_user_id, amount)
    except Exception as e:
        await message.reply(f"❌ Ошибка при выдаче денег: {e}")
        return

    await message.reply(f"✅ Пользователю <b>{target_user_id}</b> выдано <b>{amount} 🔥</b>. Новый баланс: <b>{new_balance} 🔥</b>")


@router.message(Command("give_money_all"))
async def give_money_all_cmd(message: Message):
    if message.from_user.id not in ADMINS_LIST:
        await message.answer("❌ У вас нет доступа к этой команде.")
        return

    parts = (message.text or "").split()
    if len(parts) != 2:
        await message.reply("⚠️ Использование: /give_money_all <amount>")
        return

    try:
        amount = int(parts[1])
    except ValueError:
        await message.reply("❌ Параметр должен быть числом. Пример: /give_money_all 10")
        return

    user_ids = get_all_user_ids()
    success = 0
    for uid in user_ids:
        try:
            add_balance(uid, amount)
            success += 1
        except Exception:
            # keep going; we don't want one failure to stop the distribution
            continue

    await message.reply(f"✅ Выдано по <b>{amount} 🔥</b> {success} пользователям.")


# === CASINO TEST ===

# --- Настройка шансов выпадения символов (в процентах) (синхронно с handlers/roulette.py) ---
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

SPECIAL_REWARDS = {
    "😹": "draw_member",
    "✅": "draw_skill",
    "👻": "add_spins",
    "💣": "die_spins",
    "💋": "full_die"
}


@router.message(F.text == "/simulate_slots")
async def simulate_slots(message: Message):
    """Админская проверка вероятностей слотов — НЕ изменяет реальные данные пользователя.

    Проводит симуляцию на количестве спинов из пользователя и выводит статистику.
    """
    user_id = str(message.from_user.id)
    data = load_roulette_data(user_id)

    total_spins = data.get("roulette_count", 0)
    if total_spins == 0:
        await message.answer("🎰 У тебя нет круток.")
        return

    symbols, weights = _get_symbols_and_weights()

    stats = {s: 0 for s in symbols}
    stats["❌"] = 0

    # Симуляция без изменения реального состояния
    for _ in range(total_spins):
        result = random.choices(symbols, weights=weights, k=3)
        if result[0] == result[1] == result[2]:
            stats[result[0]] += 1
        else:
            stats["❌"] += 1

    summary_lines = [f"{k} — {v} раз" for k, v in stats.items()]
    summary = "\n".join(summary_lines)

    await message.answer(
        f"🎰 Симуляция {total_spins} круток завершена (без изменения данных)!\n\n📊 Статистика:\n{summary}\n\n"
        f"🎯 Текущие реальные крутки у пользователя: {data.get('roulette_count', 0)}"
    )


# === ПРЕСЕЙВ РАССЫЛКА ===

@router.message(Command("presale"))
async def cmd_presale(message: Message, bot: Bot):
    if message.from_user.id not in ADMINS_LIST:
        await message.answer("❌ У вас нет доступа к этой команде.")
        return

    text = (
        "🎵 Сделай пресейв нашей песни, 🎵Тихая роскошь🎵, и получи уникальный приз, либо получишь по яйкам!🤣\n\n"
        "Нажми на кнопку ниже, чтобы узнать, как получить карту. Делай, что сказано, ✨висячий хуй старой собаки✨, спасибо, пожалуйста😍"
    )
    button = InlineKeyboardButton(
        text="🎧 Сделать пресейв",
        callback_data="presave_click"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[button]])

    user_ids = get_all_user_ids()
    success = 0
    failed = 0
    await message.answer(f"📤 Начинаю рассылку нахуй ({len(user_ids)} пользователей)...")

    for uid in user_ids:
        try:
            await bot.send_message(chat_id=uid, text=text, reply_markup=keyboard)
            success += 1
        except Exception as e:
            print(f"❌ Ошибка отправки {uid}: {e}")
            failed += 1
        await asyncio.sleep(BROADCAST_DELAY)  # задержка 2 секунды

    await message.answer(f"✅ Отправлено {success} пользователям.\n❌ Ошибок: {failed}")

# ==================== ВЫДАТЬ ДОСТУП К МАТЮКАМ ====================

class AdminGiveWordState(StatesGroup):
    waiting_for_username = State()

@router.callback_query(F.data == "admin_give_word_access")
async def admin_give_word_access_cb(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа.", show_alert=True)
        return
    
    await callback.message.answer(
        "📝 Введите username пользователя (с @ или без), которому нужно выдать доступ к матюкам:\n\n"
        "<i>(Для отмены просто напишите /cancel)</i>",
        parse_mode="HTML"
    )
    await state.set_state(AdminGiveWordState.waiting_for_username)
    await callback.answer()

@router.message(AdminGiveWordState.waiting_for_username)
async def process_give_word_username(message: Message, state: FSMContext, bot: Bot):
    if not message.text or message.text == "/cancel":
        await message.answer("❌ Действие отменено.")
        await state.clear()
        return
        
    username = message.text.strip()
    clean_username = username.lstrip('@')
    
    # Оборачиваем ВЕСЬ процесс в try-except, чтобы админ 100% получил обратную связь даже при сбое БД или файлов!
    try:
        # 1. Находим пользователя
        user = find_user_by_username(clean_username)
        if not user:
            await message.answer(f"❌ Пользователь @{clean_username} не найден в базе данных бота.")
            await state.clear()
            return
            
        user_id = user["user_id"]
        actual_username = user["username"]
        
        # 2. Безопасно получаем слово (с защитой от отсутствия файла words.json)
        try:
            word = get_random_word_for_user(user_id)
        except Exception as e_word:
            print(f"Ошибка чтения слов: {e_word}")
            word = None
            
        if not word:
            word = "БЛЯТЬ" # Надежный fallback, если файл не прочитался
            
        id_op = f"ADMIN_{uuid.uuid4().hex[:8]}"
        
        # 3. Сохраняем донат
        is_duplicate = save_donation(id_op, user_id, actual_username, 0, "ADMIN", word)
        
        # 4. Отправляем гарантированный ответ АДМИНУ
        if is_duplicate:
            add_balance(user_id, 10)
            await message.answer(
                f"✅ Пользователю @{actual_username} выдан доступ к матюкам!\n"
                f"🔁 Ему выпал повторный матюк: <b>{word}</b>, который конвертировался в 10🔥.", 
                parse_mode="HTML"
            )
        else:
            await message.answer(
                f"✅ Пользователю @{actual_username} выдан доступ к матюкам!\n"
                f"🎁 Ему выпал матюк: <b>{word}</b>", 
                parse_mode="HTML"
            )

        # 5. Попытка уведомить пользователя в ЛС (отдельный блок, чтобы блокировка бота юзером не роняла хэндлер)
        try:
            if is_duplicate:
                await bot.send_message(
                    user_id,
                    f"🎉 <b>Администратор выдал вам доступ к матюкам!</b>\n"
                    f"Теперь вы можете ругаться матом в боте.\n\n"
                    f"🔁 Вам выпал повторный матюк: <b>{word}</b>\n"
                    f"🔥 Он автоматически сожгся, и вы получили <b>10🔥</b> на свой счёт!",
                    parse_mode="HTML"
                )
            else:
                await bot.send_message(
                    user_id,
                    f"🎉 <b>Администратор выдал вам доступ к матюкам!</b>\n"
                    f"Теперь вы можете ругаться матом в боте.\n\n"
                    f"🎁 Ваш первый матюк: <b>{word}</b>",
                    parse_mode="HTML"
                )
        except Exception as send_err:
            await message.answer(f"ℹ️ Доступ выдан, но написать юзеру в ЛС не удалось (возможно, он заблокировал бота).")

    except Exception as fatal_error:
        # Если упала база данных, SQLite или что-то еще — админ увидит точную причину в чате!
        await message.answer(f"⚠️ <b>Произошла ошибка при выдаче прав:</b>\n<code>{fatal_error}</code>", parse_mode="HTML")
        print(f"❌ Критическая ошибка в process_give_word_username: {fatal_error}")
        return
        
    finally:
        # Гарантированно сбрасываем состояние, чтобы админ не застрял в режиме ввода юзернейма
        await state.clear()
        return

# ==================== УДАЛИТЬ СЛОТ ПИДАРАЗА ====================

class AdminDeletePidarazState(StatesGroup):
    waiting_for_number = State()

@router.callback_query(F.data == "admin_delete_pidaraz_slot")
async def admin_delete_pidaraz_slot_cb(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет доступа.", show_alert=True)
        return
    
    await callback.message.answer(
        "🗑 <b>Введите номер слота (от 1 до 9999)</b>, который нужно освободить:\n\n"
        "<i>(Для отмены напишите /cancel)</i>",
        parse_mode="HTML"
    )
    await state.set_state(AdminDeletePidarazState.waiting_for_number)
    await callback.answer()

@router.message(AdminDeletePidarazState.waiting_for_number)
async def process_delete_pidaraz_slot(message: Message, state: FSMContext):
    if not message.text or message.text == "/cancel":
        await message.answer("❌ Действие отменено.")
        await state.clear()
        return
        
    if not message.text.isdigit():
        await message.answer("❌ Пожалуйста, отправьте только число.")
        return

    slot_number = int(message.text)
    
    if slot_number < 1 or slot_number > 9999:
        await message.answer("❌ Номер должен быть от 1 до 9999. Попробуйте еще раз или напишите /cancel:")
        return

    try:
        conn = connect()
        cursor = conn.cursor()
        
        # Пытаемся найти, где именно хранится столбец (в users или pidarazs)
        cursor.execute("PRAGMA table_info(users)")
        users_columns = [col[1] for col in cursor.fetchall()]
        
        deleted = False
        
        # Проверяем, есть ли поле pid_number в таблице users
        if "pid_number" in users_columns:
            cursor.execute("SELECT user_id FROM users WHERE pid_number = ?", (slot_number,))
            if cursor.fetchone():
                cursor.execute("UPDATE users SET pid_number = NULL WHERE pid_number = ?", (slot_number,))
                deleted = True
        elif "pidaraz_number" in users_columns:
            cursor.execute("SELECT user_id FROM users WHERE pidaraz_number = ?", (slot_number,))
            if cursor.fetchone():
                cursor.execute("UPDATE users SET pidaraz_number = NULL WHERE pidaraz_number = ?", (slot_number,))
                deleted = True
        else:
            # Возможно, данные хранятся в отдельной таблице
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pidarazs'")
            if cursor.fetchone():
                cursor.execute("SELECT user_id FROM pidarazs WHERE pid_number = ?", (slot_number,))
                if cursor.fetchone():
                    cursor.execute("DELETE FROM pidarazs WHERE pid_number = ?", (slot_number,))
                    deleted = True

        conn.commit()
        conn.close()

        if deleted:
            await message.answer(f"✅ Слот <b>Пидараз {slot_number}</b> успешно освобожден! Теперь его можно занять.", parse_mode="HTML")
        else:
            await message.answer(f"⚠️ Слот <b>{slot_number}</b> и так уже свободен или не найден.", parse_mode="HTML")

    except Exception as e:
        await message.answer(f"⚠️ <b>Произошла ошибка при удалении:</b>\n<code>{e}</code>", parse_mode="HTML")
        print(f"❌ Ошибка в process_delete_pidaraz_slot: {e}")
        
    finally:
        await state.clear()