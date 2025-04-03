from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from typing import List, Tuple, Optional
from . import localization as lang, constants as c

def today_habits_keyboard(habits: List[Tuple[int, str, str]]) -> InlineKeyboardMarkup:
    """Keyboard for /today: mark pending habits done."""
    kbd = [[InlineKeyboardButton(f"{'✅ ' if status == 'done' else ''}{name}{f' ({lang.BUTTON_MARK_DONE})' if status == 'pending' else ''}",
                               callback_data=f"{c.CALLBACK_MARK_DONE if status == 'pending' else c.CALLBACK_NOOP}{hid}")]
           for hid, name, status in habits]
    return InlineKeyboardMarkup(kbd)

def reminder_management_keyboard(reminders: List[Tuple[int, str, str]]) -> InlineKeyboardMarkup:
    """Keyboard for /manage_reminders: delete buttons."""
    kbd = [[InlineKeyboardButton(f"{name} ({time_str}) - {lang.BUTTON_DELETE_REMINDER}", callback_data=f"{c.CALLBACK_DELETE_REMINDER}{hid}")]
           for hid, name, time_str in reminders]
    return InlineKeyboardMarkup(kbd)

def select_habit_keyboard(habits: List[Tuple[int, str, Optional[str], Optional[str]]], cb_prefix: str) -> List[List[InlineKeyboardButton]]:
    """Generic habit selection keyboard rows."""
    return [[InlineKeyboardButton(name, callback_data=f"{cb_prefix}{hid}")] for hid, name, _, _ in habits]

def yes_no_keyboard(yes_cb: str, no_cb: str) -> InlineKeyboardMarkup:
    """Simple Yes/No confirmation keyboard."""
    return InlineKeyboardMarkup([[InlineKeyboardButton(lang.BUTTON_YES, callback_data=yes_cb), InlineKeyboardButton(lang.BUTTON_NO, callback_data=no_cb)]])

def history_pagination_keyboard(offset: int, total: int, limit: int) -> Optional[InlineKeyboardMarkup]:
    """Pagination keyboard for /history."""
    btns = []
    if offset > 0: btns.append(InlineKeyboardButton(lang.BUTTON_PREVIOUS, callback_data=f"{c.CALLBACK_HISTORY_PAGE}{max(0, offset - limit)}"))
    if offset + limit < total: btns.append(InlineKeyboardButton(lang.BUTTON_NEXT, callback_data=f"{c.CALLBACK_HISTORY_PAGE}{offset + limit}"))
    return InlineKeyboardMarkup([btns]) if btns else None

def edit_habit_field_keyboard(habit_id: int) -> InlineKeyboardMarkup:
    """Keyboard to select which habit field to edit."""
    kbd = [
        [InlineKeyboardButton(lang.BUTTON_EDIT_NAME, callback_data=f"{c.CALLBACK_EDIT_FIELD_PREFIX}name_{habit_id}")],
        [InlineKeyboardButton(lang.BUTTON_EDIT_DESCRIPTION, callback_data=f"{c.CALLBACK_EDIT_FIELD_PREFIX}description_{habit_id}")],
        [InlineKeyboardButton(lang.BUTTON_EDIT_CATEGORY, callback_data=f"{c.CALLBACK_EDIT_FIELD_PREFIX}category_{habit_id}")],
        # [InlineKeyboardButton(lang.BUTTON_CANCEL, callback_data=c.CALLBACK_CANCEL_EDIT)], # Optional cancel
    ]
    return InlineKeyboardMarkup(kbd)