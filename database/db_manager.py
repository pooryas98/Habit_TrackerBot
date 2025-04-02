import aiosqlite
import os
from datetime import date, datetime, time, timedelta
from typing import List, Tuple, Optional, Dict, Any
import logging
from config import DATABASE_FILE

logger = logging.getLogger(__name__)

_db_connection: Optional[aiosqlite.Connection] = None

async def connect_db():
    """Connects to DB, stores connection globally. Reconnects if needed."""
    global _db_connection
    if _db_connection:
        try: # Quick check if connection is alive
            await _db_connection.execute("PRAGMA user_version;")
            logger.info("Reusing existing DB connection.")
            return
        except (aiosqlite.Error, AttributeError) as e:
            logger.warning(f"Existing DB conn failed check ({e}). Reconnecting.")
            await close_db()

    logger.info(f"Establishing global DB connection: {DATABASE_FILE}")
    try:
        db = await aiosqlite.connect(DATABASE_FILE)
        await db.execute("PRAGMA journal_mode=WAL;")
        await db.execute("PRAGMA foreign_keys = ON;")
        _db_connection = db
        logger.info("Global DB connection successful.")
    except aiosqlite.Error as e:
        logger.critical(f"Failed to connect to DB {DATABASE_FILE}: {e}", exc_info=True)
        _db_connection = None; raise

async def close_db():
    """Closes the global DB connection."""
    global _db_connection
    if _db_connection:
        conn = _db_connection
        _db_connection = None # Clear global var first
        try:
            logger.info("Closing global DB connection...")
            await conn.close()
        except aiosqlite.Error as e: logger.error(f"Error closing global DB: {e}", exc_info=True)
    else: logger.debug("close_db called but connection was already None.")

async def get_db_connection() -> aiosqlite.Connection:
    """Returns the global DB connection, raises ConnectionError if None."""
    if not _db_connection:
        logger.critical("DB connection requested but _db_connection is None.")
        raise ConnectionError("Database connection is not available.")
    return _db_connection

async def initialize_database():
    """Creates tables if they don't exist using a temporary connection."""
    logger.info(f"Initializing DB schema in: {DATABASE_FILE}")
    db = None
    try:
        db = await aiosqlite.connect(DATABASE_FILE)
        await db.execute("PRAGMA journal_mode=WAL;")
        await db.execute("PRAGMA foreign_keys = ON;")
        await db.execute("CREATE TABLE IF NOT EXISTS Users (user_id INTEGER PRIMARY KEY)")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS Habits (
                habit_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
                name TEXT NOT NULL, description TEXT, category TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES Users(user_id) ON DELETE CASCADE )""")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS HabitLog (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT, habit_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL, log_date TEXT NOT NULL, -- YYYY-MM-DD
                status TEXT DEFAULT 'pending', -- 'pending' or 'done'
                FOREIGN KEY(habit_id) REFERENCES Habits(habit_id) ON DELETE CASCADE,
                FOREIGN KEY(user_id) REFERENCES Users(user_id) ON DELETE CASCADE,
                UNIQUE(habit_id, user_id, log_date) )""")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS Reminders (
                reminder_id INTEGER PRIMARY KEY AUTOINCREMENT, habit_id INTEGER NOT NULL UNIQUE,
                user_id INTEGER NOT NULL, reminder_time TEXT NOT NULL, -- HH:MM:SS
                job_name TEXT UNIQUE NOT NULL,
                FOREIGN KEY(habit_id) REFERENCES Habits(habit_id) ON DELETE CASCADE,
                FOREIGN KEY(user_id) REFERENCES Users(user_id) ON DELETE CASCADE )""")
        await db.commit()
        logger.info("DB schema initialization check complete.")
    except aiosqlite.Error as e:
        logger.error(f"DB init error: {e}", exc_info=True)
        if db: await db.rollback(); raise
    finally:
        if db: await db.close()

# --- User ---
async def add_user_if_not_exists(user_id: int):
    """Adds user if they don't exist."""
    db = await get_db_connection()
    try:
        await db.execute("INSERT OR IGNORE INTO Users (user_id) VALUES (?)", (user_id,))
        await db.commit()
    except aiosqlite.Error as e:
        logger.error(f"DB error adding user {user_id}: {e}", exc_info=True)
        await db.rollback(); raise

# --- Habits ---
async def add_habit_db(user_id: int, name: str, desc: Optional[str]=None, cat: Optional[str]=None) -> Optional[int]:
    """Adds a new habit. Returns new habit_id or None."""
    db = await get_db_connection()
    try:
        await add_user_if_not_exists(user_id) # Ensure user exists
        cursor = await db.execute("INSERT INTO Habits (user_id, name, description, category) VALUES (?, ?, ?, ?)", (user_id, name, desc, cat))
        await db.commit()
        new_id = cursor.lastrowid
        logger.info(f"Added habit '{name}' (ID: {new_id}) for user {user_id}")
        return new_id
    except aiosqlite.Error as e:
        logger.error(f"DB error adding habit '{name}' user {user_id}: {e}", exc_info=True)
        await db.rollback(); return None

