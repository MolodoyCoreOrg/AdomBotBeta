import sqlite3, json, datetime
from aiogram.types import InlineKeyboardMarkup
from database.stats import increment_stat
from handlers.keyboard import bonus_member_card_open

DB_PATH = "database/users.db"



def connect():
    # Use a longer timeout to wait for locks and allow connections from other threads.
    # Also enable WAL journal mode and foreign_keys to improve concurrency and integrity.
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row  # Позволяет обращаться по ключам, а не по индексам
    try:
        cur = conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL;")
        cur.execute("PRAGMA foreign_keys = ON;")
        cur.execute("PRAGMA synchronous = NORMAL;")
    except Exception:
        # If PRAGMA fails for any reason, ignore and continue with the connection
        pass
    return conn

def create_roulette_tables():
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS roulette_user (
            user_id INTEGER PRIMARY KEY,
            roulette_count INTEGER NOT NULL DEFAULT 5,
            opened_today INTEGER NOT NULL DEFAULT 0,
            total_opened INTEGER NOT NULL DEFAULT 0,
            last_reset TEXT DEFAULT '',
            last_increment TEXT NOT NULL,
            notified_max INTEGER NOT NULL DEFAULT 0,
            meow_count INTEGER NOT NULL DEFAULT 0,
            meow_count_all INTEGER NOT NULL DEFAULT 0,
            jopa_count INTEGER NOT NULL DEFAULT 0,
            kazino_upgrades TEXT DEFAULT '{}',
            fire_points INTEGER NOT NULL DEFAULT 0,
            upgrade_timer_reduce INTEGER NOT NULL DEFAULT 0,
            has_double_casino INTEGER NOT NULL DEFAULT 0,
            has_fast_spin INTEGER NOT NULL DEFAULT 0,
            dopa_bet INTEGER NOT NULL DEFAULT 0
        )
        """)
        
        # Миграция: добавляем новые колонки если они отсутствуют
        columns_to_add = [
            ("fire_points", "INTEGER NOT NULL DEFAULT 0"),
            ("upgrade_timer_reduce", "INTEGER NOT NULL DEFAULT 0"),
            ("has_double_casino", "INTEGER NOT NULL DEFAULT 0"),
            ("has_fast_spin", "INTEGER NOT NULL DEFAULT 0"),
            ("dopa_bet", "INTEGER NOT NULL DEFAULT 0")
        ]
        
        existing_columns = [row[1] for row in cur.execute("PRAGMA table_info(roulette_user)").fetchall()]
        
        for col_name, col_def in columns_to_add:
            if col_name not in existing_columns:
                cur.execute(f"ALTER TABLE roulette_user ADD COLUMN {col_name} {col_def}")
        cur.execute("""
        CREATE TABLE IF NOT EXISTS roulette_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            ts TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
            entry TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES roulette_user(user_id) ON DELETE CASCADE
        )
        """)
        conn.commit()

def create_user_card_drops_table():
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_card_drops (
                user_id INTEGER NOT NULL,
                card_name TEXT NOT NULL,
                drops_count INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (user_id, card_name)
            )
        """)

def create_user_donate_table():
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_donations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                biggest_amount INTEGER DEFAULT 0,
                all_amount INTEGER DEFAULT 0,
                words TEXT DEFAULT '[]'
            )
        """)
        conn.commit()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS donate_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_operation TEXT,
            user_id INTEGER,
            username TEXT,
            donate_amount INTEGER DEFAULT 0,
            currency TEXT NOT NULL,      -- RUB, USD, EUR, XTR
            amount_rub REAL,             -- пересчитано в рубли (опционально)
            word TEXT,
            date TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
        )
        """)
        conn.commit()

