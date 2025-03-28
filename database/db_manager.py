# db_manager.py (Corrected SQL, Removed is_connected)

import aiosqlite
import os
from datetime import date, datetime, time, timedelta
from typing import List, Tuple, Optional, Dict, Any
import logging
from config import DATABASE_FILE

logger = logging.getLogger(__name__)

# --- Global Connection Management ---
_db_connection: Optional[aiosqlite.Connection] = None

async def connect_db():
    """Connects to the SQLite database and stores the connection globally."""
    global _db_connection
    # Log current state without is_connected
    logger.debug(f"connect_db called. Current _db_connection state: {'Set' if _db_connection else 'None'}")

    # If connection exists, assume it's okay unless an operation fails.
    # aiosqlite might handle stale connections internally better.
    if _db_connection:
        logger.info("Database connection object exists. Reusing.")
        # Let's perform a quick, safe check to see if it responds
        try:
            await _db_connection.execute("PRAGMA user_version;")
            logger.debug("Existing DB connection responded to PRAGMA check.")
            return # Assume okay
        except (aiosqlite.OperationalError, aiosqlite.ProgrammingError, AttributeError) as e:
            logger.warning(f"Existing DB connection failed check ({e}). Attempting to close and reconnect.")
            await close_db() # Close stale connection

    logger.info(f"Attempting to establish global database connection: {DATABASE_FILE}")
    try:
        db = await aiosqlite.connect(DATABASE_FILE)
        await db.execute("PRAGMA journal_mode=WAL;")
        await db.execute("PRAGMA foreign_keys = ON;")
        _db_connection = db
        logger.info(f"Global database connection successful. _db_connection set to: {_db_connection}")
    except aiosqlite.Error as e:
        logger.critical(f"Failed to connect to database {DATABASE_FILE}: {e}", exc_info=True)
        _db_connection = None
        raise

async def close_db():
    """Closes the global database connection if it's open."""
    global _db_connection
    logger.debug(f"close_db called. Current _db_connection state: {'Set' if _db_connection else 'None'}")
    if _db_connection:
        temp_conn = _db_connection # Hold reference
        _db_connection = None # Set global to None *before* closing
        try:
            logger.info("Closing global database connection...")
            await temp_conn.close()
            logger.info("Global database connection closed successfully.")
        except aiosqlite.Error as e:
            logger.error(f"Error closing global database connection: {e}", exc_info=True)
        # No finally needed to set to None, done earlier
    else:
        logger.debug("close_db called but _db_connection was already None.")

async def get_db_connection() -> aiosqlite.Connection:
    """Returns the globally managed database connection. Raises error if None."""
    global _db_connection
    # Log current state without is_connected
    logger.debug(f"get_db_connection called. Current _db_connection state: {'Set' if _db_connection else 'None'}")
    if not _db_connection:
        logger.critical("!!! Attempted to get DB connection, but _db_connection is None.")
        # Attempt to reconnect? Safer to raise for now.
        # logger.warning("DB connection is None, attempting reconnect...")
        # await connect_db()
        # if not _db_connection: # Check again after reconnect attempt
        #     raise ConnectionError("Database connection is not available after reconnect attempt.")
        raise ConnectionError("Database connection is not available (_db_connection is None).")

    logger.debug(f"get_db_connection returning connection object: {_db_connection}")
    return _db_connection

