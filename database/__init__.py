# Expose key functions from db_manager
from .db_manager import (
    initialize_database, connect_db, close_db, get_db_connection, # Connection
    add_user_if_not_exists, # User
    add_habit_db, get_user_habits, find_habit_by_name, get_habit_name_by_id, delete_habit_and_log, update_habit_db, # Habits
    mark_habit_done_db, get_todays_habit_statuses, get_habit_log, get_habit_log_count, # Log
    get_completion_stats, # Stats
    add_or_update_reminder_db, get_reminder_by_habit_id, get_all_reminders, remove_reminder_by_habit_id, get_user_reminders, # Reminders
)

# Define exports for 'from database import *'
__all__ = [
    "initialize_database", "connect_db", "close_db", "get_db_connection",
    "add_user_if_not_exists",
    "add_habit_db", "get_user_habits", "find_habit_by_name", "get_habit_name_by_id", "delete_habit_and_log", "update_habit_db",
    "mark_habit_done_db", "get_todays_habit_statuses", "get_habit_log", "get_habit_log_count",
    "get_completion_stats",
    "add_or_update_reminder_db", "get_reminder_by_habit_id", "get_all_reminders", "remove_reminder_by_habit_id", "get_user_reminders",
]