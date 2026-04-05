import os, json

from aiogram.exceptions import TelegramBadRequest
from aiogram import types
from datetime import datetime, timezone
try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

def format_iso_utc_to_user_tz(iso_ts: str, user_tz: str | None = None) -> str:
    """Convert ISO UTC timestamp to user's timezone and return human-friendly string.

    - iso_ts: ISO formatted UTC datetime (e.g. 2025-08-18T12:34:56.123456)
    - user_tz: IANA timezone string (e.g. 'Europe/Moscow'). If None or invalid, falls back to UTC.
    """
    if not iso_ts:
        return "неизвестна (до обновления)"
    try:
        dt = datetime.fromisoformat(iso_ts)
    except Exception:
        return iso_ts

    # assume stored as UTC
    try:
        dt_utc = dt.replace(tzinfo=ZoneInfo('UTC')) if ZoneInfo else dt
    except Exception:
        dt_utc = dt

    if user_tz and ZoneInfo:
        try:
            tz = ZoneInfo(user_tz)
            dt_local = dt_utc.astimezone(tz)
            return dt_local.strftime("%Y-%m-%d %H:%M %Z")
        except Exception:
            pass

    # fallback to UTC display
    try:
        return dt_utc.strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return iso_ts

async def safe_answer(callback: types.CallbackQuery, text: str = None, show_alert: bool = False):
    try:
        await callback.answer(text=text, show_alert=show_alert)
    except TelegramBadRequest as e:
        if "query is too old" not in str(e):
            raise


async def safe_delete(obj):
    """Safely delete a message-like object (Message, CallbackQuery.message, or Inline message target).

    Accepts objects that have an async .delete() method or a .message with .delete().
    Swallows common Telegram errors (forbidden, message not found, etc.).
    """
    try:
        # If it's a CallbackQuery, prefer deleting callback.message
        if isinstance(obj, types.CallbackQuery):
            target = getattr(obj, 'message', None)
            if target:
                await target.delete()
            else:
                # nothing to delete
                return
        else:
            # attempt direct delete
            delete_coro = getattr(obj, 'delete', None)
            if delete_coro:
                await delete_coro()
            else:
                # maybe it's a wrapper with message attribute
                target = getattr(obj, 'message', None)
                if target:
                    await target.delete()
    except TelegramBadRequest as e:
        # swallow common delete errors
        msg = str(e)
        if any(substr in msg for substr in ("message to delete not found", "message is not modified", "bot was blocked by the user", "chat not found", "message can't be deleted")):
            return
        # if it's some other TelegramBadRequest, ignore too — we don't want bot to crash on restart
        return
    except Exception:
        # ignore any other errors during delete to avoid crash after restarts
        return










def format_time_left(seconds: float) -> str:
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    hours = minutes // 60
    minutes = minutes % 60

    parts = []
    if hours > 0:
        parts.append(f"{hours} ч")
    if minutes > 0:
        parts.append(f"{minutes} мин")
    if hours == 0 and minutes == 0:
        parts.append(f"{secs} сек")

    return " ".join(parts)



# === CASINO ===
def get_combo_text(dice_value: int):
    values = ["BAR", "виноград", "лимон", "семь"]
    dice_value -= 1
    result = []
    for _ in range(3):
        result.append(values[dice_value % 4])
        dice_value //= 4
    return result




# === IMAGE PATH MEMBERS CARD ===
def get_member_card_image_path(card_data: dict, card_info: dict) -> str:
    """
    Получает путь к изображению карточки участника в зависимости от ранга.
    """
    rank = max(1, min(card_data.get("rank", 1), 4))  # Защита от выхода за диапазон

    image_filename = card_info.get("image")
    if not image_filename:
        return None

    image_path = os.path.join(
        "data/images/members",
        f"rank_{rank}",
        image_filename
    )

    if not os.path.exists(image_path):
        # fallback на rank_1
        fallback_path = os.path.join("data/images/members", "rank_1", image_filename)
        return fallback_path if os.path.exists(fallback_path) else None

    return image_path

















def get_timer_status(user_id: int, file_path: str, label: str) -> str:
    """Возвращает статус таймера (доступно или через N часов)."""
    status = f"{label}: Доступно ✅"
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            timers = json.load(f)

        user_key = str(user_id)
        if user_key in timers:
            can_open_after_str = timers[user_key].get("can_open_after")
            if can_open_after_str:
                # читаем дату и делаем её aware (UTC)
                can_open_after = datetime.fromisoformat(can_open_after_str).replace(tzinfo=timezone.utc)
                now = datetime.now(timezone.utc)

                if now < can_open_after:
                    delta = can_open_after - now
                    hours_left = int(delta.total_seconds() // 3600)
                    status = f"{label}: через {hours_left} часов"
    except FileNotFoundError:
        pass
    return status






async def safe_edit_message(message, new_text: str, reply_markup=None):
    try:
        # If the message object's .text differs from new_text, try to edit.
        # For media messages .text is usually None. Trying to edit a media
        # message's text may raise a TelegramBadRequest: "there is no text in
        # the message to edit". We handle that below.
        if getattr(message, 'text', None) != new_text:
            await message.edit_text(new_text, reply_markup=reply_markup)
        elif reply_markup is not None:
            # Sometimes it's enough to update only the keyboard
            await message.edit_reply_markup(reply_markup=reply_markup)
    except Exception as e:
        err = str(e)
        # Ignore 'message is not modified' — not an error
        if "message is not modified" in err:
            return

        # If there's no text in the message (media message), try safe fallback:
        if "there is no text in the message to edit" in err or "no text in the message to edit" in err:
            try:
                # delete old message (if possible) and send a fresh text message
                await safe_delete(message)
                # send a new message to the same chat
                try:
                    await message.answer(new_text, reply_markup=reply_markup)
                except Exception:
                    # last resort — do nothing
                    return
            except Exception:
                return

        # For other errors, just log them (don't re-raise to avoid crash)
        else:
            print(f"Ошибка при редактировании: {e}")