async def get_user_habits(user_id: int) -> List[Tuple[int, str, Optional[str], Optional[str]]]:
    """Retrieves all habits for a user (id, name, desc, cat)."""
    db = await get_db_connection()
    try:
        async with db.execute("SELECT habit_id, name, description, category FROM Habits WHERE user_id = ? ORDER BY created_at", (user_id,)) as cursor:
            return await cursor.fetchall()
    except aiosqlite.Error as e:
        logger.error(f"DB error getting habits user {user_id}: {e}", exc_info=True); return []

async def find_habit_by_name(user_id: int, name: str) -> Optional[Tuple[int, str]]:
    """Finds habit by name (case-insensitive). Returns (id, name) or None."""
    db = await get_db_connection()
    try:
        async with db.execute("SELECT habit_id, name FROM Habits WHERE user_id = ? AND name = ? COLLATE NOCASE", (user_id, name)) as cursor:
            return await cursor.fetchone()
    except aiosqlite.Error as e:
        logger.error(f"DB error finding habit '{name}' user {user_id}: {e}", exc_info=True); return None

async def get_habit_name_by_id(habit_id: int) -> Optional[str]:
    """Retrieves habit name by ID."""
    db = await get_db_connection()
    try:
        async with db.execute("SELECT name FROM Habits WHERE habit_id = ?", (habit_id,)) as cursor:
            result = await cursor.fetchone()
            return result[0] if result else None
    except aiosqlite.Error as e:
        logger.error(f"DB error getting habit name ID {habit_id}: {e}", exc_info=True); return None

async def delete_habit_and_log(habit_id: int, user_id: int) -> bool:
    """Deletes habit & associated data (via CASCADE). Returns True if deleted."""
    db = await get_db_connection()
    logger.warning(f"Attempting delete habit {habit_id} user {user_id}")
    try:
        cursor = await db.execute("DELETE FROM Habits WHERE habit_id = ? AND user_id = ?", (habit_id, user_id))
        await db.commit()
        if cursor.rowcount > 0: logger.info(f"Deleted habit {habit_id} for user {user_id}."); return True
        else: logger.warning(f"Habit {habit_id} not found or wrong user {user_id} for delete."); return False
    except aiosqlite.Error as e:
        logger.error(f"DB error deleting habit {habit_id} user {user_id}: {e}", exc_info=True)
        await db.rollback(); return False

async def update_habit_db(habit_id: int, user_id: int, field: str, value: Optional[str]) -> bool:
    """Updates habit field ('name', 'description', 'category'). Returns True if updated."""
    db = await get_db_connection()
    if field not in ["name", "description", "category"]: logger.error(f"Invalid field update '{field}'"); return False
    if field == "name" and not value: logger.error("Habit name cannot be empty."); return False

    sql = f"UPDATE Habits SET {field} = ? WHERE habit_id = ? AND user_id = ?"
    try:
        cursor = await db.execute(sql, (value, habit_id, user_id))
        await db.commit()
        if cursor.rowcount > 0: logger.info(f"Updated '{field}' for habit {habit_id}."); return True
        else: logger.warning(f"Update failed: Habit {habit_id} not found or wrong user {user_id}."); return False
    except aiosqlite.Error as e:
        logger.error(f"DB error updating habit {habit_id}: {e}", exc_info=True)
        await db.rollback(); return False

# --- Log ---
async def mark_habit_done_db(user_id: int, habit_id: int, log_date: date) -> str:
    """Marks habit 'done'. Returns 'success', 'already_done', 'error'."""
    db = await get_db_connection()
    log_date_str = log_date.isoformat()
    try:
        cursor = await db.execute("""
            INSERT INTO HabitLog (habit_id, user_id, log_date, status) VALUES (?, ?, ?, 'done')
            ON CONFLICT(habit_id, user_id, log_date) DO UPDATE SET status = 'done' WHERE status != 'done'
        """, (habit_id, user_id, log_date_str))
        if cursor.rowcount > 0: await db.commit(); return "success"
        else: return "already_done" # No rows affected means it was already 'done'
    except aiosqlite.Error as e:
        logger.error(f"DB error marking done habit {habit_id} user {user_id}: {e}", exc_info=True)
        await db.rollback(); return "error"