def create_users_table():
    conn = connect()  # открываем соединение
    try:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_number INTEGER,
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            admin_lvl INTEGER DEFAULT 0,
            banned INTEGER DEFAULT 0,
            cards TEXT DEFAULT '[]',
            timers TEXT DEFAULT '{}',
            member_cards TEXT DEFAULT '{}',
            skill_cards TEXT DEFAULT '{}',
            registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ranks TEXT DEFAULT '{}',
            referrer_id INTEGER,
            bonuses INTEGER DEFAULT 0,
            skill_bonuses INTEGER DEFAULT 0,
            total_invited INTEGER DEFAULT 0,
            referral_bonuses INTEGER DEFAULT 0,
            timezone TEXT DEFAULT 'UTC',
            balance INTEGER DEFAULT 0,
            balance_all_time INTEGER DEFAULT 0
        )
        """)
        conn.commit()
    finally:
        conn.close()

# ===== PRESAVE =====
def create_presave_table():
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS presave_actions (
                user_id INTEGER PRIMARY KEY,
                pressed_at INTEGER NOT NULL,      -- unix timestamp
                rewarded BOOLEAN DEFAULT 0,
                screenshot_file_id TEXT           -- file_id скриншота
            )
        """)
        conn.commit()

def init_db():
    create_user_donate_table()
    create_users_table()
    create_roulette_tables()
    create_user_card_drops_table()
    create_presave_table()   # добавлено
    init_exchange_tables()   # инициализация таблиц системы обмена

def get_user_timezone(user_id: int) -> str:
    """Return user's timezone string (IANA), default 'UTC' if not set."""
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT timezone FROM users WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        if row and row[0]:
            return row[0]
        return 'UTC'

def user_exists(user_id):
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
        return cur.fetchone() is not None

