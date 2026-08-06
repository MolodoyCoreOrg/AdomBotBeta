import os
import tempfile
import unittest
import uuid

from database import db
from handlers.admin import admin_GG


class PidarazStreakTests(unittest.TestCase):
    def setUp(self):
        self.db_path = os.path.join(
            tempfile.gettempdir(),
            f"test_pidaraz_streaks_{uuid.uuid4().hex}.db",
        )
        db.DB_PATH = self.db_path
        admin_GG.DB_PATH = self.db_path
        db.create_pidaraz_table()

    def tearDown(self):
        for extra_path in [self.db_path, self.db_path + "-wal", self.db_path + "-shm"]:
            if os.path.exists(extra_path):
                try:
                    os.remove(extra_path)
                except PermissionError:
                    pass

    def test_mark_pidaraz_confirmed_tracks_streaks(self):
        ok, _ = db.claim_pidaraz_number(777, 7, "tester", "Tester")
        self.assertTrue(ok)

        db.mark_pidaraz_confirmed(777, "2024-01-01")
        stats = db.get_pidaraz_stats(777)
        self.assertEqual(stats["streak_current"], 1)
        self.assertEqual(stats["best_streak"], 1)

        db.mark_pidaraz_confirmed(777, "2024-01-02")
        stats = db.get_pidaraz_stats(777)
        self.assertEqual(stats["streak_current"], 2)
        self.assertEqual(stats["best_streak"], 2)

        db.mark_pidaraz_confirmed(777, "2024-01-04")
        stats = db.get_pidaraz_stats(777)
        self.assertEqual(stats["streak_current"], 1)
        self.assertEqual(stats["best_streak"], 2)

    def test_mark_pidaraz_confirmed_resets_streak_after_a_gap(self):
        ok, _ = db.claim_pidaraz_number(888, 8, "tester2", "Tester2")
        self.assertTrue(ok)

        db.mark_pidaraz_confirmed(888, "2024-01-01")
        db.mark_pidaraz_confirmed(888, "2024-01-02")
        db.mark_pidaraz_confirmed(888, "2024-01-04")

        stats = db.get_pidaraz_stats(888)
        self.assertEqual(stats["streak_current"], 1)
        self.assertEqual(stats["best_streak"], 2)

    def test_delete_pidaraz_slot_removes_registry_and_confirmations(self):
        ok, _ = db.claim_pidaraz_number(999, 9, "tester3", "Tester3")
        self.assertTrue(ok)

        db.mark_pidaraz_confirmed(999, "2024-01-01")

        deleted = admin_GG.delete_pidaraz_slot(9)

        self.assertTrue(deleted)
        self.assertIsNone(db.get_pidaraz_number(999))
        self.assertEqual(db.get_pidaraz_stats(999)["streak_current"], 0)
        self.assertEqual(db.get_pidaraz_stats(999)["best_streak"], 0)


if __name__ == "__main__":
    unittest.main()
