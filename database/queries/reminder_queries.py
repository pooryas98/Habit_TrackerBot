import logging,aiosqlite
from datetime import time,datetime
from typing import List,Tuple,Optional
from ..connection import _e,_fo,_fa
from .user_queries import add_user_if_not_exists

log=logging.getLogger(__name__)

async def add_or_update_reminder_db(uid: int, hid: int, rem_time: time, jname: str) -> bool:
	"""Adds/updates reminder (INSERT ON CONFLICT)."""
	await add_user_if_not_exists(uid)
	ts=rem_time.strftime('%H:%M:%S')
	sql="INSERT INTO Reminders (user_id,habit_id,reminder_time,job_name) VALUES (?,?,?,?) ON CONFLICT(habit_id) DO UPDATE SET reminder_time=excluded.reminder_time, job_name=excluded.job_name, user_id=excluded.user_id"
	try: await _e(sql,(uid,hid,ts,jname)); log.info(f"Add/Upd rem h:{hid} (Job:{jname}) u:{uid} at {ts}"); return True
	except aiosqlite.IntegrityError as e: log.error(f"Fail add/upd rem h:{hid}: IntegrityErr (Habit del?): {e}"); return False
	except aiosqlite.Error: return False # Logged by _e

async def get_reminder_by_habit_id(hid: int) -> Optional[Tuple[int, time, str]]:
	"""Gets reminder (uid, time, job_name) for habit ID."""
	sql="SELECT user_id, reminder_time, job_name FROM Reminders WHERE habit_id = ?"
	try:
		row=await _fo(sql,(hid,))
		if row:
			uid,ts,jname=row
			try: return uid,datetime.strptime(ts,'%H:%M:%S').time(),jname
			except (ValueError,TypeError): log.error(f"Invalid time fmt '{ts}' DB rem h:{hid}"); return None
		return None
	except aiosqlite.Error: return None # Logged by _fo

async def get_all_reminders() -> List[Tuple[int, int, time, str]]:
	"""Gets all reminders (uid, hid, time, job_name)."""
	rems:List[Tuple[int,int,time,str]]=[]
	sql="SELECT user_id, habit_id, reminder_time, job_name FROM Reminders ORDER BY user_id, reminder_time"
	try:
		raw_rems=await _fa(sql)
		for uid,hid,ts,jname in raw_rems:
			try: rems.append((uid,hid,datetime.strptime(ts,'%H:%M:%S').time(),jname))
			except (ValueError,TypeError): log.warning(f"Skip rem h:{hid} invalid time DB: '{ts}'")
		return rems
	except aiosqlite.Error: return [] # Logged by _fa

async def remove_reminder_by_habit_id(hid: int) -> Optional[str]:
	"""Deletes reminder by habit ID. Returns job_name if found/deleted."""
	rem_data=await get_reminder_by_habit_id(hid)
	if not rem_data: log.warning(f"Attempt rem non-exist rem h:{hid}"); return None
	_,_,jname=rem_data; sql="DELETE FROM Reminders WHERE habit_id = ?"
	try:
		ra=await _e(sql,(hid,))
		if ra is not None and ra > 0: log.info(f"Removed rem h:{hid} (Job:{jname}) DB."); return jname
		elif ra==0: log.warning(f"Found rem job '{jname}' but fail del DB h:{hid} (ra=0)."); return None
		else: log.error(f"Del rem h:{hid} unexpected rc: {ra}"); return None
	except aiosqlite.Error: return None # Logged by _e

async def get_user_reminders(uid: int) -> List[Tuple[int, time, str]]:
	"""Gets active reminders (hid, time, job_name) for user."""
	rems:List[Tuple[int,time,str]]=[]
	sql="SELECT habit_id, reminder_time, job_name FROM Reminders WHERE user_id = ? ORDER BY reminder_time ASC"
	try:
		raw_rems=await _fa(sql,(uid,))
		for hid,ts,jname in raw_rems:
			 try: rems.append((hid,datetime.strptime(ts,'%H:%M:%S').time(),jname))
			 except (ValueError,TypeError): log.warning(f"Skip user rem h:{hid} invalid time DB: '{ts}'")
		return rems
	except aiosqlite.Error: return [] # Logged by _fa