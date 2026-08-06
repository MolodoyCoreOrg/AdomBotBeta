import os
import sqlite3
from database import db
from handlers.cards_handler.skills import award_skill_to_user

path = os.path.join(os.getcwd(), 'database', 'test_admin_skill_award.db')
if os.path.exists(path):
    os.remove(path)

db.DB_PATH = path
db.create_users_table()
with sqlite3.connect(path) as conn:
    conn.execute(
        'INSERT INTO users (user_number, user_id, username, first_name, last_name, skill_cards) VALUES (?, ?, ?, ?, ?, ?)',
        (1, 777, 'target_user', 'Target', 'User', '{}')
    )
    conn.commit()

ok, msg = award_skill_to_user(777, 'дебик')
print(ok, msg)
with sqlite3.connect(path) as conn:
    row = conn.execute('SELECT skill_cards FROM users WHERE user_id = ?', (777,)).fetchone()
    print(row[0])

if os.path.exists(path):
    os.remove(path)