# --- Initialization (Uses its own temporary connection) ---
async def initialize_database():
    """Creates database and tables if they don't exist. Uses a temporary connection."""
    logger.info(f"--- Initializing database schema in: {DATABASE_FILE} ---")
    db = None
    try:
        db = await aiosqlite.connect(DATABASE_FILE)
        await db.execute("PRAGMA journal_mode=WAL;")
        await db.execute("PRAGMA foreign_keys = ON;")

        # --- CORRECTED CREATE TABLE STATEMENTS ---
        await db.execute("""
            CREATE TABLE IF NOT EXISTS Users (
                user_id INTEGER PRIMARY KEY
            )
        """)
        logger.debug("Checked/Created Users table.")

        await db.execute("""
            CREATE TABLE IF NOT EXISTS Habits (
                habit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                category TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES Users(user_id) ON DELETE CASCADE
            )
        """)
        logger.debug("Checked/Created Habits table.")

        await db.execute("""
            CREATE TABLE IF NOT EXISTS HabitLog (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                habit_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                log_date TEXT NOT NULL, -- Store as ISO8601 string (YYYY-MM-DD)
                status TEXT DEFAULT 'pending', -- 'pending' or 'done'
                FOREIGN KEY(habit_id) REFERENCES Habits(habit_id) ON DELETE CASCADE,
                FOREIGN KEY(user_id) REFERENCES Users(user_id) ON DELETE CASCADE,
                UNIQUE(habit_id, user_id, log_date)
            )
        """)
        logger.debug("Checked/Created HabitLog table.")

        await db.execute("""
            CREATE TABLE IF NOT EXISTS Reminders (
                reminder_id INTEGER PRIMARY KEY AUTOINCREMENT,
                habit_id INTEGER NOT NULL UNIQUE, -- Only one reminder per habit
                user_id INTEGER NOT NULL,
                reminder_time TEXT NOT NULL, -- Store as HH:MM:SS string
                job_name TEXT UNIQUE NOT NULL, -- Use the generated job name (user_id_habit_id)
                FOREIGN KEY(habit_id) REFERENCES Habits(habit_id) ON DELETE CASCADE,
                FOREIGN KEY(user_id) REFERENCES Users(user_id) ON DELETE CASCADE
            )
        """)
        logger.debug("Checked/Created Reminders table.")
        # --- END CORRECTED STATEMENTS ---

        await db.commit()
        logger.info("--- Database schema initialization successful ---")
    except aiosqlite.Error as e:
        logger.error(f"!!! aiosqlite error during database initialization: {e}", exc_info=True)
        if db: await db.rollback()
        raise
    finally:
        if db: await db.close()


# --- (Rest of db_manager.py: User, Habit, Log, Reminder functions remain the same,
#      using `await get_db_connection()` internally) ---

# --- User Functions ---
async def add_user_if_not_exists(user_id: int):
    db = await get_db_connection()
    try:
        await db.execute("INSERT OR IGNORE INTO Users (user_id) VALUES (?)", (user_id,))
        await db.commit()
        logger.debug(f"User {user_id} checked/added.")
    except aiosqlite.Error as e:
        logger.error(f"Database error adding user {user_id}: {e}", exc_info=True)
        await db.rollback()
        raise

# --- Habit Functions ---
async def add_habit_db(user_id: int, name: str, description: Optional[str] = None, category: Optional[str] = None) -> Optional[int]:
    db = await get_db_connection()
    logger.debug(f"Attempting to add habit '{name}' for user {user_id}")
    try:
        await add_user_if_not_exists(user_id)
        cursor = await db.execute(
            "INSERT INTO Habits (user_id, name, description, category) VALUES (?, ?, ?, ?)",
            (user_id, name, description, category)
        )
        await db.commit()
        new_id = cursor.lastrowid
        logger.info(f"Successfully added habit '{name}' with ID {new_id} for user {user_id}")
        return new_id
    except aiosqlite.Error as e:
        logger.error(f"Database error adding habit '{name}' for user {user_id}: {e}", exc_info=True)
        await db.rollback()
        return None

async def get_user_habits(user_id: int) -> List[Tuple[int, str, Optional[str], Optional[str]]]:
    db = await get_db_connection()
    logger.debug(f"Fetching habits for user {user_id}")
    habits = []
    try:
        async with db.execute("SELECT habit_id, name, description, category FROM Habits WHERE user_id = ? ORDER BY created_at", (user_id,)) as cursor:
            habits = await cursor.fetchall()
        logger.debug(f"Found {len(habits)} habits for user {user_id}")
        return habits
    except aiosqlite.Error as e:
        logger.error(f"Database error getting habits for user {user_id}: {e}", exc_info=True)
        return []

async def find_habit_by_name(user_id: int, name: str) -> Optional[Tuple[int, str]]:
    db = await get_db_connection()
    logger.debug(f"Searching for habit named '{name}' for user {user_id}")
    try:
        async with db.execute("SELECT habit_id, name FROM Habits WHERE user_id = ? AND name = ? COLLATE NOCASE", (user_id, name)) as cursor:
            habit = await cursor.fetchone()
        if habit:
            logger.debug(f"Found habit '{habit[1]}' (ID: {habit[0]}) for user {user_id}")
            return habit
        else:
            logger.debug(f"Habit '{name}' not found for user {user_id}")
            return None
    except aiosqlite.Error as e:
        logger.error(f"Database error finding habit by name '{name}' for user {user_id}: {e}", exc_info=True)
        return None

async def get_habit_name_by_id(habit_id: int) -> Optional[str]:
    db = await get_db_connection()
    logger.debug(f"Fetching name for habit ID {habit_id}")
    try:
        async with db.execute("SELECT name FROM Habits WHERE habit_id = ?", (habit_id,)) as cursor:
            result = await cursor.fetchone()
        if result:
            logger.debug(f"Found name '{result[0]}' for habit ID {habit_id}")
            return result[0]
        else:
            logger.warning(f"Could not find name for habit ID {habit_id}")
            return None
    except aiosqlite.Error as e:
        logger.error(f"Database error getting habit name for ID {habit_id}: {e}", exc_info=True)
        return None

