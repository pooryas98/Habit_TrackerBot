import aiosqlite, os, logging
from datetime import date, datetime, time, timedelta
from typing import List, Tuple, Optional, Dict, Any
from config import DATABASE_FILE

logger = logging.getLogger(__name__)
_db: Optional[aiosqlite.Connection] = None

async def connect_db():
    """Connects/Reuses global DB connection."""
    global _db
    if _db:
        try: await _db.execute("PRAGMA user_version;"); logger.info("Reusing DB connection."); return
        except (aiosqlite.Error, AttributeError) as e: logger.warning(f"DB check failed ({e}). Reconnecting."); await close_db()
    logger.info(f"Connecting to DB: {DATABASE_FILE}")
    try:
        db = await aiosqlite.connect(DATABASE_FILE)
        await db.execute("PRAGMA journal_mode=WAL;")
        await db.execute("PRAGMA foreign_keys = ON;")
        _db = db; logger.info("Global DB connection successful.")
    except aiosqlite.Error as e: logger.critical(f"DB connect failed: {e}", exc_info=True); _db = None; raise ConnectionError(f"DB connect failed: {e}")

async def close_db():
    """Closes global DB connection."""
    global _db
    if _db:
        conn = _db; _db = None
        try: logger.info("Closing global DB..."); await conn.close()
        except aiosqlite.Error as e: logger.error(f"Error closing DB: {e}", exc_info=True)
    else: logger.debug("close_db called, but _db is None.")

async def get_db_connection() -> aiosqlite.Connection:
    """Returns global DB connection, raises ConnectionError if None."""
    if not _db: logger.critical("DB connection is None."); raise ConnectionError("DB unavailable.")
    return _db

async def _execute_commit(sql: str, params: tuple = (), *, get_last_id: bool = False) -> Optional[int]:
    """Helper: execute, commit, optionally return last row ID/rowcount."""
    db = await get_db_connection()
    last_id = None
    try:
        cursor = await db.execute(sql, params)
        if get_last_id: last_id = cursor.lastrowid
        await db.commit()
        return last_id if get_last_id else cursor.rowcount
    except aiosqlite.Error as e:
        logger.error(f"DB commit err: {sql[:80]}.. P:{params} E:{e}", exc_info=True)
        await db.rollback(); raise

async def _fetchone(sql: str, params: tuple = ()) -> Optional[tuple]:
    """Helper: execute and fetch one."""
    db = await get_db_connection()
    try:
        async with db.execute(sql, params) as cursor: return await cursor.fetchone()
    except aiosqlite.Error as e: logger.error(f"DB fetchone err: {sql[:80]}.. E:{e}", exc_info=True); raise

async def _fetchall(sql: str, params: tuple = ()) -> List[tuple]:
    """Helper: execute and fetch all."""
    db = await get_db_connection()
    try:
        async with db.execute(sql, params) as cursor: return await cursor.fetchall()
    except aiosqlite.Error as e: logger.error(f"DB fetchall err: {sql[:80]}.. E:{e}", exc_info=True); raise

