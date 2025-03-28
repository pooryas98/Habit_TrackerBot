from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from typing import List, Tuple

from . import localization as lang
from . import constants as c # Import constants

def today_habits_keyboard(habits_with_status: List[Tuple[int, str, str]]) -> InlineKeyboardMarkup:
    """Generates keyboard for today's habits with 'Done' buttons."""
    keyboard = []
    for habit_id, habit_name, status in habits_with_status:
        if status == 'pending':
            button_text = f"{habit_name} ({lang.BUTTON_MARK_DONE})"
            # Use constant for callback prefix
            callback_data = f"{c.CALLBACK_MARK_DONE}{habit_id}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
        else:
            # Show completed habits with a checkmark, unclickable
            button_text = f"✅ {habit_name}"
            callback_data = f"{c.CALLBACK_NOOP}{habit_id}" # Use noop prefix
            keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
    return InlineKeyboardMarkup(keyboard)

def reminder_management_keyboard(reminders: List[Tuple[int, str, str]]) -> InlineKeyboardMarkup:
    """Generates keyboard to delete reminders."""
    keyboard = []
    for habit_id, habit_name, time_str in reminders:
        button_text = f"{habit_name} ({time_str}) - {lang.BUTTON_DELETE_REMINDER}"
        # Use constant for callback prefix
        callback_data = f"{c.CALLBACK_DELETE_REMINDER}{habit_id}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
    if not keyboard: # Handle case where input list might be empty after filtering
         return InlineKeyboardMarkup([])
    return InlineKeyboardMarkup(keyboard)

def select_habit_keyboard(habits: List[Tuple[int, str, str | None, str | None]], callback_prefix: str) -> List[List[InlineKeyboardButton]]:
    """Generates rows of buttons for selecting a habit."""
    keyboard_rows = []
    for habit_id, habit_name, _, _ in habits:
        # Use provided prefix + habit_id
        callback_data = f"{callback_prefix}{habit_id}"
        keyboard_rows.append([InlineKeyboardButton(habit_name, callback_data=callback_data)])
    return keyboard_rows

def yes_no_keyboard(yes_callback: str, no_callback: str) -> InlineKeyboardMarkup:
    """Generates a simple Yes/No confirmation keyboard."""
    keyboard = [[
        InlineKeyboardButton(lang.BUTTON_YES, callback_data=yes_callback),
        InlineKeyboardButton(lang.BUTTON_NO, callback_data=no_callback),
    ]]
    return InlineKeyboardMarkup(keyboard)
