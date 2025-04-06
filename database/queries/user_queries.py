import logging,aiosqlite
from ..connection import _e

log=logging.getLogger(__name__)

async def add_user_if_not_exists(uid: int) -> bool:
	"""Adds user if not exists. Returns True if inserted."""
	sql="INSERT OR IGNORE INTO Users (user_id) VALUES (?)"
	try:
		ra=await _e(sql,(uid,))
		if ra is not None and ra>0: log.info(f"New user: {uid}"); return True
		elif ra==0: log.debug(f"User exists: {uid}"); return False
		else: log.warning(f"Add user {uid} unexpected rc: {ra}"); return False
	except aiosqlite.Error: return False # Logged by _e