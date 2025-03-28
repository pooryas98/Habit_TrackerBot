# utils/constants.py

# --- Callback Data Prefixes ---
CALLBACK_MARK_DONE = "done_"
CALLBACK_DELETE_REMINDER = "delrem_"
CALLBACK_NOOP = "noop_" # No operation / placeholder button

# Delete Habit Flow Callbacks
CALLBACK_SELECT_HABIT_DELETE = "seldelhab_"
CALLBACK_CONFIRM_DELETE_HABIT = "confdelhab_"
CALLBACK_CANCEL_DELETE = "canceldel_"

# Set Reminder Flow Callbacks
CALLBACK_SELECT_REMINDER_HABIT = "setremhab_"

# History Pagination Callbacks
CALLBACK_HISTORY_PAGE = "histpg_" # e.g., histpg_15 (offset)

# Mark Done Selection Callback (New)
CALLBACK_SELECT_HABIT_DONE = "seldone_"

# Edit Habit Flow Callbacks (New)
CALLBACK_SELECT_HABIT_EDIT = "seledithab_"
CALLBACK_EDIT_FIELD_PREFIX = "editfld_" # e.g., editfld_name_{habit_id}, editfld_desc_{habit_id}
CALLBACK_CANCEL_EDIT = "canceledit_"

# General Callbacks
CALLBACK_YES = "yes_"
CALLBACK_NO = "no_"

# --- Conversation States ---
# Add Habit
ADD_HABIT_STATES = range(3)
ASK_NAME, ASK_DESCRIPTION, ASK_CATEGORY = ADD_HABIT_STATES

# Set Reminder
SET_REMINDER_STATES = range(2)
SELECT_REMINDER_HABIT, ASK_REMINDER_TIME = SET_REMINDER_STATES

# Delete Habit
DELETE_HABIT_STATES = range(2)
ASK_HABIT_TO_DELETE, CONFIRM_DELETE = DELETE_HABIT_STATES

# Edit Habit (New)
EDIT_HABIT_STATES = range(4)
SELECT_HABIT_TO_EDIT, SELECT_FIELD_TO_EDIT, ASK_NEW_VALUE, CONFIRM_EDIT_SAVE = EDIT_HABIT_STATES


# --- Job Names ---
JOB_PREFIX_REMINDER = "reminder_" # reminder_{user_id}_{habit_id}


# --- Command Names (used for CommandHandler registration) ---
CMD_START = "start"
CMD_HELP = "help"
CMD_ADD_HABIT = "add_habit"
CMD_TODAY = "today"
CMD_DONE = "done"
CMD_HISTORY = "history"
CMD_STATS = "stats"
CMD_SET_REMINDER = "set_reminder"
CMD_MANAGE_REMINDERS = "manage_reminders"
CMD_DELETE_HABIT = "delete_habit"
CMD_EDIT_HABIT = "edit_habit"
CMD_CANCEL = "cancel"
CMD_REFRESH_MEMBERSHIP = "refresh_membership" # <-- Added

# --- Misc ---
HISTORY_PAGE_LIMIT = 15 # Number of items per history page