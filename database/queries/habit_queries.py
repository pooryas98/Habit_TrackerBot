import logging,aiosqlite
from typing import List,Tuple,Optional
from ..connection import _e,_fo,_fa
from .user_queries import add_user_if_not_exists

log=logging.getLogger(__name__)

async def add_habit_db(uid: int, name: str, desc: Optional[str]=None, cat: Optional[str]=None) -> Optional[int]:
	"""Adds new habit. Returns habit_id or None."""
	try:
		await add_user_if_not_exists(uid)
		sql="INSERT INTO Habits (user_id,name,description,category) VALUES (?,?,?,?)"
		new_id=await _e(sql,(uid,name,desc,cat),last_id=True)
		if new_id is not None: log.info(f"Added habit '{name}' (ID:{new_id}) u:{uid}"); return new_id
		else: log.error(f"Failed get last ID add habit u:{uid}"); return None
	except aiosqlite.Error: return None # Logged by _e

async def get_user_habits(uid: int) -> List[Tuple[int, str, Optional[str], Optional[str]]]:
	"""Retrieves all habits for user."""
	sql="SELECT habit_id, name, description, category FROM Habits WHERE user_id = ? ORDER BY created_at ASC"
	try: return await _fa(sql,(uid,))
	except aiosqlite.Error: return [] # Logged by _fa

async def find_habit_by_name(uid: int, name: str) -> Optional[Tuple[int, str]]:
	"""Finds habit by name (case-insensitive). Returns (hid, name) or None."""
	sql="SELECT habit_id, name FROM Habits WHERE user_id = ? AND name = ? COLLATE NOCASE LIMIT 1"
	try: return await _fo(sql,(uid,name))
	except aiosqlite.Error: return None # Logged by _fo

async def get_habit_name_by_id(hid: int) -> Optional[str]:
	"""Retrieves habit name by ID."""
	sql="SELECT name FROM Habits WHERE habit_id = ?"
	try: res=await _fo(sql,(hid,)); return res[0] if res else None
	except aiosqlite.Error: return None # Logged by _fo

async def delete_habit_and_log(hid: int, uid: int) -> bool:
	"""Deletes habit, logs, reminders (CASCADE). Checks ownership. Returns True/False."""
	log.warning(f"Attempt del habit {hid} u:{uid}")
	sql="DELETE FROM Habits WHERE habit_id = ? AND user_id = ?"
	try:
		ra=await _e(sql,(hid,uid))
		if ra is not None and ra>0: log.info(f"Deleted habit {hid} (cascaded) u:{uid}."); return True
		elif ra==0: log.warning(f"Habit {hid} not found or u:{uid} mismatch delete."); return False
		else: log.error(f"Del habit {hid} unexpected rc: {ra}"); return False
	except aiosqlite.Error: return False # Logged by _e

async def update_habit_db(hid: int, uid: int, field: str, value: Optional[str]) -> bool:
	"""Updates 'name', 'description', or 'category'. Checks ownership."""
	valid=("name","description","category")
	if field not in valid: log.error(f"Invalid update field: '{field}'"); return False
	if field=="name" and not value: log.error(f"Attempt set name empty/None h:{hid}."); return False
	sql=f"UPDATE Habits SET {field} = ? WHERE habit_id = ? AND user_id = ?" # Safe f-string
	try:
		ra=await _e(sql,(value,hid,uid))
		if ra is not None and ra>0: log.info(f"Updated '{field}' h:{hid} u:{uid}."); return True
		elif ra==0: log.warning(f"Habit {hid} not found/u:{uid} mismatch update '{field}'."); return False
		else: log.error(f"Update habit {hid} unexpected rc: {ra}"); return False
	except aiosqlite.Error: return False # Logged by _e