def add_user(user_id, username, first_name, last_name, referrer_id=None):
    conn = connect()
    cursor = conn.cursor()
    increment_stat("total_users")

    # Получить следующий user_number (порядковый номер регистрации)
    cursor.execute("SELECT MAX(user_number) FROM users")
    max_number = cursor.fetchone()[0]
    next_number = (max_number or 0) + 1

    cursor.execute("""
        INSERT INTO users (
            user_number,
            user_id,
            username,
            first_name,
            last_name,
            admin_lvl,
            banned,
            cards,
            timers,
            member_cards,
            skill_cards,
            ranks,
            referrer_id,
            bonuses,
            skill_bonuses,
            total_invited,
            referral_bonuses,
            timezone,
            balance,
            balance_all_time
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        next_number,
        user_id,
        username,
        first_name,
        last_name,
        0,          # admin_lvl
        0,          # banned
        '[]',       # cards
        '{}',       # timers
        '{}',       # member_cards
        '{}',       # skill_cards
        '{}',       # ranks
        referrer_id,
        0,           # bonuses
        0,              #способность бонус
        0,
        0,
        'UTC',      # timezone
        0,            # balance
        0             # balance_all_time
    ))

    if referrer_id:
        # Увеличиваем счетчик приглашенных у реферера
        cursor.execute("UPDATE users SET total_invited = total_invited + 1 WHERE user_id = ?", (referrer_id,))

    conn.commit()
    conn.close()

def add_bonus(user_id, bonus_amount=1):
    conn = connect()
    cursor = conn.cursor()

    cursor.execute("UPDATE users SET bonuses = bonuses + ? WHERE user_id = ?", (bonus_amount, user_id))

    conn.commit()
    conn.close()

def add_member_bonus(user_id: int, count: int = 1):
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE users SET bonuses = bonuses + ? WHERE user_id = ?", (count, user_id))
        conn.commit()

def add_skill_bonus(user_id: int, count: int = 1):
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE users SET skill_bonuses = skill_bonuses + ? WHERE user_id = ?", (count, user_id))
        conn.commit()

def update_referral_bonuses(user_id: int):
    with connect() as conn:
        cur = conn.cursor()

        # Получаем текущие значения
        cur.execute("SELECT total_invited, referral_bonuses FROM users WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        if not row:
            return

        invited = row["total_invited"]
        given = row["referral_bonuses"]

        # Расчет количества полагающихся бонусов
        if invited <= 10:
            expected = invited
        elif invited <= 20:
            expected = 10 + (invited - 10) // 2
        else:
            expected = 10 + (10 // 2) + (invited - 20) // 3

        to_give = expected - given
        if to_give > 0:
            cur.execute("""
                UPDATE users
                SET bonuses = bonuses + ?,
                    referral_bonuses = referral_bonuses + ?
                WHERE user_id = ?
            """, (to_give, to_give, user_id))
            conn.commit()



def get_referral_message(user_id: int, before_given: int) -> tuple[str, InlineKeyboardMarkup | None]:
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT total_invited FROM users WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        if not row:
            return "❌ Ошибка: пользователь не найден.", None

        invited = row["total_invited"]
        given = before_given  # передаём старое значение

        if invited < 10:
            return (
                "🎉 По твоей реферальной ссылке зарегистрировался пользователь.\n"
                "Ты получил бонусное открытие карточки 👥",
                bonus_member_card_open()
            )

        if invited < 20:
            next_bonus_at = 10 + ((given - 10 + 1) * 2)
        else:
            next_bonus_at = 20 + ((given - 15 + 1) * 3)

        remaining = max(0, next_bonus_at - invited)

        if remaining > 0:
            return (
                f"🎉 По твоей реферальной ссылке зарегистрировался пользователь.\n"
                f"Пригласи ещё {remaining} чел. и получи возможность открыть карту участника 👥",
                None
            )
        else:
            return (
                "🎉 По твоей реферальной ссылке зарегистрировался пользователь.\n"
                "Ты получил бонусное открытие карточки 👥",
                bonus_member_card_open()
            )






class Database:
    def __init__(self, db_path: str):
        self.path = db_path

    def connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row  # Чтобы можно было обращаться по ключам
        return conn

    def get_user_data(self, user_id: int):
        with self.connect() as conn:
            cursor = conn.execute("SELECT * FROM roulette_user WHERE user_id = ?", (user_id,))
            return cursor.fetchone()

    def insert_user(self, user_id: int, roulette_count: int = 0):
        with self.connect() as conn:
            conn.execute("INSERT INTO roulette_user (user_id, roulette_count) VALUES (?, ?)", (user_id, roulette_count))
            conn.commit()

    def update_user_data(self, user_id: int, roulette_count: int):
        with self.connect() as conn:
            conn.execute("UPDATE roulette_user SET roulette_count = ? WHERE user_id = ?", (roulette_count, user_id))
            conn.commit()














def get_user_data(user_id: int) -> tuple[list, dict]:
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT cards, timers FROM users WHERE user_id = ?", (user_id,))
        row = c.fetchone()
        if row:
            return json.loads(row[0]), json.loads(row[1])
        return [], {}

def update_user_data(user_id: int, cards: list, timers: dict):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute(
            "UPDATE users SET cards = ?, timers = ? WHERE user_id = ?",
            (json.dumps(cards), json.dumps(timers), user_id)
        )
        conn.commit()

def get_user_ranks(user_id: int) -> dict:
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT ranks FROM users WHERE user_id = ?", (user_id,))
        row = c.fetchone()
        return json.loads(row[0]) if row and row[0] else {}

def update_user_ranks(user_id: int, ranks: dict):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute(
            "UPDATE users SET ranks = ? WHERE user_id = ?",
            (json.dumps(ranks), user_id)
        )
        conn.commit()

def get_member_cards(user_id: int) -> dict:
    with connect() as conn:
        c = conn.cursor()
        c.execute("SELECT member_cards FROM users WHERE user_id = ?", (user_id,))
        row = c.fetchone()
        if row and row[0]:
            return json.loads(row[0])
        return {}
    
def update_member_cards(user_id: int, member_cards: dict):
    with connect() as conn:
        c = conn.cursor()
        c.execute(
            "UPDATE users SET member_cards = ? WHERE user_id = ?",
            (json.dumps(member_cards), user_id)
        )
        conn.commit()

def get_skill_cards(user_id: int) -> dict:
    with connect() as conn:
        c = conn.cursor()
        c.execute("SELECT skill_cards FROM users WHERE user_id = ?", (user_id,))
        row = c.fetchone()
        if row and row[0]:
            return json.loads(row[0])
        return {}
    
def update_skill_cards(user_id: int, skill_cards: dict):
    with connect() as conn:
        c = conn.cursor()
        c.execute(
            "UPDATE users SET skill_cards = ? WHERE user_id = ?",
            (json.dumps(skill_cards), user_id)
        )
        conn.commit()

def add_member_card(user_id: int, card_name: str):
    """Добавляет карту участника пользователю."""
    cards = get_member_cards(user_id)
    # Если карты еще нет или она имеет простую структуру, добавляем с rank
    if card_name not in cards:
        cards[card_name] = {'rank': 1}
    else:
        # Если карта уже есть, просто увеличиваем счетчик (если он есть)
        card_data = cards[card_name]
        if isinstance(card_data, dict):
            count = card_data.get('count', 1)
            cards[card_name]['count'] = count + 1
        elif isinstance(card_data, int):
            cards[card_name] = card_data + 1
        else:
            cards[card_name] = {'rank': 1, 'count': 2}
    update_member_cards(user_id, cards)

def remove_member_card(user_id: int, card_name: str):
    """Удаляет одну карту участника у пользователя."""
    cards = get_member_cards(user_id)
    if card_name in cards:
        del cards[card_name]
        update_member_cards(user_id, cards)

def add_skill_card(user_id: int, card_name: str, is_unique: bool = False):
    """Добавляет карту суперспособности пользователю.
    
    Args:
        user_id: ID пользователя
        card_name: Название карты
        is_unique: Если True, карта помечается как уникальная (нельзя продать/обменять)
    """
    cards = get_skill_cards(user_id)
    # Добавляем карту с базовой структурой
    cards[card_name] = {'rank': 1, 'unique': is_unique}
    update_skill_cards(user_id, cards)

def remove_skill_card(user_id: int, card_name: str):
    """Удаляет одну карту суперспособности у пользователя."""
    cards = get_skill_cards(user_id)
    if card_name in cards:
        del cards[card_name]
        update_skill_cards(user_id, cards)


def add_balance(user_id: int, amount: int) -> int:
    """Add amount to user's balance and return new balance."""
    # Coerce amount to integer (if a float or numeric string was passed)
    try:
        amount = int(amount)
    except Exception:
        try:
            amount = int(float(amount))
        except Exception:
            amount = 0

    with connect() as conn:
        cur = conn.cursor()
        # Perform an atomic update: always update balance, and only increment
        # balance_all_time when amount > 0. Using a single statement avoids
        # races where two concurrent updates could produce incorrect totals.
        try:
            cur.execute(
                """
                UPDATE users
                SET balance = balance + ?,
                    balance_all_time = balance_all_time + CASE WHEN ? > 0 THEN ? ELSE 0 END
                WHERE user_id = ?
                """,
                (amount, amount, amount, user_id)
            )
        except Exception:
            # If the column doesn't exist or another DB issue occurs, fall back
            # to updating only the balance (preserve previous behavior).
            try:
                cur.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
            except Exception:
                # give up silently to avoid crashing the bot; caller can log if needed
                pass

        conn.commit()
        cur.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        return int(row[0]) if row and row[0] is not None else 0

def get_all_user_ids():
    conn = connect()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    user_ids = [row[0] for row in cursor.fetchall()]
    conn.close()
    return user_ids








# === RARITY ===
def get_card_drop_counts(user_id: int) -> dict[str, int]:
    """Получить словарь {card_name: drops_count} для пользователя."""
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT card_name, drops_count FROM user_card_drops WHERE user_id = ?", (user_id,))
        rows = cur.fetchall()
    return {row["card_name"]: row["drops_count"] for row in rows}

def increment_card_drop(user_id: int, card_name: str):
    """Увеличить счётчик выпадений карты для пользователя."""
    with connect() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT drops_count FROM user_card_drops WHERE user_id = ? AND card_name = ?",
            (user_id, card_name)
        )
        row = cur.fetchone()
        if row:
            cur.execute(
                "UPDATE user_card_drops SET drops_count = drops_count + 1 WHERE user_id = ? AND card_name = ?",
                (user_id, card_name)
            )
        else:
            cur.execute(
                "INSERT INTO user_card_drops (user_id, card_name, drops_count) VALUES (?, ?, 1)",
                (user_id, card_name)
            )
        conn.commit()