async def get_todays_habit_statuses(user_id: int, today_date: date) -> Dict[int, str]:
    """Gets status ('done'/'pending') for all user habits for a date."""
    db = await get_db_connection()
    today_str = today_date.isoformat()
    statuses = {}
    try:
        async with db.execute("SELECT habit_id FROM Habits WHERE user_id = ?", (user_id,)) as cursor:
            all_ids = [r[0] for r in await cursor.fetchall()]
        if not all_ids: return {}

        placeholders = ','.join('?' * len(all_ids))
        query = f"SELECT habit_id, status FROM HabitLog WHERE user_id=? AND log_date=? AND habit_id IN ({placeholders})"
        params = [user_id, today_str] + all_ids
        async with db.execute(query, params) as cursor:
            logged = {r[0]: r[1] for r in await cursor.fetchall()}
        # Default to pending if not in log
        for hid in all_ids: statuses[hid] = logged.get(hid, 'pending')
        return statuses
    except aiosqlite.Error as e:
        logger.error(f"DB error getting today's statuses user {user_id}: {e}", exc_info=True); return {}

async def get_habit_log(user_id: int, habit_id: Optional[int]=None, limit: int=30, offset: int=0) -> List[Tuple[date, str, str]]:
    """Retrieves habit log (date, name, status), ordered desc."""
    db = await get_db_connection()
    entries = []
    try:
        query = "SELECT hl.log_date, h.name, hl.status FROM HabitLog hl JOIN Habits h ON hl.habit_id = h.habit_id WHERE hl.user_id = ?"
        params: List[Any] = [user_id]
        if habit_id: query += " AND hl.habit_id = ?"; params.append(habit_id)
        query += " ORDER BY hl.log_date DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        async with db.execute(query, tuple(params)) as cursor:
            for row in await cursor.fetchall():
                try: entries.append((date.fromisoformat(row[0]), row[1], row[2]))
                except (ValueError, TypeError): logger.warning(f"Skipping log entry invalid date: {row}")
        return entries
    except aiosqlite.Error as e:
        logger.error(f"DB error getting log user {user_id}: {e}", exc_info=True); return []

async def get_habit_log_count(user_id: int, habit_id: Optional[int] = None) -> int:
    """Counts habit log entries."""
    db = await get_db_connection()
    try:
        query = "SELECT COUNT(*) FROM HabitLog WHERE user_id = ?"
        params: List[Any] = [user_id]
        if habit_id: query += " AND habit_id = ?"; params.append(habit_id)
        async with db.execute(query, tuple(params)) as cursor:
            result = await cursor.fetchone(); return result[0] if result else 0
    except aiosqlite.Error as e:
        logger.error(f"DB error counting log user {user_id}: {e}", exc_info=True); return 0

async def get_completion_stats(user_id: int, days_back: int = 30) -> Dict[int, Dict[str, Any]]:
    """Calculates stats (rate, streaks) over last N days."""
    db = await get_db_connection()
    stats = {}
    end_date = date.today()
    start_date = end_date - timedelta(days=days_back - 1)
    start_str, end_str = start_date.isoformat(), end_date.isoformat()

    try:
        user_habits = await get_user_habits(user_id)
        if not user_habits: return {}
        habit_ids = [h[0] for h in user_habits]
        placeholders = ','.join('?' * len(habit_ids))

        query = f"SELECT habit_id, log_date, status FROM HabitLog WHERE user_id=? AND habit_id IN ({placeholders}) AND log_date BETWEEN ? AND ?"
        params = [user_id] + habit_ids + [start_str, end_str]
        logs_by_habit: Dict[int, Dict[date, str]] = {hid: {} for hid in habit_ids}
        async with db.execute(query, tuple(params)) as cursor:
            for hid, date_str, status in await cursor.fetchall():
                try: logs_by_habit[hid][date.fromisoformat(date_str)] = status
                except (ValueError, TypeError): pass # Ignore invalid dates

        num_days = (end_date - start_date).days + 1
        for hid, name, _, _ in user_habits:
            logs = logs_by_habit.get(hid, {})
            done_count, current_streak, max_streak, temp_streak = 0, 0, 0, 0
            streak_active = True
            for i in range(num_days):
                d = end_date - timedelta(days=i)
                if logs.get(d) == 'done': done_count += 1; temp_streak += 1
                else:
                    if i == 0: current_streak = 0
                    streak_active = False; max_streak = max(max_streak, temp_streak); temp_streak = 0
                if i == 0 and streak_active: current_streak = temp_streak
            max_streak = max(max_streak, temp_streak) # Check last streak
            rate = (done_count / num_days) * 100 if num_days > 0 else 0
            stats[hid] = {"name": name, "done_count": done_count, "total_days": num_days,
                          "completion_rate": round(rate, 1), "current_streak": current_streak, "max_streak": max_streak}
        return stats
    except aiosqlite.Error as e:
        logger.error(f"DB error calculating stats user {user_id}: {e}", exc_info=True); return {}

