import aiosqlite,os,logging,asyncio
from config import settings
from typing import Optional,List,Tuple,Any

log=logging.getLogger(__name__)
_db:Optional[aiosqlite.Connection]=None
DB_CLOSE_TIMEOUT=1.5 # Seconds grace period for close

async def connect_db():
	global _db
	if _db:
		try:
			await asyncio.wait_for(_db.execute("PRAGMA user_version;"),timeout=1.0)
			log.debug("Reusing DB conn.")
			return
		except (aiosqlite.Error,AttributeError,RuntimeError,asyncio.TimeoutError) as e:
			log.warning(f"DB check fail ('{type(e).__name__}'). Reconnecting.")
			old_conn=_db; _db=None
			if old_conn:
				try: await asyncio.wait_for(old_conn.close(),timeout=0.5); log.debug("Old problematic DB conn closed.")
				except Exception: log.warning("Ignoring err closing old conn during reconnect.")
	log.info(f"Connecting DB: {settings.database_file}")
	try:
		db_dir=os.path.dirname(settings.database_file)
		if db_dir and not os.path.exists(db_dir): os.makedirs(db_dir); log.info(f"Created DB dir: {db_dir}")
		db=await aiosqlite.connect(settings.database_file,timeout=10)
		await db.execute("PRAGMA journal_mode=WAL;")
		await db.execute("PRAGMA foreign_keys = ON;")
		await db.execute("PRAGMA synchronous = NORMAL;")
		_db=db; log.info("Global DB conn established.")
	except (aiosqlite.Error, OSError) as e:
		log.critical(f"DB conn failed: {e}",exc_info=True); _db=None
		raise ConnectionError(f"Failed connect DB: {e}")

async def close_db():
	global _db
	conn=_db
	if conn:
		if getattr(conn,'_closed',False): log.debug("close_db: Already closed."); _db=None; return
		log.info(f"Attempting DB close (Timeout: {DB_CLOSE_TIMEOUT}s)...")
		try:
			await asyncio.wait_for(conn.close(),timeout=DB_CLOSE_TIMEOUT)
			log.info("DB conn closed successfully within timeout.")
		except asyncio.TimeoutError: log.warning(f"DB close timed out after {DB_CLOSE_TIMEOUT}s!")
		except (aiosqlite.Error, RuntimeError) as e: log.error(f"Error closing DB: {e}",exc_info=True)
		except Exception as e: log.error(f"Unexpected err during DB close: {e}",exc_info=True)
		finally: _db=None; log.info("Global _db set None after close attempt.") # Ensure _db is None
	else: log.debug("close_db: Global _db already None.")

async def get_db_connection()->aiosqlite.Connection:
	if not _db: log.error("DB conn requested but global _db is None."); raise ConnectionError("DB conn unavailable.")
	return _db

async def initialize_database():
	log.info(f"Initializing DB schema: {settings.database_file}")
	try:
		async with aiosqlite.connect(settings.database_file,timeout=10) as db:
			await db.execute("PRAGMA journal_mode=WAL;")
			await db.execute("PRAGMA foreign_keys = ON;")
			await db.execute("CREATE TABLE IF NOT EXISTS Users (user_id INTEGER PRIMARY KEY NOT NULL)")
			await db.execute("""
				CREATE TABLE IF NOT EXISTS Habits (
					habit_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, name TEXT NOT NULL,
					description TEXT, category TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
					FOREIGN KEY(user_id) REFERENCES Users(user_id) ON DELETE CASCADE )""")
			await db.execute("CREATE INDEX IF NOT EXISTS idx_habits_user_id ON Habits(user_id)")
			await db.execute("""
				CREATE TABLE IF NOT EXISTS HabitLog (
					log_id INTEGER PRIMARY KEY AUTOINCREMENT, habit_id INTEGER NOT NULL, user_id INTEGER NOT NULL,
					log_date TEXT NOT NULL, status TEXT DEFAULT 'pending' CHECK(status IN ('done','pending','skipped')),
					FOREIGN KEY(habit_id) REFERENCES Habits(habit_id) ON DELETE CASCADE,
					FOREIGN KEY(user_id) REFERENCES Users(user_id) ON DELETE CASCADE,
					UNIQUE(habit_id, user_id, log_date) )""")
			await db.execute("CREATE INDEX IF NOT EXISTS idx_habitlog_user_date ON HabitLog(user_id, log_date)")
			await db.execute("CREATE INDEX IF NOT EXISTS idx_habitlog_habit_date ON HabitLog(habit_id, log_date)")
			await db.execute("""
				CREATE TABLE IF NOT EXISTS Reminders (
					reminder_id INTEGER PRIMARY KEY AUTOINCREMENT, habit_id INTEGER NOT NULL UNIQUE, user_id INTEGER NOT NULL,
					reminder_time TEXT NOT NULL, job_name TEXT UNIQUE NOT NULL,
					FOREIGN KEY(habit_id) REFERENCES Habits(habit_id) ON DELETE CASCADE,
					FOREIGN KEY(user_id) REFERENCES Users(user_id) ON DELETE CASCADE )""")
			await db.execute("CREATE INDEX IF NOT EXISTS idx_reminders_user_id ON Reminders(user_id)")
			await db.commit()
			log.info("DB schema check/init complete.")
	except (aiosqlite.Error, OSError) as e:
		log.error(f"DB schema init failed: {e}",exc_info=True);
		raise ConnectionError(f"Failed init DB schema: {e}")

async def execute_query(sql:str,params:tuple=(),*,return_last_id:bool=False)->int|None:
	db=await get_db_connection()
	try:
		async with await db.execute(sql,params) as cur: rc,lid=cur.rowcount,cur.lastrowid if return_last_id else None
		await db.commit(); return lid if return_last_id else rc
	except aiosqlite.Error as e:
		log.error(f"DB Exec err: SQL='{sql[:60]}...', P={params}, E='{e}'",exc_info=True)
		try: await db.rollback(); log.warning("Tx rolled back.")
		except aiosqlite.Error as rb_e: log.error(f"Rollback fail: {rb_e}")
		raise

async def fetch_one(sql:str,params:tuple=())->Tuple|None:
	db=await get_db_connection()
	try:
		async with await db.execute(sql,params) as cur: return await cur.fetchone()
	except aiosqlite.Error as e: log.error(f"DB FetchOne err: SQL='{sql[:60]}...', P={params}, E='{e}'",exc_info=True); raise

async def fetch_all(sql:str,params:tuple=())->List[Tuple]:
	db=await get_db_connection()
	try:
		async with await db.execute(sql,params) as cur: return await cur.fetchall()
	except aiosqlite.Error as e: log.error(f"DB FetchAll err: SQL='{sql[:60]}...', P={params}, E='{e}'",exc_info=True); raise