# === ROULETTE ===
def load_roulette_data(user_id: int) -> dict:
    with connect() as conn:
        cur = conn.cursor()
        row = cur.execute("SELECT * FROM roulette_user WHERE user_id = ?", (user_id,)).fetchone()
        if not row:
            now = datetime.datetime.utcnow().isoformat()
            cur.execute("""
                INSERT INTO roulette_user (user_id, roulette_count, opened_today, total_opened, last_reset, last_increment, notified_max, meow_count, meow_count_all, jopa_count, kazino_upgrades, fire_points, upgrade_timer_reduce, has_double_casino, has_fast_spin, dopa_bet)
                VALUES (?, 5, 0, 0, '', ?, 0, 0, 0, 0, '{}', 0, 0, 0, 0, 0)
            """, (user_id, now))
            conn.commit()
            row = cur.execute("SELECT * FROM roulette_user WHERE user_id = ?", (user_id,)).fetchone()

        history = cur.execute("SELECT entry FROM roulette_history WHERE user_id = ? ORDER BY ts DESC LIMIT 10", (user_id,))
        return {
            "roulette_count": row["roulette_count"],
            "opened_today": row["opened_today"],
            "total_opened": row["total_opened"],
            "last_reset": row["last_reset"],
            "last_increment": row["last_increment"],
            "notified_max": bool(row["notified_max"]),
            "meow_count": row["meow_count"],
            "meow_count_all": row["meow_count_all"],
            "jopa_count": row["jopa_count"],
            "kazino_upgrades": json.loads(row["kazino_upgrades"]) if row["kazino_upgrades"] else {},
            "history": [r["entry"] for r in history.fetchall()],
            "fire_points": row["fire_points"],
            "upgrade_timer_reduce": row["upgrade_timer_reduce"],
            "has_double_casino": bool(row["has_double_casino"]),
            "has_fast_spin": bool(row["has_fast_spin"]),
            "dopa_bet": row["dopa_bet"]
        }