async def initialize_database():
    """Creates tables if they don't exist."""
    logger.info(f"Initializing DB schema: {DATABASE_FILE}")
    try:
        async with aiosqlite.connect(DATABASE_FILE) as db: # Temp connection for init
            await db.execute("PRAGMA journal_mode=WAL;")
            await db.execute("PRAGMA foreign_keys = ON;")
            await db.execute("CREATE TABLE IF NOT EXISTS Users (user_id INTEGER PRIMARY KEY)")
            await db.execute("""CREATE TABLE IF NOT EXISTS Habits ( habit_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
                                name TEXT NOT NULL, description TEXT, category TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                                FOREIGN KEY(user_id) REFERENCES Users(user_id) ON DELETE CASCADE )""")
            await db.execute("""CREATE TABLE IF NOT EXISTS HabitLog ( log_id INTEGER PRIMARY KEY AUTOINCREMENT, habit_id INTEGER NOT NULL,
                                user_id INTEGER NOT NULL, log_date TEXT NOT NULL, status TEXT DEFAULT 'pending',
                                FOREIGN KEY(habit_id) REFERENCES Habits(habit_id) ON DELETE CASCADE,
                                FOREIGN KEY(user_id) REFERENCES Users(user_id) ON DELETE CASCADE, UNIQUE(habit_id, user_id, log_date) )""")
            await db.execute("""CREATE TABLE IF NOT EXISTS Reminders ( reminder_id INTEGER PRIMARY KEY AUTOINCREMENT, habit_id INTEGER NOT NULL UNIQUE,
                                user_id INTEGER NOT NULL, reminder_time TEXT NOT NULL, job_name TEXT UNIQUE NOT NULL,
                                FOREIGN KEY(habit_id) REFERENCES Habits(habit_id) ON DELETE CASCADE,
                                FOREIGN KEY(user_id) REFERENCES Users(user_id) ON DELETE CASCADE )""")
            await db.commit()
            logger.info("DB schema init check complete.")
    except aiosqlite.Error as e: logger.error(f"DB init error: {e}", exc_info=True); raise

# --- User ---
async def add_user_if_not_exists(user_id: int):
    await _execute_commit("INSERT OR IGNORE INTO Users (user_id) VALUES (?)", (user_id,))

# --- Habits ---
async def add_habit_db(user_id: int, name: str, desc: Optional[str]=None, cat: Optional[str]=None) -> Optional[int]:
    await add_user_if_not_exists(user_id)
    try:
        new_id = await _execute_commit("INSERT INTO Habits (user_id, name, description, category) VALUES (?, ?, ?, ?)", (user_id, name, desc, cat), get_last_id=True)
        logger.info(f"Added habit '{name}' (ID: {new_id}) u {user_id}"); return new_id
    except aiosqlite.Error: return None # Error logged in helper

async def get_user_habits(user_id: int) -> List[Tuple[int, str, Optional[str], Optional[str]]]:
    try: return await _fetchall("SELECT habit_id, name, description, category FROM Habits WHERE user_id = ? ORDER BY created_at", (user_id,))
    except aiosqlite.Error: return []

async def find_habit_by_name(user_id: int, name: str) -> Optional[Tuple[int, str]]:
    try: return await _fetchone("SELECT habit_id, name FROM Habits WHERE user_id = ? AND name = ? COLLATE NOCASE", (user_id, name))
    except aiosqlite.Error: return None

async def get_habit_name_by_id(habit_id: int) -> Optional[str]:
    try: r = await _fetchone("SELECT name FROM Habits WHERE habit_id = ?", (habit_id,)); return r[0] if r else None
    except aiosqlite.Error: return None

async def delete_habit_and_log(habit_id: int, user_id: int) -> bool:
    logger.warning(f"Attempt delete habit {habit_id} user {user_id}")
    try:
        rc = await _execute_commit("DELETE FROM Habits WHERE habit_id = ? AND user_id = ?", (habit_id, user_id))
        if rc > 0: logger.info(f"Deleted habit {habit_id} u {user_id}."); return True
        else: logger.warning(f"Habit {habit_id} not found/wrong user {user_id} for delete."); return False
    except aiosqlite.Error: return False

async def update_habit_db(habit_id: int, user_id: int, field: str, value: Optional[str]) -> bool:
    if field not in ("name", "description", "category"): logger.error(f"Invalid field update '{field}'"); return False
    if field == "name" and not value: logger.error("Habit name cannot be empty."); return False
    sql = f"UPDATE Habits SET {field} = ? WHERE habit_id = ? AND user_id = ?"
    try:
        rc = await _execute_commit(sql, (value, habit_id, user_id))
        if rc > 0: logger.info(f"Updated '{field}' for habit {habit_id}."); return True
        else: logger.warning(f"Update failed: Habit {habit_id} not found/wrong user {user_id}."); return False
    except aiosqlite.Error: return False