# --- Reminders ---
async def add_or_update_reminder_db(user_id: int, habit_id: int, reminder_time: time, job_name: str) -> bool:
    """Adds/Updates reminder. Returns True on success."""
    db = await get_db_connection()
    time_str = reminder_time.strftime('%H:%M:%S')
    try:
        await add_user_if_not_exists(user_id)
        # Verify habit exists for user
        async with db.execute("SELECT 1 FROM Habits WHERE habit_id = ? AND user_id = ?", (habit_id, user_id)) as cur:
             if not await cur.fetchone(): logger.warning(f"Reminder attempt for non-existent/wrong user habit: {habit_id}, user {user_id}"); return False
        cursor = await db.execute("""INSERT INTO Reminders (user_id, habit_id, reminder_time, job_name) VALUES (?, ?, ?, ?)
                                     ON CONFLICT(habit_id) DO UPDATE SET reminder_time=excluded.reminder_time, job_name=excluded.job_name""",
                                  (user_id, habit_id, time_str, job_name))
        await db.commit()
        logger.info(f"Added/Updated reminder habit {habit_id}, job {job_name}")
        return True
    except aiosqlite.Error as e:
        logger.error(f"DB error adding/updating reminder habit {habit_id}: {e}", exc_info=True)
        await db.rollback(); return False

async def get_reminder_by_habit_id(habit_id: int) -> Optional[Tuple[int, time, str]]:
    """Gets reminder details (user_id, time, job_name) by habit ID."""
    db = await get_db_connection()
    try:
        async with db.execute("SELECT user_id, reminder_time, job_name FROM Reminders WHERE habit_id = ?", (habit_id,)) as cursor:
            row = await cursor.fetchone()
        if row:
            try: return row[0], datetime.strptime(row[1], '%H:%M:%S').time(), row[2]
            except (ValueError, TypeError): logger.error(f"Invalid time format '{row[1]}' in DB for habit {habit_id}."); return None
        return None
    except aiosqlite.Error as e:
        logger.error(f"DB error getting reminder habit {habit_id}: {e}", exc_info=True); return None

async def get_all_reminders() -> List[Tuple[int, int, time, str]]:
    """Retrieves all reminders (user_id, habit_id, time, job_name)."""
    db = await get_db_connection()
    reminders = []
    try:
        async with db.execute("SELECT user_id, habit_id, reminder_time, job_name FROM Reminders") as cursor:
            for row in await cursor.fetchall():
                 try: reminders.append((row[0], row[1], datetime.strptime(row[2], '%H:%M:%S').time(), row[3]))
                 except (ValueError, TypeError): logger.warning(f"Skipping reminder invalid time fmt: {row}")
        return reminders
    except aiosqlite.Error as e: logger.error(f"DB error getting all reminders: {e}", exc_info=True); return []

async def remove_reminder_by_habit_id(habit_id: int) -> Optional[str]:
    """Removes reminder by habit ID. Returns job_name if found & removed, else None."""
    db = await get_db_connection()
    job_name = None
    try:
        async with db.execute("SELECT job_name FROM Reminders WHERE habit_id = ?", (habit_id,)) as cursor: row = await cursor.fetchone()
        if row:
            job_name = row[0]
            cursor = await db.execute("DELETE FROM Reminders WHERE habit_id = ?", (habit_id,))
            await db.commit()
            if cursor.rowcount > 0: logger.info(f"Removed reminder habit {habit_id} from DB.")
            else: logger.warning(f"Found job '{job_name}' but failed delete reminder habit {habit_id}."); job_name = None # Indicate delete fail
        else: logger.warning(f"Remove reminder attempt: habit {habit_id} not found.")
        return job_name
    except aiosqlite.Error as e:
        logger.error(f"DB error removing reminder habit {habit_id}: {e}", exc_info=True)
        await db.rollback(); return None

async def get_user_reminders(user_id: int) -> List[Tuple[int, time, str]]:
    """Retrieves reminders (habit_id, time, job_name) for a specific user."""
    db = await get_db_connection()
    reminders = []
    try:
        query = "SELECT r.habit_id, r.reminder_time, r.job_name FROM Reminders r JOIN Habits h ON r.habit_id = h.habit_id WHERE r.user_id = ? ORDER BY r.reminder_time"
        async with db.execute(query, (user_id,)) as cursor:
            for row in await cursor.fetchall():
                 try: reminders.append((row[0], datetime.strptime(row[1], '%H:%M:%S').time(), row[2]))
                 except ValueError: logger.warning(f"Skipping user reminder invalid time: {row}")
        return reminders
    except aiosqlite.Error as e: logger.error(f"DB error getting user reminders {user_id}: {e}", exc_info=True); return []