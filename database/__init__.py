# database/__init__.py
# Expose key functions or classes
from .db_manager import (
    initialize_database,
    connect_db,
    close_db,
    get_db_connection, # <--- Added here
    add_user_if_not_exists,
    add_habit_db,
    get_user_habits,
    find_habit_by_name,
    get_habit_name_by_id,
    mark_habit_done_db,
    get_todays_habit_statuses,
    add_or_update_reminder_db,
    get_reminder_by_habit_id,
    get_all_reminders,
    remove_reminder_by_habit_id,
    get_user_reminders,
    delete_habit_and_log,
    get_habit_log,
    get_completion_stats
)

# Also add it to __all__ for explicit exports
__all__ = [
    "initialize_database",
    "connect_db",
    "close_db",
    "get_db_connection", # <--- Added here
    "add_user_if_not_exists",
    "add_habit_db",
    "get_user_habits",
    "find_habit_by_name",
    "get_habit_name_by_id",
    "mark_habit_done_db",
    "get_todays_habit_statuses",
    "add_or_update_reminder_db",
    "get_reminder_by_habit_id",
    "get_all_reminders",
    "remove_reminder_by_habit_id",
    "get_user_reminders",
    "delete_habit_and_log",
    "get_habit_log",
    "get_completion_stats",
]