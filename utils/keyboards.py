from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from typing import List, Tuple, Optional

from . import localization as lang
from . import constants as c # Import constants

# --- Today View ---
def today_habits_keyboard(habits_with_status: List[Tuple[int, str, str]]) -> InlineKeyboardMarkup:
    """
    Generates keyboard for the /today command. Shows habits with buttons
    to mark 'pending' ones as 'done'. Completed habits are shown with a checkmark.

    Args:
        habits_with_status: List of tuples (habit_id, habit_name, status).

    Returns:
        InlineKeyboardMarkup: The keyboard layout for the message.
    """
    keyboard = []
    for habit_id, habit_name, status in habits_with_status:
        if status == 'pending':
            button_text = f"{habit_name} ({lang.BUTTON_MARK_DONE})"
            callback_data = f"{c.CALLBACK_MARK_DONE}{habit_id}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
        else:
            # Indicate completed habit, make button non-interactive (or subtly interactive)
            button_text = f"✅ {habit_name}"
            # Use a no-operation callback prefix to avoid accidental triggers
            callback_data = f"{c.CALLBACK_NOOP}{habit_id}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
    return InlineKeyboardMarkup(keyboard)

# --- Reminder Management ---
def reminder_management_keyboard(reminders: List[Tuple[int, str, str]]) -> InlineKeyboardMarkup:
    """
    Generates keyboard for the /manage_reminders command. Shows active reminders
    with buttons to delete them.

    Args:
        reminders: List of tuples (habit_id, habit_name, formatted_time_string).

    Returns:
        InlineKeyboardMarkup: The keyboard layout. Returns empty keyboard if input is empty.
    """
    keyboard = []
    for habit_id, habit_name, time_str in reminders:
        button_text = f"{habit_name} ({time_str}) - {lang.BUTTON_DELETE_REMINDER}"
        callback_data = f"{c.CALLBACK_DELETE_REMINDER}{habit_id}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
    if not keyboard: # Handle case where input list might be empty after filtering
         return InlineKeyboardMarkup([])
    return InlineKeyboardMarkup(keyboard)

# --- Generic Habit Selection ---
def select_habit_keyboard(
    habits: List[Tuple[int, str, Optional[str], Optional[str]]],
    callback_prefix: str
) -> List[List[InlineKeyboardButton]]:
    """
    Generates rows of buttons, each representing a habit, for selection.
    Used by /set_reminder, /delete_habit, /edit_habit, /done (when no args).

    Args:
        habits: List of tuples (habit_id, habit_name, description, category).
                Only habit_id and habit_name are used.
        callback_prefix: The prefix to use for the callback data (e.g., c.CALLBACK_SELECT_HABIT_DELETE).
                         The habit_id will be appended to this prefix.

    Returns:
        List[List[InlineKeyboardButton]]: A list of button rows suitable for InlineKeyboardMarkup.
    """
    keyboard_rows = []
    for habit_id, habit_name, _, _ in habits:
        # Construct callback data: prefix + habit_id
        callback_data = f"{callback_prefix}{habit_id}"
        keyboard_rows.append([InlineKeyboardButton(habit_name, callback_data=callback_data)])
    return keyboard_rows

# --- Yes/No Confirmation ---
def yes_no_keyboard(yes_callback: str, no_callback: str) -> InlineKeyboardMarkup:
    """
    Generates a simple confirmation keyboard with "Yes" and "No" buttons.

    Args:
        yes_callback (str): The callback data for the "Yes" button.
        no_callback (str): The callback data for the "No" button.

    Returns:
        InlineKeyboardMarkup: The keyboard layout.
    """
    keyboard = [[
        InlineKeyboardButton(lang.BUTTON_YES, callback_data=yes_callback),
        InlineKeyboardButton(lang.BUTTON_NO, callback_data=no_callback),
    ]]
    return InlineKeyboardMarkup(keyboard)

# --- History Pagination ---
def history_pagination_keyboard(current_offset: int, total_items: int, limit: int) -> Optional[InlineKeyboardMarkup]:
    """
    Generates pagination buttons ("Previous", "Next") for the /history command.

    Args:
        current_offset (int): The offset of the currently displayed page.
        total_items (int): The total number of items available.
        limit (int): The number of items displayed per page.

    Returns:
        Optional[InlineKeyboardMarkup]: The keyboard with pagination buttons,
                                        or None if no pagination is needed.
    """
    buttons = []
    # Previous button
    if current_offset > 0:
        prev_offset = max(0, current_offset - limit)
        buttons.append(
            InlineKeyboardButton(lang.BUTTON_PREVIOUS, callback_data=f"{c.CALLBACK_HISTORY_PAGE}{prev_offset}")
        )

    # Next button
    if current_offset + limit < total_items:
        next_offset = current_offset + limit
        buttons.append(
            InlineKeyboardButton(lang.BUTTON_NEXT, callback_data=f"{c.CALLBACK_HISTORY_PAGE}{next_offset}")
        )

    if not buttons:
        return None # No pagination needed

    return InlineKeyboardMarkup([buttons]) # Place buttons on the same row

# --- Edit Habit Field Selection ---
def edit_habit_field_keyboard(habit_id: int) -> InlineKeyboardMarkup:
    """
    Generates buttons to select which field of a habit to edit (Name, Description, Category).

    Args:
        habit_id (int): The ID of the habit being edited, used in callback data.

    Returns:
        InlineKeyboardMarkup: The keyboard layout.
    """
    keyboard = [
        [InlineKeyboardButton(lang.BUTTON_EDIT_NAME, callback_data=f"{c.CALLBACK_EDIT_FIELD_PREFIX}name_{habit_id}")],
        [InlineKeyboardButton(lang.BUTTON_EDIT_DESCRIPTION, callback_data=f"{c.CALLBACK_EDIT_FIELD_PREFIX}description_{habit_id}")],
        [InlineKeyboardButton(lang.BUTTON_EDIT_CATEGORY, callback_data=f"{c.CALLBACK_EDIT_FIELD_PREFIX}category_{habit_id}")],
        # Optionally add a cancel button here too
        # [InlineKeyboardButton(lang.BUTTON_CANCEL, callback_data=c.CALLBACK_CANCEL_EDIT)],
    ]
    return InlineKeyboardMarkup(keyboard)
