import sqlite3, json, random, datetime, asyncio, time
from threading import Lock

from pathlib import Path

from aiogram import Router, F, Bot
from aiogram.utils.keyboard import InlineKeyboardBuilder, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.types import Message, CallbackQuery, LabeledPrice, PreCheckoutQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from utils.config import DA_TOKEN, TOKEN
from database.db import connect, add_balance
from handlers.keyboard import get_back_menu_button
import uuid
import socketio

sio = socketio.AsyncClient()  # создаём объект клиента


# создаём один экземпляр бота
bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

router = Router()

DA_LINK = "https://www.donationalerts.com/r/pix0r_"

STORAGE_FILE = Path("data/table/pending_donations.json")
WORDS_FILE = "data/cards/words.json"
DB_FILE = "database/users.db"

class DonateStates(StatesGroup):
    waiting_for_amount = State()















# ====== DonationAlerts обработчики ======
@sio.on("connect")
async def on_connect():
    print("✅ Подключились к DonationAlerts")
    await sio.emit("add-user", {"token": DA_TOKEN, "type": "alert_widget"})

@sio.on("donation")
async def on_donation(data):
    id_operation = uuid.uuid4().hex  # уникальный ID операции для возвратов

    y = json.loads(data)
    message = y["message"]  # unique_code
    amount = y["amount"]
    currency = y["currency"]

    user_id, username, stored_amount = get_user_by_code(message)

    print(f"💸 Донат от {username}: {amount}{currency}, код={message}")
    if user_id:
        # Код валиден — выдаём приз
        word = get_random_word_for_user(user_id)
        save_donation(id_operation, user_id, username, amount, currency, word or "")
        remove_code(message)

        # Отправка сообщения пользователю
        try:
            await bot.send_message(
                user_id,
                f"🎁 Твой донат на {amount}{currency} успешно получен!\n"
                f"Тебе выпал матюк: <b>{word}</b>\n"
                f"💖 Спасибо за поддержку!\n\n Транзакция: `{id_operation}`"
            )
        except Exception as e:
            print(f"❌ Не удалось отправить сообщение пользователю {user_id}: {e}")
    else:
        print(f"❌ Донат с кодом {message} не найден или уже использован.")

async def run_da_client():
    await sio.connect("wss://socket.donationalerts.ru:443", transports=["websocket"])
    await sio.wait()





# ====== Хранилище уникальных кодов ======
# Словарь: key=код, value=(user_id, amount, expiry_timestamp)
_codes_storage: dict[str, tuple[int, int, float]] = {}
_codes_lock = Lock()

CODE_EXPIRY_SECONDS = 3 * 60 * 60  # 3 часа

def add_code(user_id: int, username: str, code: str, amount: int = None):
    expiry = time.time() + CODE_EXPIRY_SECONDS
    with _codes_lock:
        _codes_storage[code] = (user_id, username, amount or 0, expiry)

def get_user_by_code(code: str):
    with _codes_lock:
        entry = _codes_storage.get(code)
        if not entry:
            return None, None
        user_id, username, amount, expiry = entry
        if time.time() > expiry:
            # Код устарел
            del _codes_storage[code]
            return None, None
        return user_id, username, amount

def remove_code(code: str):
    with _codes_lock:
        _codes_storage.pop(code, None)









def generate_da_link(user_id: int, username: str, amount: int = None) -> tuple[str, str]:
    """Генерация ссылки на DonationAlerts с уникальным кодом"""
    unique_code = f"T{user_id}_{uuid.uuid4().hex[:6]}"
    link = f"{DA_LINK}?message={unique_code}"
    if amount:
        link += f"&sum={amount}"

    # Сохраняем код в хранилище на 3 часа
    add_code(user_id, username, unique_code, amount)
    return link, unique_code



@router.callback_query(F.data == "prikalyimba_donate_svoysumrub_menu")
async def donate_custom(callback: CallbackQuery, state: FSMContext):
    # Генерируем ссылку без фиксированной суммы
    link, code = generate_da_link(callback.from_user.id, callback.from_user.username or "")

    await state.update_data(da_code=code)

    kb = InlineKeyboardBuilder()
    kb.row(InlineKeyboardButton(text="💸 Оплатить (любая сумма)", url=link))
    kb.row(InlineKeyboardButton(text="❌ Отменить", callback_data="donate_cancel"))

    await callback.message.edit_text(
        f"👉 Введи сумму на сайте DonationAlerts.\n\n"
        f"🔑 Твой код: <code>{code}</code>\n"
        f"Обязательно оставь его в комментарии при донате. "
        f"По нему мы определим твой донат и выдадим приз.\n\n"
        f"После оплаты приз придёт автоматически 🚀",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "prikalyimba_donate_100zv_menu")