# --- Log ---
async def mark_habit_done_db(user_id: int, habit_id: int, log_date: date) -> str:
    sql = "INSERT INTO HabitLog (habit_id, user_id, log_date, status) VALUES (?, ?, ?, 'done') ON CONFLICT(habit_id, user_id, log_date) DO UPDATE SET status = 'done' WHERE status != 'done'"
    try: rc = await _execute_commit(sql, (habit_id, user_id, log_date.isoformat())); return "success" if rc > 0 else "already_done"
    except aiosqlite.Error: return "error"

async def get_todays_habit_statuses(user_id: int, today_date: date) -> Dict[int, str]:
    statuses = {}
    try:
        habits = await get_user_habits(user_id)
        if not habits: return {}
        all_ids = [h[0] for h in habits]; placeholders = ','.join('?' * len(all_ids))
        query = f"SELECT habit_id, status FROM HabitLog WHERE user_id=? AND log_date=? AND habit_id IN ({placeholders})"
        params = (user_id, today_date.isoformat()) + tuple(all_ids)
        logged = {r[0]: r[1] for r in await _fetchall(query, params)}
        for hid in all_ids: statuses[hid] = logged.get(hid, 'pending')
        return statuses
    except aiosqlite.Error: return {}

async def get_habit_log(user_id: int, habit_id: Optional[int]=None, limit: int=30, offset: int=0) -> List[Tuple[date, str, str]]:
    entries = []
    try:
        sql = "SELECT hl.log_date, h.name, hl.status FROM HabitLog hl JOIN Habits h ON hl.habit_id = h.habit_id WHERE hl.user_id = ?"
        params: List[Any] = [user_id]
        if habit_id: sql += " AND hl.habit_id = ?"; params.append(habit_id)
        sql += " ORDER BY hl.log_date DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        for row in await _fetchall(sql, tuple(params)):
            try: entries.append((date.fromisoformat(row[0]), row[1], row[2]))
            except (ValueError, TypeError): logger.warning(f"Skipping log entry invalid date: {row}")
        return entries
    except aiosqlite.Error: return []

async def get_habit_log_count(user_id: int, habit_id: Optional[int] = None) -> int:
    try:
        sql = "SELECT COUNT(*) FROM HabitLog WHERE user_id = ?"
        params: List[Any] = [user_id]
        if habit_id: sql += " AND habit_id = ?"; params.append(habit_id)
        r = await _fetchone(sql, tuple(params)); return r[0] if r else 0
    except aiosqlite.Error: return 0

async def get_completion_stats(user_id: int, days_back: int = 30) -> Dict[int, Dict[str, Any]]:
    stats: Dict[int, Dict[str, Any]] = {}
    end_date = date.today(); start_date = end_date - timedelta(days=days_back - 1)
    start_str, end_str = start_date.isoformat(), end_date.isoformat()
    try:
        user_habits = await get_user_habits(user_id);
        if not user_habits: return {}
        habit_ids = [h[0] for h in user_habits]; placeholders = ','.join('?' * len(habit_ids))
        sql = f"SELECT habit_id, log_date, status FROM HabitLog WHERE user_id=? AND habit_id IN ({placeholders}) AND log_date BETWEEN ? AND ?"
        params = (user_id,) + tuple(habit_ids) + (start_str, end_str)
        logs_by_h: Dict[int, Dict[date, str]] = {hid: {} for hid in habit_ids}
        for hid, date_str, status in await _fetchall(sql, params):
            try: logs_by_h[hid][date.fromisoformat(date_str)] = status
            except (ValueError, TypeError): pass # Ignore invalid dates

        num_days = (end_date - start_date).days + 1
        for hid, name, _, _ in user_habits:
            logs = logs_by_h.get(hid, {})
            done_cnt, cur_s, max_s, tmp_s = 0, 0, 0, 0; s_active = True
            for i in range(num_days):
                d = end_date - timedelta(days=i)
                if logs.get(d) == 'done': done_cnt += 1; tmp_s += 1
                else:
                    if i == 0: cur_s = 0 # Reset current if today missed
                    s_active = False; max_s = max(max_s, tmp_s); tmp_s = 0
                if i == 0 and s_active: cur_s = tmp_s # Set current streak if today done
            max_s = max(max_s, tmp_s) # Check last ongoing streak
            rate = round((done_cnt / num_days) * 100, 1) if num_days > 0 else 0
            stats[hid] = {"name": name, "done_count": done_cnt, "total_days": num_days, "completion_rate": rate, "current_streak": cur_s, "max_streak": max_s}
        return stats
    except aiosqlite.Error: return {}