async def delete_habit_and_log(habit_id: int, user_id: int) -> bool:
    db = await get_db_connection()
    logger.warning(f"Attempting to delete habit {habit_id} and associated data for user {user_id}")
    try:
        cursor = await db.execute("DELETE FROM Habits WHERE habit_id = ? AND user_id = ?", (habit_id, user_id))
        await db.commit()
        if cursor.rowcount > 0:
            logger.info(f"Successfully deleted habit {habit_id} for user {user_id}.")
            return True
        else:
            logger.warning(f"Habit {habit_id} not found or not owned by user {user_id} during deletion.")
            return False
    except aiosqlite.Error as e:
        logger.error(f"Database error deleting habit {habit_id} for user {user_id}: {e}", exc_info=True)
        await db.rollback()
        return False


# --- Habit Log Functions ---
async def mark_habit_done_db(user_id: int, habit_id: int, log_date: date) -> str:
    db = await get_db_connection()
    logger.debug(f"Attempting to mark habit {habit_id} as done for user {user_id} on {log_date}")
    log_date_str = log_date.isoformat()
    try:
        async with db.execute("SELECT 1 FROM Habits WHERE habit_id = ? AND user_id = ?", (habit_id, user_id)) as cursor:
            if not await cursor.fetchone():
                logger.warning(f"Attempted to mark non-existent or wrong user's habit: {habit_id}, user {user_id}")
                return "error"

        cursor = await db.execute("""
            INSERT INTO HabitLog (habit_id, user_id, log_date, status)
            VALUES (?, ?, ?, 'done')
            ON CONFLICT(habit_id, user_id, log_date) DO UPDATE SET status = 'done'
            WHERE status != 'done'
        """, (habit_id, user_id, log_date_str))

        if cursor.rowcount > 0:
            await db.commit()
            logger.info(f"Successfully marked habit {habit_id} as done for user {user_id} on {log_date_str}")
            return "success"
        else:
            logger.info(f"Habit {habit_id} was already marked as done for user {user_id} on {log_date_str}")
            return "already_done"
    except aiosqlite.Error as e:
        logger.error(f"Database error marking habit {habit_id} done for user {user_id}: {e}", exc_info=True)
        await db.rollback()
        return "error"

async def get_todays_habit_statuses(user_id: int, today_date: date) -> Dict[int, str]:
    db = await get_db_connection()
    logger.debug(f"Fetching today's ({today_date}) statuses for user {user_id}")
    today_date_str = today_date.isoformat()
    statuses = {}
    try:
        async with db.execute("SELECT habit_id FROM Habits WHERE user_id = ?", (user_id,)) as cursor:
            all_habit_ids = [row[0] for row in await cursor.fetchall()]

        if not all_habit_ids: return {}

        placeholders = ','.join('?' * len(all_habit_ids))
        query = f"""
            SELECT habit_id, status
            FROM HabitLog
            WHERE user_id = ? AND log_date = ? AND habit_id IN ({placeholders})
        """
        params = [user_id, today_date_str] + all_habit_ids
        async with db.execute(query, params) as cursor:
            logged_statuses = {row[0]: row[1] for row in await cursor.fetchall()}

        for habit_id in all_habit_ids:
            statuses[habit_id] = logged_statuses.get(habit_id, 'pending')

        return statuses
    except aiosqlite.Error as e:
        logger.error(f"Database error getting today's statuses for user {user_id}: {e}", exc_info=True)
        return {}

async def get_habit_log(user_id: int, habit_id: Optional[int] = None, limit: int = 30, offset: int = 0) -> List[Tuple[date, str, str]]:
    db = await get_db_connection()
    logger.debug(f"Fetching habit log for user {user_id}, habit_id={habit_id}, limit={limit}, offset={offset}")
    log_entries = []
    try:
        query = """
            SELECT hl.log_date, h.name, hl.status
            FROM HabitLog hl
            JOIN Habits h ON hl.habit_id = h.habit_id
            WHERE hl.user_id = ?
        """
        params: List[Any] = [user_id]
        if habit_id:
            query += " AND hl.habit_id = ?"
            params.append(habit_id)

        query += " ORDER BY hl.log_date DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        async with db.execute(query, tuple(params)) as cursor:
            rows = await cursor.fetchall()
            for row in rows:
                try:
                    log_date_obj = date.fromisoformat(row[0])
                    log_entries.append((log_date_obj, row[1], row[2]))
                except (ValueError, TypeError):
                     logger.warning(f"Skipping log entry with invalid date format: {row}")

        logger.debug(f"Found {len(log_entries)} log entries matching criteria.")
        return log_entries

    except aiosqlite.Error as e:
        logger.error(f"Database error getting habit log for user {user_id}: {e}", exc_info=True)
        return []