async def donate_start(callback: CallbackQuery, state: FSMContext):
    amount = 100

    kb = InlineKeyboardBuilder()
    kb.button(
        text=f"💸 Оплатить {amount} ⭐️",
        pay=True
    )
    kb.button(
        text="❌ Отменить",
        callback_data="donate_cancel"
    )
    kb.adjust(1)

    prices = [LabeledPrice(label="Поддержка бота", amount=amount)]

    await callback.message.answer_invoice(
        title="Поддержка проекта",
        description=f"Спасибо за поддержку! Вы отправите {amount} звёзд ⭐️",
        prices=prices,
        provider_token="",  # Не указываем для Telegram Stars
        payload=f"{amount}_stars",
        currency="XTR",
        reply_markup=kb.as_markup()
    )
    await state.clear()

@router.callback_query(F.data == "prikalyimba_donate_svoysumzv_menu")
async def donate_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "Вы точно хотите поддержать бота?! Напоминаем: Вы не получите никакого преимущества!\n\n Введите сумму доната (минимум 100):",
        reply_markup=get_back_menu_button())
    await state.set_state(DonateStates.waiting_for_amount)
    await callback.answer()

@router.message(DonateStates.waiting_for_amount)
async def donate_amount_handler(message: Message, state: FSMContext):
    try:
        amount = int(message.text)
        if amount < 100:
            await message.answer("❌ Минимальная сумма доната — 100 звёзд. Введите сумму ещё раз:")
            return
    except ValueError:
        await message.answer("❌ Введите сумму доната числом (минимум 100):")
        return

    kb = InlineKeyboardBuilder()
    kb.button(
        text=f"💸 Оплатить {amount} ⭐️",
        pay=True
    )
    kb.button(
        text="❌ Отменить",
        callback_data="donate_cancel"
    )
    kb.adjust(1)

    prices = [LabeledPrice(label="Поддержка бота", amount=amount)]

    await message.answer_invoice(
        title="Поддержка проекта",
        description=f"Спасибо за поддержку! Вы отправите {amount} звёзд ⭐️",
        prices=prices,
        provider_token="",  # Не указываем для Telegram Stars
        payload=f"{amount}_stars",
        currency="XTR",
        reply_markup=kb.as_markup()
    )
    await state.clear()

@router.callback_query(F.data == "donate_cancel")
async def on_donate_cancel(callback: CallbackQuery):
    await callback.answer("❌ Платёж отменён")
    await callback.message.delete()

@router.pre_checkout_query()
async def pre_checkout_query(query: PreCheckoutQuery):
    await query.answer(ok=True)

@router.message(F.successful_payment)
async def on_successfull_payment(message: Message):

    amount = int(message.successful_payment.total_amount) if hasattr(message.successful_payment, 'total_amount') else 0
    user_id = message.from_user.id
    id_operation = uuid.uuid4().hex  # уникальный ID операции для возвратов
    username = message.from_user.username or ""

    word = get_random_word_for_user(user_id)


    # Сохраняем донат
    save_donation(id_operation, user_id, username, amount, "XTR", word or "")

    # Показать выданное слово и благодарность
    await message.answer(
        f"🎁 Тебе выпал матюк: <b>{word}</b>\nСумма доната: {amount}\n"
        f"💖 Спасибо за поддержку!\n\n Транзакция: `{id_operation}`",
        parse_mode="HTML",
        message_effect_id="5159385139981059251"
    )