# --- Reminders ---
async def add_or_update_reminder_db(user_id: int, habit_id: int, reminder_time: time, job_name: str) -> bool:
    await add_user_if_not_exists(user_id)
    time_str = reminder_time.strftime('%H:%M:%S')
    try:
        # Verify habit exists for user
        if not await _fetchone("SELECT 1 FROM Habits WHERE habit_id = ? AND user_id = ?", (habit_id, user_id)):
             logger.warning(f"Reminder attempt bad habit/user: h {habit_id}, u {user_id}"); return False
        sql = "INSERT INTO Reminders (user_id, habit_id, reminder_time, job_name) VALUES (?, ?, ?, ?) ON CONFLICT(habit_id) DO UPDATE SET reminder_time=excluded.reminder_time, job_name=excluded.job_name"
        await _execute_commit(sql, (user_id, habit_id, time_str, job_name))
        logger.info(f"Add/Update reminder h {habit_id}, job {job_name}"); return True
    except aiosqlite.Error: return False

async def get_reminder_by_habit_id(habit_id: int) -> Optional[Tuple[int, time, str]]:
    try:
        row = await _fetchone("SELECT user_id, reminder_time, job_name FROM Reminders WHERE habit_id = ?", (habit_id,))
        if row:
            try: return row[0], datetime.strptime(row[1], '%H:%M:%S').time(), row[2]
            except (ValueError, TypeError): logger.error(f"Invalid time format '{row[1]}' in DB h {habit_id}."); return None
        return None
    except aiosqlite.Error: return None

async def get_all_reminders() -> List[Tuple[int, int, time, str]]:
    reminders = []
    try:
        for row in await _fetchall("SELECT user_id, habit_id, reminder_time, job_name FROM Reminders"):
             try: reminders.append((row[0], row[1], datetime.strptime(row[2], '%H:%M:%S').time(), row[3]))
             except (ValueError, TypeError): logger.warning(f"Skipping reminder invalid time fmt: {row}")
        return reminders
    except aiosqlite.Error: return []

async def remove_reminder_by_habit_id(habit_id: int) -> Optional[str]:
    job_name = None
    try:
        row = await _fetchone("SELECT job_name FROM Reminders WHERE habit_id = ?", (habit_id,))
        if row:
            job_name = row[0]
            rc = await _execute_commit("DELETE FROM Reminders WHERE habit_id = ?", (habit_id,))
            if rc > 0: logger.info(f"Removed reminder h {habit_id} from DB.")
            else: logger.warning(f"Found job '{job_name}' but failed delete rem h {habit_id}."); job_name = None # Indicate delete fail
        else: logger.warning(f"Remove rem attempt: h {habit_id} not found.")
        return job_name
    except aiosqlite.Error: return None

async def get_user_reminders(user_id: int) -> List[Tuple[int, time, str]]:
    reminders = []
    try:
        sql = "SELECT r.habit_id, r.reminder_time, r.job_name FROM Reminders r JOIN Habits h ON r.habit_id = h.habit_id WHERE r.user_id = ? ORDER BY r.reminder_time"
        for row in await _fetchall(sql, (user_id,)):
             try: reminders.append((row[0], datetime.strptime(row[1], '%H:%M:%S').time(), row[2]))
             except ValueError: logger.warning(f"Skipping user reminder invalid time: {row}")
        return reminders
    except aiosqlite.Error: return []