def save_roulette_data(user_id: int, data: dict):
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO roulette_user (user_id, roulette_count, opened_today, total_opened, last_reset, last_increment, notified_max, meow_count, meow_count_all, jopa_count, kazino_upgrades, fire_points, upgrade_timer_reduce, has_double_casino, has_fast_spin, dopa_bet)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                roulette_count = excluded.roulette_count,
                opened_today = excluded.opened_today,
                total_opened = excluded.total_opened,
                last_reset = excluded.last_reset,
                last_increment = excluded.last_increment,
                notified_max = excluded.notified_max,
                meow_count = excluded.meow_count,
                meow_count_all = excluded.meow_count_all,
                jopa_count = excluded.jopa_count,
                kazino_upgrades = excluded.kazino_upgrades,
                fire_points = excluded.fire_points,
                upgrade_timer_reduce = excluded.upgrade_timer_reduce,
                has_double_casino = excluded.has_double_casino,
                has_fast_spin = excluded.has_fast_spin,
                dopa_bet = excluded.dopa_bet
        """, (
            user_id,
            int(data.get("roulette_count", 5)),
            int(data.get("opened_today", 0)),
            int(data.get("total_opened", 0)),
            data.get("last_reset", ""),
            data.get("last_increment", datetime.datetime.utcnow().isoformat()),
            1 if data.get("notified_max", False) else 0,
            int(data.get("meow_count", 0)),
            int(data.get("meow_count_all", 0)),
            int(data.get("jopa_count", 0)),
            json.dumps(data.get("kazino_upgrades", {})),
            int(data.get("fire_points", 0)),
            int(data.get("upgrade_timer_reduce", 0)),
            1 if data.get("has_double_casino", False) else 0,
            1 if data.get("has_fast_spin", False) else 0,
            int(data.get("dopa_bet", 0))
        )
        )
        conn.commit()

def append_roulette_history(user_id: int, entry: str):
    with connect() as conn:
        conn.execute("INSERT INTO roulette_history (user_id, entry) VALUES (?, ?)", (user_id, entry))

def get_roulette_history(user_id: int, limit: int = 10) -> list[str]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT entry FROM roulette_history WHERE user_id = ? ORDER BY ts DESC LIMIT ?", (user_id, limit)
        ).fetchall()
        return [r["entry"] for r in rows]



























# АДМИНЫ

def is_admin(user_id: int) -> bool:
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


# ===== PRESAVE FUNCTIONS =====

def add_presave_action(user_id: int, pressed_at: int) -> None:
    """Записывает или обновляет действие пресейва для пользователя."""
    with connect() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT OR REPLACE INTO presave_actions (user_id, pressed_at, rewarded, screenshot_file_id) VALUES (?, ?, 0, NULL)",
            (user_id, pressed_at)
        )
        conn.commit()

def get_presave_action(user_id: int) -> dict | None:
    """Возвращает информацию о действии пресейва пользователя."""
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT pressed_at, rewarded, screenshot_file_id FROM presave_actions WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        if row:
            return {"pressed_at": row[0], "rewarded": bool(row[1]), "screenshot_file_id": row[2]}
        return None

def update_presave_screenshot(user_id: int, screenshot_file_id: str) -> None:
    """Сохраняет file_id скриншота для пользователя."""
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE presave_actions SET screenshot_file_id = ? WHERE user_id = ?", (screenshot_file_id, user_id))
        conn.commit()

def mark_presave_rewarded(user_id: int) -> None:
    """Отмечает, что награда за пресейв уже выдана."""
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE presave_actions SET rewarded = 1 WHERE user_id = ?", (user_id,))
        conn.commit()

def delete_presave_action(user_id: int) -> None:
    """Удаляет запись о действии пресейва пользователя."""
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM presave_actions WHERE user_id = ?", (user_id,))
        conn.commit()

def get_unrewarded_presave_actions() -> list[dict]:
    """Возвращает список пользователей, которые нажали кнопку, но ещё не получили награду."""
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT user_id, pressed_at, screenshot_file_id FROM presave_actions WHERE rewarded = 0 AND screenshot_file_id IS NOT NULL")
        rows = cur.fetchall()
        return [{"user_id": row[0], "pressed_at": row[1], "screenshot_file_id": row[2]} for row in rows]


# ==================== ФУНКЦИИ ДЛЯ СИСТЕМЫ ОБМЕНА ====================

def find_user_by_username(username: str) -> dict | None:
    """Ищет пользователя по username (без @)."""
    username = username.lstrip('@')
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT user_id, username FROM users WHERE username = ?", (username,))
        row = cur.fetchone()
        if row:
            return {"user_id": row[0], "username": row[1]}
        return None

def get_user_full_data(user_id: int) -> dict | None:
    """Получает полные данные пользователя по user_id."""
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT user_id, username, first_name, last_name FROM users WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        if row:
            return {"user_id": row[0], "username": row[1], "first_name": row[2], "last_name": row[3]}
        return None


def create_exchange_offer(
    from_user_id: int,
    to_user_id: int,
    from_user_username: str,
    to_user_username: str,
    offered_card_type: str,
    offered_card_name: str,
    requested_card_type: str,
    requested_card_name: str
) -> int:
    """Создает предложение обмена и возвращает его ID."""
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO exchange_offers (
                from_user_id, to_user_id, from_user_username, to_user_username,
                offered_card_type, offered_card_name,
                requested_card_type, requested_card_name,
                status, created_at, expires_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', datetime('now'), datetime('now', '+1 day'))
        """, (
            from_user_id, to_user_id, from_user_username, to_user_username,
            offered_card_type, offered_card_name,
            requested_card_type, requested_card_name
        ))
        conn.commit()
        return cur.lastrowid


