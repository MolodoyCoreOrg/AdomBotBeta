import json
import os
import sqlite3
import unittest

from database import db
from handlers.cards_handler.skills import award_skill_to_user


class AdminSkillAwardTests(unittest.TestCase):
    def setUp(self):
        self.db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "database", "test_admin_skill_award.db")
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

        db.DB_PATH = self.db_path
        db.create_users_table()

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO users (user_number, user_id, username, first_name, last_name, skill_cards) VALUES (?, ?, ?, ?, ?, ?)",
                (1, 777, "target_user", "Target", "User", "{}"),
            )
            conn.commit()

    def tearDown(self):
        try:
            import gc
            gc.collect()
        except Exception:
            pass
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
            except PermissionError:
                pass

    def test_award_skill_to_user_adds_known_card(self):
        ok, message = award_skill_to_user(777, "дебик")

        self.assertTrue(ok)
        self.assertIn("выдана", message.lower())

        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("SELECT skill_cards FROM users WHERE user_id = ?", (777,)).fetchone()
            self.assertIsNotNone(row)
            cards = json.loads(row[0])
            self.assertIn("дебик", cards)


if __name__ == "__main__":
    unittest.main()