@router.callback_query(F.data.startswith("sell_word:"))
async def sell_word(callback: CallbackQuery):
    # format: sell_word:<page>
    try:
        page = int(callback.data.split(":", 1)[1])
    except Exception:
        page = 0

    user_id = callback.from_user.id

    # load user's words
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT words, user_id FROM user_donations WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        await callback.answer("У тебя нет слов для продажи.", show_alert=True)
        return

    # We need to remove the specific donate_history row (the UI lists history entries)
    # Fetch donate_history entries (use rowid to delete exact row)
    cur.execute("SELECT rowid, word FROM donate_history WHERE user_id = ? ORDER BY date", (user_id,))
    dh_rows = cur.fetchall()
    if not dh_rows:
        conn.close()
        await callback.answer("У тебя нет слов для продажи.", show_alert=True)
        return

    if page < 0 or page >= len(dh_rows):
        conn.close()
        await callback.answer("Неверная позиция.", show_alert=True)
        return

    rowid, word_to_sell = dh_rows[page]

    try:
        # delete the exact donate_history row
        cur.execute("DELETE FROM donate_history WHERE rowid = ?", (rowid,))

        # Now update user_donations.words if needed: if no remaining donate_history rows with this word,
        # remove it from the user's words list and decrement word_count.
        cur.execute("SELECT words, word_count FROM user_donations WHERE user_id = ?", (user_id,))
        ud = cur.fetchone()
        if ud:
            try:
                words_json = ud[0] or '[]'
                ud_words = json.loads(words_json)
            except Exception:
                ud_words = []

            # check if any remaining history entries with same word exist
            cur.execute("SELECT COUNT(1) FROM donate_history WHERE user_id = ? AND word = ?", (user_id, word_to_sell))
            cnt_row = cur.fetchone()
            remaining = cnt_row[0] if cnt_row else 0

            if remaining == 0 and word_to_sell in ud_words:
                ud_words.remove(word_to_sell)
                word_count = (ud[1] or 0) - 1 if ud[1] is not None else 0
                cur.execute("UPDATE user_donations SET words = ?, word_count = ? WHERE user_id = ?", (json.dumps(ud_words), max(0, word_count), user_id))

        conn.commit()
    except Exception:
        conn.rollback()
        conn.close()
        await callback.answer("Произошла ошибка при попытке продать слово.", show_alert=True)
        return

    conn.close()

    # Give user 10 units
    try:
        new_balance = add_balance(user_id, 10)
    except Exception:
        new_balance = None

    await callback.message.delete()
    await callback.message.answer(f"✅ Матюк '{word_to_sell}' продан за 10 🔥. Твой баланс: {new_balance if new_balance is not None else 'неизвестно'} 🔥", reply_markup=get_back_menu_button())
    await callback.answer()


def get_random_word_for_user(user_id: int) -> str:
    # Загружаем все слова из файла
    with open(WORDS_FILE, "r", encoding="utf-8") as f:
        words = json.load(f)

    if not words:
        return None
        
    # Матюки могут повторяться - выбираем случайное слово из всех доступных
    return random.choice(words)




def save_donation(id_operation: str, user_id: int, username: str, amount: int, currency: str, word: str):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    date_now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Пересчитываем в рубли
    if currency.upper() in ("XTR", "STAR", "STARS", "ЗВЕЗДЫ", "ЗВЕЗДА"):  # телеграм-звезды
        amount_rub = amount * 1  # 1 звезда = 1 рубль
    elif currency.upper() == "RUB":
        amount_rub = amount
    elif currency.upper() == "USD":
        amount_rub = amount * 80
    elif currency.upper() == "EUR":
        amount_rub = amount * 94
    elif currency.upper() == "BRL":
        amount_rub = amount * 15
    elif currency.upper() == "TRY":
        amount_rub = amount * 2
    elif currency.upper() == "PLN":
        amount_rub = amount * 22
    else:
        amount_rub = amount  # fallback

    # Сохраняем в историю донатов
    c.execute(
        """INSERT INTO donate_history 
        (id_operation, user_id, username, donate_amount, currency, amount_rub, word, date) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (id_operation, user_id, username, amount, currency.upper(), amount_rub, word, date_now)
    )

    # Проверяем, есть ли пользователь в user_donations
    c.execute("SELECT biggest_amount, all_amount, words, word_count FROM user_donations WHERE user_id=?", (user_id,))
    row = c.fetchone()

    if row:
        biggest_amount, all_amount, words_json, word_count = row

        all_amount += amount_rub  # копим только рубли
        biggest_amount = max(biggest_amount, amount_rub)
        word_count = (word_count or 0) + 1

        words_list = json.loads(words_json) if words_json else []
        if word not in words_list:
            words_list.append(word)

        c.execute(
            """UPDATE user_donations 
            SET username=?, biggest_amount=?, all_amount=?, words=?, word_count=? 
            WHERE user_id=?""",
            (username, biggest_amount, all_amount, json.dumps(words_list), word_count, user_id)
        )
    else:
        words_list = [word]
        c.execute(
            """INSERT INTO user_donations 
            (user_id, username, biggest_amount, all_amount, words, word_count) 
            VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, username, amount_rub, amount_rub, json.dumps(words_list), 1)
        )

    conn.commit()
    conn.close()

def get_user_words(user_id):
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT word, donate_amount, date FROM donate_history WHERE user_id = ? ORDER BY date", (user_id,))
    words = cur.fetchall()
    conn.close()
    return words

def get_words_keyboard(page, total):
    prev_page = (page - 1) % total
    next_page = (page + 1) % total

    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="⬅", callback_data=f"word_collection:{prev_page}"),
        InlineKeyboardButton(text=f"{page+1}/{total}", callback_data="noop"),
        InlineKeyboardButton(text="➡", callback_data=f"word_collection:{next_page}")
    )
    builder.row(
    InlineKeyboardButton(text="Продать: 10🔥", callback_data=f"sell_word:{page}"),
    )
    builder.row(
        InlineKeyboardButton(text="↪️ Назад", callback_data="go_back_menu")
    )
    return builder.as_markup()

