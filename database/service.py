import logging
import aiosqlite
from typing import Optional, List, Tuple, Dict, Any
from datetime import date, time, datetime, timedelta
from .connection import execute_query, fetch_one, fetch_all


class DatabaseService:
    """
    Database service that provides dependency injection for database operations.
    This replaces the global database connection approach with a more testable and maintainable design.
    """
    
    def __init__(self, connection: Optional[aiosqlite.Connection] = None):
        """
        Initialize the database service.
        
        Args:
            connection: Optional aiosqlite connection. If not provided, 
                       will use global connection via connection module.
        """
        self._conn = connection
        self.log = logging.getLogger(self.__class__.__name__)
    
    async def get_connection(self) -> aiosqlite.Connection:
        """
        Get the database connection. If initialized with a connection, returns that,
        otherwise falls back to the global connection from the connection module.
        """
        if self._conn:
            return self._conn
        # Fallback to global connection if needed
        from .connection import get_db_connection
        return await get_db_connection()
    
    async def add_user_if_not_exists(self, user_id: int) -> bool:
        """
        Adds user if not exists. Returns True if inserted, False if already exists.
        
        Args:
            user_id: Telegram user ID to check/add
            
        Returns:
            True if user was newly added, False if already existed
        """
        sql = "INSERT OR IGNORE INTO Users (user_id) VALUES (?)"
        try:
            result = await execute_query(sql, (user_id,))
            if result is not None and result > 0:
                self.log.info(f"New user: {user_id}")
                return True
            elif result == 0:
                self.log.debug(f"User exists: {user_id}")
                return False
            else:
                self.log.warning(f"Add user {user_id} unexpected rc: {result}")
                return False
        except aiosqlite.Error:
            return False  # Logged by execute_query
    
    async def add_habit(self, user_id: int, name: str, description: Optional[str] = None, category: Optional[str] = None) -> Optional[int]:
        """
        Adds new habit. Returns habit_id or None.
        
        Args:
            user_id: Telegram user ID
            name: Habit name
            description: Optional habit description
            category: Optional habit category
            
        Returns:
            The newly created habit ID or None if failed
        """
        try:
            await self.add_user_if_not_exists(user_id)
            sql = "INSERT INTO Habits (user_id, name, description, category) VALUES (?, ?, ?, ?)"
            new_id = await execute_query(sql, (user_id, name, description, category), return_last_id=True)
            if new_id is not None:
                self.log.info(f"Added habit '{name}' (ID:{new_id}) u:{user_id}")
                return new_id
            else:
                self.log.error(f"Failed get last ID add habit u:{user_id}")
                return None
        except aiosqlite.Error:
            return None  # Logged by execute_query
    
    async def get_user_habits(self, user_id: int) -> List[Tuple[int, str, Optional[str], Optional[str]]]:
        """
        Retrieves all habits for user.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            List of tuples (habit_id, name, description, category)
        """
        sql = "SELECT habit_id, name, description, category FROM Habits WHERE user_id = ? ORDER BY created_at ASC"
        try:
            return await fetch_all(sql, (user_id,))
        except aiosqlite.Error:
            return []  # Logged by fetch_all
    
    async def find_habit_by_name(self, user_id: int, name: str) -> Optional[Tuple[int, str]]:
        """
        Finds habit by name (case-insensitive). Returns (hid, name) or None.
        
        Args:
            user_id: Telegram user ID
            name: Habit name to search for
            
        Returns:
            Tuple of (habit_id, name) or None if not found
        """
        sql = "SELECT habit_id, name FROM Habits WHERE user_id = ? AND name = ? COLLATE NOCASE LIMIT 1"
        try:
            return await fetch_one(sql, (user_id, name))
        except aiosqlite.Error:
            return None  # Logged by fetch_one
    
    async def get_habit_name_by_id(self, habit_id: int) -> Optional[str]:
        """
        Retrieves habit name by ID.
        
        Args:
            habit_id: Habit ID to look up
            
        Returns:
            Habit name or None if not found
        """
        sql = "SELECT name FROM Habits WHERE habit_id = ?"
        try:
            result = await fetch_one(sql, (habit_id,))
            return result[0] if result else None
        except aiosqlite.Error:
            return None  # Logged by fetch_one
    
    async def delete_habit_and_log(self, habit_id: int, user_id: int) -> bool:
        """
        Deletes habit, logs, reminders (CASCADE). Checks ownership. Returns True/False.
        
        Args:
            habit_id: Habit ID to delete
            user_id: Telegram user ID (for ownership verification)
            
        Returns:
            True if successfully deleted, False otherwise
        """
        self.log.warning(f"Attempt del habit {habit_id} u:{user_id}")
        sql = "DELETE FROM Habits WHERE habit_id = ? AND user_id = ?"
        try:
            result = await execute_query(sql, (habit_id, user_id))
            if result is not None and result > 0:
                self.log.info(f"Deleted habit {habit_id} (cascaded) u:{user_id}.")
                return True
            elif result == 0:
                self.log.warning(f"Habit {habit_id} not found or u:{user_id} mismatch delete.")
                return False
            else:
                self.log.error(f"Del habit {habit_id} unexpected rc: {result}")
                return False
        except aiosqlite.Error:
            return False  # Logged by execute_query
    
    async def update_habit(self, habit_id: int, user_id: int, field: str, value: Optional[str]) -> bool:
        """
        Updates 'name', 'description', or 'category'. Checks ownership.
        
        Args:
            habit_id: Habit ID to update
            user_id: Telegram user ID (for ownership verification)
            field: Field to update ('name', 'description', or 'category')
            value: New value for the field
            
        Returns:
            True if successfully updated, False otherwise
        """
        valid = ("name", "description", "category")
        if field not in valid:
            self.log.error(f"Invalid update field: '{field}'")
            return False
        if field == "name" and not value:
            self.log.error(f"Attempt set name empty/None h:{habit_id}.")
            return False

        sql = f"UPDATE Habits SET {field} = ? WHERE habit_id = ? AND user_id = ?"  # Safe f-string
        try:
            result = await execute_query(sql, (value, habit_id, user_id))
            if result is not None and result > 0:
                self.log.info(f"Updated '{field}' h:{habit_id} u:{user_id}.")
                return True
            elif result == 0:
                self.log.warning(f"Habit {habit_id} not found/u:{user_id} mismatch update '{field}'.")
                return False
            else:
                self.log.error(f"Update habit {habit_id} unexpected rc: {result}")
                return False
        except aiosqlite.Error:
            return False  # Logged by execute_query
    
    async def mark_habit_done(self, user_id: int, habit_id: int, log_date: date) -> str:
        """
        Mark a habit as done for a specific date.
        
        Args:
            user_id: Telegram user ID
            habit_id: Habit ID to mark as done
            log_date: Date to mark as done
            
        Returns:
            'success' if marked, 'already_done' if already marked, 'error' if failed
        """
        date_str = log_date.isoformat()
        sql = "INSERT INTO HabitLog (habit_id,user_id,log_date,status) VALUES (?,?,?,'done') ON CONFLICT(habit_id,user_id,log_date) DO UPDATE SET status='done' WHERE status!='done'"
        try:
            result = await execute_query(sql, (habit_id, user_id, date_str))
            if result is not None and result > 0:
                self.log.info(f"Marked h:{habit_id} done u:{user_id} on {date_str}")
                return "success"
            elif result == 0:
                self.log.debug(f"H:{habit_id} already done u:{user_id} on {date_str}")
                return "already_done"
            else:
                self.log.error(f"Mark done h:{habit_id} unexp rc: {result}")
                return "error"
        except aiosqlite.Error:
            return "error"  # Logged by execute_query
    
    async def get_todays_habit_statuses(self, user_id: int, today: date) -> Dict[int, str]:
        """
        Get the status of all user habits for a specific date.
        
        Args:
            user_id: Telegram user ID
            today: Date to get statuses for
            
        Returns:
            Dictionary mapping habit_id to status ('done', 'pending', 'skipped')
        """
        statuses: Dict[int, str] = {}
        date_str = today.isoformat()
        try:
            # Single query with LEFT JOIN to get all habits and their status for the given date
            sql = """
            SELECT h.habit_id, COALESCE(hl.status, 'pending') as status
            FROM Habits h
            LEFT JOIN HabitLog hl ON h.habit_id = hl.habit_id 
                AND hl.log_date = ? AND hl.user_id = ?
            WHERE h.user_id = ?
            ORDER BY h.created_at
            """
            params = (date_str, user_id, user_id)
            rows = await fetch_all(sql, params)
            
            for habit_id, status in rows:
                statuses[habit_id] = status
            
            return statuses
        except aiosqlite.Error:
            return {}  # Logged by helpers
    
    async def get_habit_log(self, user_id: int, habit_id: Optional[int] = None, limit: int = 30, offset: int = 0) -> List[Tuple[date, str, str]]:
        """
        Get log entries for a user's habits.
        
        Args:
            user_id: Telegram user ID
            habit_id: Optional specific habit ID to filter by
            limit: Number of entries to return
            offset: Number of entries to skip (for pagination)
            
        Returns:
            List of tuples (date, habit_name, status)
        """
        entries: List[Tuple[date, str, str]] = []
        try:
            sql = "SELECT hl.log_date, h.name, hl.status FROM HabitLog hl JOIN Habits h ON hl.habit_id = h.habit_id WHERE hl.user_id = ?"
            params: List[Any] = [user_id]
            
            if habit_id is not None:
                sql += " AND hl.habit_id = ?"
                params.append(habit_id)
            
            sql += " ORDER BY hl.log_date DESC, h.name ASC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            
            for date_str, habit_name, status in await fetch_all(sql, tuple(params)):
                try:
                    entries.append((date.fromisoformat(date_str), habit_name, status))
                except (ValueError, TypeError):
                    self.log.warning(f"Skip log invalid date: d='{date_str}', h='{habit_name}'")
            
            return entries
        except aiosqlite.Error:
            return []  # Logged by fetch_all

    async def get_habit_log_count(self, user_id: int, habit_id: Optional[int] = None) -> int:
        """
        Get count of log entries for a user's habits.
        
        Args:
            user_id: Telegram user ID
            habit_id: Optional specific habit ID to filter by
            
        Returns:
            Count of log entries
        """
        try:
            sql = "SELECT COUNT(*) FROM HabitLog WHERE user_id = ?"
            params: List[Any] = [user_id]
            if habit_id is not None:
                sql += " AND habit_id = ?"
                params.append(habit_id)
            result = await fetch_one(sql, tuple(params))
            return result[0] if result else 0
        except aiosqlite.Error:
            return 0  # Logged by fetch_one

    async def get_completion_stats(self, user_id: int, days: int = 30) -> Dict[int, Dict[str, Any]]:
        """
        Get completion statistics for user's habits.
        
        Args:
            user_id: Telegram user ID
            days: Number of days to calculate stats for
            
        Returns:
            Dictionary mapping habit_id to statistics dict
        """
        stats: Dict[int, Dict[str, Any]] = {}
        if days <= 0:
            return {}
        
        end_date = date.today()
        start_date = end_date - timedelta(days=days-1)
        start_s, end_s = start_date.isoformat(), end_date.isoformat()
        
        try:
            habits = await self.get_user_habits(user_id)
            if not habits:
                return {}
            
            habit_ids = [h[0] for h in habits]
            placeholders = ','.join('?' * len(habit_ids))
            sql = f"SELECT habit_id, log_date FROM HabitLog WHERE user_id=? AND habit_id IN ({placeholders}) AND log_date BETWEEN ? AND ? AND status='done' ORDER BY log_date DESC"
            params = (user_id,) + tuple(habit_ids) + (start_s, end_s)
            raw_logs = await fetch_all(sql, params)
            
            logs_by_habit: Dict[int, Dict[date, bool]] = {hid: {} for hid in habit_ids}
            for hid, ds in raw_logs:
                try:
                    logs_by_habit[hid][date.fromisoformat(ds)] = True
                except (ValueError, TypeError):
                    self.log.warning(f"Skip stats log invalid date: d='{ds}', h='{hid}'")

            num_days = (end_date - start_date).days + 1
            for h_id, h_name, _, _ in habits:
                h_logs = logs_by_habit.get(h_id, {})
                done_count, cur_streak, max_streak, temp_streak = 0, 0, 0, 0
                is_current_active = True
                
                for i in range(num_days):
                    d = end_date - timedelta(days=i)
                    if d in h_logs:
                        done_count += 1
                        temp_streak += 1
                    else:
                        max_streak = max(max_streak, temp_streak)
                        temp_streak = 0
                        if i == 0:  # Check if streak broken today
                            is_current_active = False
                
                max_streak = max(max_streak, temp_streak)  # Final check for streak ending today
                current_streak = temp_streak if is_current_active and (end_date in h_logs) else (temp_streak if is_current_active and not h_logs else 0)
                rate = round((done_count / num_days) * 100, 1) if num_days > 0 else 0
                
                stats[h_id] = {
                    "name": h_name,
                    "done_count": done_count,
                    "total_days": num_days,
                    "completion_rate": rate,
                    "current_streak": current_streak,
                    "max_streak": max_streak
                }
            
            return stats
        except aiosqlite.Error:
            return {}  # Logged by helpers
    
    async def add_or_update_reminder(self, user_id: int, habit_id: int, reminder_time: time, job_name: str) -> bool:
        """
        Adds or updates a reminder for a habit.
        
        Args:
            user_id: Telegram user ID
            habit_id: Habit ID to set reminder for
            reminder_time: Time for the reminder
            job_name: Name for the scheduled job
            
        Returns:
            True if successful, False otherwise
        """
        await self.add_user_if_not_exists(user_id)
        time_str = reminder_time.strftime('%H:%M:%S')
        sql = "INSERT INTO Reminders (user_id,habit_id,reminder_time,job_name) VALUES (?,?,?,?) ON CONFLICT(habit_id) DO UPDATE SET reminder_time=excluded.reminder_time, job_name=excluded.job_name, user_id=excluded.user_id"
        try:
            await execute_query(sql, (user_id, habit_id, time_str, job_name))
            self.log.info(f"Add/Upd rem h:{habit_id} (Job:{job_name}) u:{user_id} at {time_str}")
            return True
        except aiosqlite.IntegrityError as e:
            self.log.error(f"Fail add/upd rem h:{habit_id}: IntegrityErr (Habit del?): {e}")
            return False
        except aiosqlite.Error:
            return False  # Logged by execute_query
    
    async def get_reminder_by_habit_id(self, habit_id: int) -> Optional[Tuple[int, time, str]]:
        """
        Gets reminder info for a specific habit ID.
        
        Args:
            habit_id: Habit ID to look up
            
        Returns:
            Tuple of (user_id, reminder_time, job_name) or None if not found
        """
        sql = "SELECT user_id, reminder_time, job_name FROM Reminders WHERE habit_id = ?"
        try:
            row = await fetch_one(sql, (habit_id,))
            if row:
                user_id, time_str, job_name = row
                try:
                    return user_id, datetime.strptime(time_str, '%H:%M:%S').time(), job_name
                except (ValueError, TypeError):
                    self.log.error(f"Invalid time fmt '{time_str}' DB rem h:{habit_id}")
                    return None
            return None
        except aiosqlite.Error:
            return None  # Logged by fetch_one
    
    async def get_user_reminders(self, user_id: int) -> List[Tuple[int, time, str]]:
        """
        Gets active reminders (habit_id, time, job_name) for user.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            List of tuples (habit_id, time, job_name)
        """
        reminders: List[Tuple[int, time, str]] = []
        sql = "SELECT habit_id, reminder_time, job_name FROM Reminders WHERE user_id = ? ORDER BY reminder_time ASC"
        try:
            raw_rems = await fetch_all(sql, (user_id,))
            for habit_id, time_str, job_name in raw_rems:
                try:
                    reminders.append((habit_id, datetime.strptime(time_str, '%H:%M:%S').time(), job_name))
                except (ValueError, TypeError):
                    self.log.warning(f"Skip user rem h:{habit_id} invalid time DB: '{time_str}'")
            return reminders
        except aiosqlite.Error:
            return []  # Logged by fetch_all

    async def get_all_reminders(self) -> List[Tuple[int, int, time, str]]:
        """
        Gets all reminders in the system.
        
        Returns:
            List of tuples (user_id, habit_id, time, job_name)
        """
        reminders: List[Tuple[int, int, time, str]] = []
        sql = "SELECT user_id, habit_id, reminder_time, job_name FROM Reminders ORDER BY user_id, reminder_time"
        try:
            raw_rems = await fetch_all(sql)
            for user_id, habit_id, time_str, job_name in raw_rems:
                try:
                    reminders.append((user_id, habit_id, datetime.strptime(time_str, '%H:%M:%S').time(), job_name))
                except (ValueError, TypeError):
                    self.log.warning(f"Skip rem h:{habit_id} invalid time DB: '{time_str}'")
            return reminders
        except aiosqlite.Error:
            return []  # Logged by fetch_all
    
    async def remove_reminder_by_habit_id(self, habit_id: int) -> Optional[str]:
        """
        Removes a reminder by habit ID.
        
        Args:
            habit_id: Habit ID of the reminder to remove
            
        Returns:
            Job name if successfully removed, None otherwise
        """
        rem_data = await self.get_reminder_by_habit_id(habit_id)
        if not rem_data:
            self.log.warning(f"Attempt rem non-exist rem h:{habit_id}")
            return None
        
        _, _, job_name = rem_data
        sql = "DELETE FROM Reminders WHERE habit_id = ?"
        try:
            result = await execute_query(sql, (habit_id,))
            if result is not None and result > 0:
                self.log.info(f"Removed rem h:{habit_id} (Job:{job_name}) DB.")
                return job_name
            elif result == 0:
                self.log.warning(f"Found rem job '{job_name}' but fail del DB h:{habit_id} (ra=0).")
                return None
            else:
                self.log.error(f"Del rem h:{habit_id} unexpected rc: {result}")
                return None
        except aiosqlite.Error:
            return None  # Logged by execute_query