def get_exchange_offer(offer_id: int) -> dict | None:
    """Получает предложение обмена по ID."""
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT * FROM exchange_offers WHERE id = ?
        """, (offer_id,))
        row = cur.fetchone()
        if row:
            return dict(row)
        return None


def get_pending_offers_to_user(user_id: int) -> list[dict]:
    """Получает все активные входящие предложения для пользователя."""
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT * FROM exchange_offers 
            WHERE to_user_id = ? AND status = 'pending' 
            ORDER BY created_at DESC
        """, (user_id,))
        rows = cur.fetchall()
        return [dict(row) for row in rows]


def get_pending_offers_from_user(user_id: int) -> list[dict]:
    """Получает все активные исходящие предложения от пользователя."""
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT * FROM exchange_offers 
            WHERE from_user_id = ? AND status = 'pending' 
            ORDER BY created_at DESC
        """, (user_id,))
        rows = cur.fetchall()
        return [dict(row) for row in rows]


def update_exchange_offer_status(offer_id: int, status: str) -> None:
    """Обновляет статус предложения обмена."""
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("""
            UPDATE exchange_offers SET status = ? WHERE id = ?
        """, (status, offer_id))
        conn.commit()


def set_exchange_offer_message_id(offer_id: int, message_id: int) -> None:
    """Сохраняет ID сообщения с предложением обмена."""
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("""
            UPDATE exchange_offers SET message_id = ? WHERE id = ?
        """, (message_id, offer_id))
        conn.commit()


def add_exchange_to_history(
    offer_id: int,
    from_user_id: int,
    to_user_id: int,
    from_user_username: str,
    to_user_username: str,
    exchanged_card_type: str,
    exchanged_card_name: str,
    received_card_type: str,
    received_card_name: str
) -> None:
    """Добавляет запись об успешном обмене в историю."""
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO exchange_history (
                offer_id, from_user_id, to_user_id, from_user_username, to_user_username,
                exchanged_card_type, exchanged_card_name,
                received_card_type, received_card_name,
                exchanged_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """, (
            offer_id, from_user_id, to_user_id, from_user_username, to_user_username,
            exchanged_card_type, exchanged_card_name,
            received_card_type, received_card_name
        ))
        conn.commit()


