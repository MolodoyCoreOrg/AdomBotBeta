import os
import tempfile
import unittest
import uuid

from database import db
from handlers import menu


class StartConfirmationTests(unittest.TestCase):
    def setUp(self):
        self.db_path = os.path.join(
            tempfile.gettempdir(),
            f"test_start_confirmation_{uuid.uuid4().hex}.db",
        )
        db.DB_PATH = self.db_path
        menu.DB_PATH = self.db_path
        db.create_users_table()

    def tearDown(self):
        for extra_path in [self.db_path, self.db_path + "-wal", self.db_path + "-shm"]:
            if os.path.exists(extra_path):
                try:
                    os.remove(extra_path)
                except PermissionError:
                    pass

    def test_finalize_registration_counts_referral_only_after_confirmation(self):
        db.add_user(1, "ref", "Ref", "Ref")

        menu.finalize_registration(
            user_id=2,
            username="new",
            first_name="New",
            last_name="User",
            referrer_id=1,
        )

        self.assertTrue(db.user_exists(2))
        row = db.connect().execute(
            "SELECT total_invited FROM users WHERE user_id = ?",
            (1,),
        ).fetchone()
        self.assertEqual(row[0], 0)

        db.confirm_pending_referrer(2)

        row = db.connect().execute(
            "SELECT total_invited FROM users WHERE user_id = ?",
            (1,),
        ).fetchone()
        self.assertEqual(row[0], 1)


if __name__ == "__main__":
    unittest.main()
