# Expose key functions or classes
from .db_manager import (
    # Connection Management
    initialize_database,
    connect_db,
    close_db,
    get_db_connection,
    # User
    add_user_if_not_exists,
    # Habits
    add_habit_db,
    get_user_habits,
    find_habit_by_name,
    get_habit_name_by_id,
    delete_habit_and_log,
    update_habit_db, # <-- Added here
    # Log
    mark_habit_done_db,
    get_todays_habit_statuses,
    get_habit_log,
    get_habit_log_count, # <-- Added here
    # Stats
    get_completion_stats,
    # Reminders
    add_or_update_reminder_db,
    get_reminder_by_habit_id,
    get_all_reminders,
    remove_reminder_by_habit_id,
    get_user_reminders,
)

# Also add it to __all__ for explicit exports
__all__ = [
    # Connection Management
    "initialize_database",
    "connect_db",
    "close_db",
    "get_db_connection",
    # User
    "add_user_if_not_exists",
    # Habits
    "add_habit_db",
    "get_user_habits",
    "find_habit_by_name",
    "get_habit_name_by_id",
    "delete_habit_and_log",
    "update_habit_db", # <-- Added here
    # Log
    "mark_habit_done_db",
    "get_todays_habit_statuses",
    "get_habit_log",
    "get_habit_log_count", # <-- Added here
    # Stats
    "get_completion_stats",
    # Reminders
    "add_or_update_reminder_db",
    "get_reminder_by_habit_id",
    "get_all_reminders",
    "remove_reminder_by_habit_id",
    "get_user_reminders",
]