def get_user_exchange_history(user_id: int, limit: int = 10) -> list[dict]:
    """Получает историю обменов пользователя."""
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT * FROM exchange_history 
            WHERE from_user_id = ? OR to_user_id = ?
            ORDER BY exchanged_at DESC
            LIMIT ?
        """, (user_id, user_id, limit))
        rows = cur.fetchall()
        return [dict(row) for row in rows]


def cleanup_expired_exchange_offers() -> int:
    """Удаляет просроченные предложения обмена. Возвращает количество удаленных."""
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("""
            DELETE FROM exchange_offers 
            WHERE status = 'pending' AND expires_at < datetime('now')
        """)
        conn.commit()
        return cur.rowcount


def init_exchange_tables():
    """Инициализирует таблицы для системы обмена."""
    with connect() as conn:
        cur = conn.cursor()
        
        # Таблица предложений обмена
        cur.execute("""
            CREATE TABLE IF NOT EXISTS exchange_offers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_user_id INTEGER NOT NULL,
                to_user_id INTEGER NOT NULL,
                from_user_username TEXT NOT NULL,
                to_user_username TEXT NOT NULL,
                offered_card_type TEXT NOT NULL,
                offered_card_name TEXT NOT NULL,
                requested_card_type TEXT NOT NULL,
                requested_card_name TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                message_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                FOREIGN KEY (from_user_id) REFERENCES users(user_id),
                FOREIGN KEY (to_user_id) REFERENCES users(user_id)
            )
        """)
        
        # Таблица истории обменов
        cur.execute("""
            CREATE TABLE IF NOT EXISTS exchange_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                offer_id INTEGER,
                from_user_id INTEGER NOT NULL,
                to_user_id INTEGER NOT NULL,
                from_user_username TEXT NOT NULL,
                to_user_username TEXT NOT NULL,
                exchanged_card_type TEXT NOT NULL,
                exchanged_card_name TEXT NOT NULL,
                received_card_type TEXT NOT NULL,
                received_card_name TEXT NOT NULL,
                exchanged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (offer_id) REFERENCES exchange_offers(id)
            )
        """)
        
        conn.commit()