async def get_completion_stats(user_id: int, days_back: int = 30) -> Dict[int, Dict[str, Any]]:
    db = await get_db_connection()
    logger.debug(f"Calculating completion stats for user {user_id} over last {days_back} days.")
    stats = {}
    end_date = date.today()
    start_date = end_date - timedelta(days=days_back - 1)
    start_date_str = start_date.isoformat()
    end_date_str = end_date.isoformat()

    try:
        user_habits = await get_user_habits(user_id)
        if not user_habits: return {}

        habit_ids = [h[0] for h in user_habits]
        placeholders = ','.join('?' * len(habit_ids))

        query = f"""
            SELECT habit_id, log_date, status
            FROM HabitLog
            WHERE user_id = ? AND habit_id IN ({placeholders}) AND log_date BETWEEN ? AND ?
        """
        params = [user_id] + habit_ids + [start_date_str, end_date_str]

        logs_by_habit: Dict[int, Dict[date, str]] = {hid: {} for hid in habit_ids}
        async with db.execute(query, tuple(params)) as cursor:
            rows = await cursor.fetchall()
            for habit_id, log_date_str, status in rows:
                try:
                    log_date_obj = date.fromisoformat(log_date_str)
                    if start_date <= log_date_obj <= end_date:
                        logs_by_habit[habit_id][log_date_obj] = status
                except (ValueError, TypeError):
                    logger.warning(f"Skipping stat entry with invalid date format: {log_date_str}")

        num_days_in_period = (end_date - start_date).days + 1
        for habit_id, name, _, _ in user_habits:
            done_count = 0; current_streak = 0; max_streak = 0; streak_active = True
            habit_logs = logs_by_habit.get(habit_id, {}); temp_streak = 0
            for i in range(num_days_in_period):
                d = end_date - timedelta(days=i)
                status = habit_logs.get(d)
                if status == 'done': done_count += 1; temp_streak += 1
                else:
                    if i == 0: current_streak = 0
                    streak_active = False; max_streak = max(max_streak, temp_streak); temp_streak = 0
                if i == 0 and streak_active: current_streak = temp_streak
            max_streak = max(max_streak, temp_streak)
            completion_rate = (done_count / num_days_in_period) * 100 if num_days_in_period > 0 else 0
            stats[habit_id] = {
                "name": name, "done_count": done_count, "total_days": num_days_in_period,
                "completion_rate": round(completion_rate, 1),
                "current_streak": current_streak, "max_streak": max_streak
            }
        return stats
    except aiosqlite.Error as e:
        logger.error(f"Database error calculating stats for user {user_id}: {e}", exc_info=True)
        return {}


# --- Reminder Functions ---
async def add_or_update_reminder_db(user_id: int, habit_id: int, reminder_time: time, job_name: str) -> bool:
    db = await get_db_connection()
    logger.debug(f"Adding/updating reminder for habit {habit_id}, user {user_id} at {reminder_time}, job {job_name}")
    time_str = reminder_time.strftime('%H:%M:%S')
    try:
        await add_user_if_not_exists(user_id)
        async with db.execute("SELECT 1 FROM Habits WHERE habit_id = ? AND user_id = ?", (habit_id, user_id)) as cursor:
            if not await cursor.fetchone():
                logger.warning(f"Attempted to set reminder for non-existent or wrong user's habit: {habit_id}, user {user_id}")
                return False
        cursor = await db.execute("""
            INSERT INTO Reminders (user_id, habit_id, reminder_time, job_name)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(habit_id) DO UPDATE SET
                reminder_time = excluded.reminder_time,
                job_name = excluded.job_name,
                user_id = excluded.user_id
        """, (user_id, habit_id, time_str, job_name))
        await db.commit()
        logger.info(f"Successfully added/updated reminder for habit {habit_id}, job {job_name}")
        return True
    except aiosqlite.Error as e:
        logger.error(f"Database error adding/updating reminder for habit {habit_id}: {e}", exc_info=True)
        await db.rollback()
        return False

