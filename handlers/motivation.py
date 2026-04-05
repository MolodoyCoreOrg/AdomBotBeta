import asyncio, json, os, random, datetime

from aiogram import Router, types, F, Bot, Dispatcher
from aiogram.utils.keyboard import InlineKeyboardBuilder, InlineKeyboardButton
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton
from aiogram.exceptions import TelegramBadRequest
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from database.db import add_skill_bonus, add_member_bonus, load_roulette_data, save_roulette_data, append_roulette_history, get_all_user_ids
from utils.helpers import format_time_left, get_combo_text, safe_edit_message, safe_delete
from utils.config import TOKEN

router = Router()

# Debounce settings for editing the motivation message to avoid edit flood
MOTIVATION_EDIT_DEBOUNCE = 10.0  # seconds
_mot_last_edit_ts: float = 0.0
_mot_pending_task: "asyncio.Task | None" = None

def motivation_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="😎 ПОДНЯТЬ МОТИВАЦИЮ!", callback_data="motivation_up"),
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="go_back_menu"),
    )
    return builder.as_markup()

@router.callback_query(F.data == "motivation_menu")
async def show_motivation_menu(callback: CallbackQuery):
    await callback.message.answer(f"У разработчика последний год в школе и ему предстоит сдавать экзамены. Ему крайне не хватает времени на разработку бота, ведь бота он пишет в свободное время и в одниночку. Вы можете нажать на кнопку ниже чтобы проявить активность в боте, чтобы разработчик видел насколько сильно вы хотите новых обновлений. У нас очень большие планы на бота, вы не представляете какие приколюхи у него будут в будущем\n\n"
                                  f"Количество нажатий: [{json.load(open('data/cards/motivation.json'))['click_count']}]"
                                  , reply_markup=motivation_keyboard())
    
@router.callback_query(F.data == "motivation_up")
async def motivation_up(callback: CallbackQuery):
    # Load and update click counter safely
    mot_file = 'data/cards/motivation.json'
    try:
        with open(mot_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        data = {'click_count': 0}

    data['click_count'] = int(data.get('click_count', 0)) + 1

    try:
        with open(mot_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception:
        # non-fatal: continue even if we can't persist the counter
        pass

    # If we've reached a multiple of 100 clicks, award +1 roulette spin to all users
    if data.get('click_count', 0) % 100 == 0:
        try:
            user_ids = get_all_user_ids() or []
        except Exception:
            user_ids = []

        given = 0
        for uid in user_ids:
            try:
                rd = load_roulette_data(uid)
                rd['roulette_count'] = int(rd.get('roulette_count', 0)) + 1
                save_roulette_data(uid, rd)
                # append a short history entry for this award
                try:
                    append_roulette_history(uid, f"motivation_bonus:+1")
                except Exception:
                    pass
                given += 1
            except Exception:
                # keep going on error for individual users
                continue

        # Notify the clicking user (alert) about the broadcast bonus
        try:
            await callback.answer(f"🎉 Достигнуто {data['click_count']} нажатий — всем выдано по 1 крутке ({given} пользователей).", show_alert=True)
        except Exception:
            # fallback to non-alert answer
            try:
                await callback.answer()
            except Exception:
                pass

    else:
        try:
            await callback.answer("Спасибо за поддержку! Разработчик очень ценит вашу активность и поддержку!", show_alert=True)
        except Exception:
            pass

    # Update the displayed message with new count
    # Debounced edit to avoid frequent edits
    try:
        # If enough time passed since last edit, edit immediately.
        now = asyncio.get_event_loop().time()
        global _mot_last_edit_ts, _mot_pending_task
        elapsed = now - _mot_last_edit_ts
        if elapsed >= MOTIVATION_EDIT_DEBOUNCE:
            try:
                await safe_edit_message(callback.message, f"У разработчика последний год в школе и ему предстоит сдавать экзамены. Ему крайне не хватает времени на разработку бота, ведь бота он пишет в свободное время и в одниночку. Вы можете нажать на кнопку ниже чтобы проявить активность в боте, чтобы разработчик видел насколько сильно вы хотите новых обновлений. У нас очень большие планы на бота, вы не представляете какие приколюхи у него будут в будущем\n\n"
                                              f"Количество нажатий: [{data['click_count']}]"
                                              , reply_markup=motivation_keyboard())
                _mot_last_edit_ts = asyncio.get_event_loop().time()
            except Exception:
                # ignore editing errors
                pass
        else:
            # schedule a delayed edit if not already scheduled
            if _mot_pending_task is None or _mot_pending_task.done():
                delay = MOTIVATION_EDIT_DEBOUNCE - elapsed

                async def _delayed_edit(delay_sec: float, msg):
                    try:
                        await asyncio.sleep(delay_sec)
                        # reload latest count from file to ensure accuracy
                        mot_file_local = 'data/cards/motivation.json'
                        try:
                            with open(mot_file_local, 'r', encoding='utf-8') as f:
                                latest = json.load(f)
                        except Exception:
                            latest = {'click_count': data.get('click_count', 0)}
                        try:
                            await safe_edit_message(msg, f"У разработчика последний год в школе и ему предстоит сдавать экзамены. Ему крайне не хватает времени на разработку бота, ведь бота он пишет в свободное время и в одниночку. Вы можете нажать на кнопку ниже чтобы проявить активность в боте, чтобы разработчик видел насколько сильно вы хотите новых обновлений. У нас очень большие планы на бота, вы не представляете какие приколюхи у него будут в будущем\n\n"
                                                              f"Количество нажатий: [{latest.get('click_count', 0)}]"
                                                              , reply_markup=motivation_keyboard())
                        except Exception:
                            pass
                        finally:
                            # update module-level last edit timestamp
                            global _mot_last_edit_ts
                            _mot_last_edit_ts = asyncio.get_event_loop().time()
                    except asyncio.CancelledError:
                        return

                _mot_pending_task = asyncio.create_task(_delayed_edit(delay, callback.message))
    except Exception:
        # ensure handler doesn't crash due to debounce logic
        pass
    