def get_donate_info_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(
            InlineKeyboardButton(text="⭐️ Прикалюха", callback_data="donate_menu"),
            InlineKeyboardButton(text="↪️ Назад", callback_data="go_back_menu")
        )
    return builder.as_markup()

instr = (
            "Вам необходимо задонатить для получения доступа к матюкам.\n\n"
            "За каждый донат которым вы поддержите разработку бота вам будут выпадать рандомные угарные матюки, которыми можно спамить в боте\n\n"
            "<tg-spoiler>А еще бот иногда материт участников ГУЧИГЕНГОВО =Р</tg-spoiler>"
        )

# --- Хендлер: показать коллекцию слов ---
@router.callback_query(F.data == "word_collection")
async def show_word_collection(callback: CallbackQuery):
    user_id = callback.from_user.id
    # Проверим, задонатил ли пользователь (есть ли запись в таблице user_donations)
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT words, all_amount FROM user_donations WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()

    if not row:
        # Отправляем полную инструкцию обычным сообщением (в сообщениях можно больше текста)
        try:
            await callback.message.answer(instr, reply_markup=get_donate_info_keyboard())
        except Exception:
            try:
                await callback.bot.send_message(callback.from_user.id, instr)
            except Exception:
                # если и это не удалось — ничего не делаем, чтобы не ломать обработку
                pass
        return

    words = get_user_words(user_id)
    if not words:
        await callback.answer("У вас пока нет слов в коллекции.", show_alert=True)
        return
    # Показываем первое слово
    word, amount, date = words[0]
    text = f"<b>{word}</b> - {amount}⭐️, {date}"
    kb = get_words_keyboard(0, len(words))
    await callback.message.delete()
    await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")

# --- Хендлер: перелистывание коллекции ---
@router.callback_query(F.data.startswith("word_collection:"))
async def paginate_word_collection(callback: CallbackQuery):
    user_id = callback.from_user.id
    words = get_user_words(user_id)
    if not words:
        await callback.answer("У тебя нет слов.", show_alert=True)
        return
    page = int(callback.data.split(":")[1])
    word, amount, date = words[page]
    text = f"<b>{word}</b> - {amount}⭐️, {date}"
    kb = get_words_keyboard(page, len(words))
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")

# --- Хендлер: отправить случайный матюк из коллекции пользователя ---
@router.callback_query(F.data == "word_random")
async def send_random_user_word(callback: CallbackQuery):
    user_id = callback.from_user.id

    # Получаем слова пользователя
    words = get_user_words(user_id)

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    if not words:
        await callback.message.delete()
        await callback.message.answer(instr, reply_markup=get_donate_info_keyboard())
        return
    
    # Получаем текущее значение счетчика
    cur.execute("SELECT word_send_count FROM user_donations WHERE user_id = ?", (user_id,))
    row = cur.fetchone()

    if row:
        send_count_word_old = row[0]
    else:
        send_count_word_old = 0
        # На случай, если записи нет, создаём её
        cur.execute(
            "INSERT INTO user_donations (user_id, word_send_count) VALUES (?, ?)",
            (user_id, 0)
        )

    send_count_word = send_count_word_old + 1

    # Обновляем счетчик
    cur.execute(
         "UPDATE user_donations SET word_send_count=? WHERE user_id=?",
        (send_count_word, user_id)
    )
    conn.commit()
    conn.close()

    word = random.choice(words)[0]  # words — это (word, amount, date)

    # Небольшой шанс (7%) отправить сообщение в формате "рандомный ник из gg_members + матюк"
    if random.random() < 0.5:
        try:
            # Попробуем взять ник из data/cards/gg_members.json
            with open("data/cards/gg_members.json", "r", encoding="utf-8") as f:
                gg = json.load(f)
            members = gg.get("members") if isinstance(gg, dict) else None
            if not members:
                # fallback: try DB (legacy behavior)
                conn2 = sqlite3.connect(DB_FILE)
                cur2 = conn2.cursor()
                cur2.execute("SELECT username FROM users WHERE username IS NOT NULL AND username != ''")
                rows = cur2.fetchall()
                conn2.close()
                if rows:
                    random_username = random.choice(rows)[0]
                    if not random_username.startswith("@"):
                        random_username = "@" + random_username
                    await callback.answer()
                    await callback.message.answer(f"{random_username} {word}")
                    return
            else:
                random_username = random.choice(members)
                # send the stored nick as-is (gg_members.json may already include @ where appropriate)
                await callback.answer()
                await callback.message.answer(f"{random_username} {word}")
                return
        except Exception:
            # в случае ошибки — продолжаем обычный путь
            pass

    await callback.answer()  # убираем "часики" у кнопки
    await callback.message.answer(f"{word}", parse_mode="HTML")




