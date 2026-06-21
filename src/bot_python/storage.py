import json
import os
import datetime
from typing import Dict, List, Optional, Tuple

class JSONRecountStorage:
    def __init__(self, file_path: str = "recount_data.json", max_slots: int = 100):
        self.file_path = file_path
        self.max_slots = max_slots
        self.data = self._load_data()

    def _load_data(self) -> dict:
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if "users" not in data:
                        data["users"] = {}
                    if "slots" not in data:
                        data["slots"] = {}
                    if "check_ins" not in data:
                        data["check_ins"] = {}
                    return data
            except Exception as e:
                print(f"Ошибка при загрузке JSON: {e}. Инициализируем новую базу.")
        
        return {
            "users": {},      # user_id (str) -> {id, username, first_name, last_name, slot, registered_at}
            "slots": {},      # slot_number (str) -> user_id
            "check_ins": {}   # date_str -> list of user_ids (str)
        }

    def _save_data(self):
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Ошибка сохранения JSON: {e}")

    def get_user(self, user_id: int) -> Optional[dict]:
        user_id_str = str(user_id)
        return self.data["users"].get(user_id_str)

    def get_all_users(self) -> List[dict]:
        return list(self.data["users"].values())

    def choose_slot(self, user_id: int, username: Optional[str], first_name: str, last_name: Optional[str], slot_number: int) -> Tuple[bool, Optional[str]]:
        if slot_number < 1 or slot_number > self.max_slots:
            return False, f"Номер должен быть от 1 до {self.max_slots}!"

        user_id_str = str(user_id)
        slot_str = str(slot_number)

        # Check if user already has a slot
        user = self.get_user(user_id)
        if user and user.get("slot_number") is not None:
            return False, f"Вы уже выбрали номер — это Пидараз {user['slot_number']}. Изменить его нельзя!"

        # Check if slot already taken
        taken_by = self.data["slots"].get(slot_str)
        if taken_by and taken_by != user_id_str:
            return False, f"Номер {slot_number} уже занят другим пидаразом!"

        # Process reservation
        now_str = datetime.datetime.now().isoformat()
        user_info = {
            "id": user_id,
            "username": username,
            "first_name": first_name,
            "last_name": last_name,
            "slot_number": slot_number,
            "registered_at": now_str
        }

        self.data["users"][user_id_str] = user_info
        self.data["slots"][slot_str] = user_id_str
        self._save_data()

        return True, None

    def record_check_in(self, user_id: int, date_str: str) -> bool:
        """
        Record morning presence check-in. Returns True if recorded successfully, 
        False if user not found, or already checked in today.
        """
        user_id_str = str(user_id)
        user = self.get_user(user_id)
        if not user or user.get("slot_number") is None:
            return False

        if date_str not in self.data["check_ins"]:
            self.data["check_ins"][date_str] = []

        if user_id_str not in self.data["check_ins"][date_str]:
            self.data["check_ins"][date_str].append(user_id_str)
            self._save_data()
            return True

        return False

    def get_check_ins(self, date_str: str) -> List[int]:
        user_id_strs = self.data["check_ins"].get(date_str, [])
        return [int(uid) for uid in user_id_strs]

    def get_slots(self, limit: int = 100) -> List[dict]:
        slots_list = []
        for i in range(1, limit + 1):
            slot_str = str(i)
            user_id_str = self.data["slots"].get(slot_str)
            slots_list.append({
                "number": i,
                "user_id": int(user_id_str) if user_id_str else None
            })
        return slots_list