async def get_reminder_by_habit_id(habit_id: int) -> Optional[Tuple[int, time, str]]:
    db = await get_db_connection()
    logger.debug(f"Fetching reminder details for habit {habit_id}")
    try:
        async with db.execute("SELECT user_id, reminder_time, job_name FROM Reminders WHERE habit_id = ?", (habit_id,)) as cursor:
            row = await cursor.fetchone()
        if row:
            try:
                reminder_time_obj = datetime.strptime(row[1], '%H:%M:%S').time()
                logger.debug(f"Found reminder for habit {habit_id}: User {row[0]}, Time {reminder_time_obj}, Job {row[2]}")
                return row[0], reminder_time_obj, row[2]
            except (ValueError, TypeError):
                logger.error(f"Invalid time format '{row[1]}' found in DB for habit {habit_id}")
                return None
        logger.debug(f"No reminder found for habit {habit_id}")
        return None
    except aiosqlite.Error as e:
        logger.error(f"Database error getting reminder for habit {habit_id}: {e}", exc_info=True)
        return None

async def get_all_reminders() -> List[Tuple[int, int, time, str]]:
    db = await get_db_connection()
    logger.debug("Fetching all reminders from database.")
    reminders = []
    try:
        async with db.execute("SELECT user_id, habit_id, reminder_time, job_name FROM Reminders") as cursor:
            rows = await cursor.fetchall()
        logger.debug(f"Found {len(rows)} total reminder entries in DB.")
        for row in rows:
             try:
                 reminder_time_obj = datetime.strptime(row[2], '%H:%M:%S').time()
                 reminders.append((row[0], row[1], reminder_time_obj, row[3]))
             except (ValueError, TypeError):
                 logger.warning(f"Skipping reminder with invalid time format in DB: {row}")
        return reminders
    except aiosqlite.Error as e:
        logger.error(f"Database error getting all reminders: {e}", exc_info=True)
        return []

async def remove_reminder_by_habit_id(habit_id: int) -> Optional[str]:
    db = await get_db_connection()
    logger.debug(f"Attempting to remove reminder for habit {habit_id}")
    job_name = None
    try:
        async with db.execute("SELECT job_name FROM Reminders WHERE habit_id = ?", (habit_id,)) as cursor:
            row = await cursor.fetchone()
        if row:
            job_name = row[0]
            logger.debug(f"Found job_name '{job_name}' for habit {habit_id}. Proceeding with deletion.")
            cursor = await db.execute("DELETE FROM Reminders WHERE habit_id = ?", (habit_id,))
            await db.commit()
            if cursor.rowcount > 0:
                logger.info(f"Successfully removed reminder for habit {habit_id} from DB.")
            else:
                 logger.warning(f"Found job_name '{job_name}' but failed to delete reminder for habit {habit_id}.")
                 job_name = None
        else:
            logger.warning(f"Attempted to remove reminder for habit {habit_id}, but it was not found in DB.")
        return job_name
    except aiosqlite.Error as e:
        logger.error(f"Database error removing reminder for habit {habit_id}: {e}", exc_info=True)
        await db.rollback()
        return None

async def get_user_reminders(user_id: int) -> List[Tuple[int, time, str]]:
    db = await get_db_connection()
    logger.debug(f"Fetching reminders specifically for user {user_id}")
    reminders = []
    try:
        async with db.execute(
            "SELECT r.habit_id, r.reminder_time, r.job_name FROM Reminders r JOIN Habits h ON r.habit_id = h.habit_id WHERE r.user_id = ? ORDER BY r.reminder_time",
            (user_id,)
        ) as cursor:
            rows = await cursor.fetchall()
        logger.debug(f"Found {len(rows)} reminders for user {user_id}")
        for row in rows:
             try:
                 reminder_time_obj = datetime.strptime(row[1], '%H:%M:%S').time()
                 reminders.append((row[0], reminder_time_obj, row[2]))
             except ValueError:
                 logger.warning(f"Skipping user reminder for user {user_id} with invalid time format: {row}")
        return reminders
    except aiosqlite.Error as e:
        logger.error(f"Database error getting reminders for user {user_id}: {e}", exc_info=True)
        return []


__all__ = [
    "connect_db", "close_db", "get_db_connection", "initialize_database",
    "add_user_if_not_exists", "add_habit_db", "get_user_habits", "find_habit_by_name",
    "get_habit_name_by_id", "delete_habit_and_log", "mark_habit_done_db",
    "get_todays_habit_statuses", "get_habit_log", "get_completion_stats",
    "add_or_update_reminder_db", "get_reminder_by_habit_id", "get_all_reminders",
    "remove_reminder_by_habit_id", "get_user_reminders",
]