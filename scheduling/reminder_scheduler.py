import logging,datetime,aiosqlite
from typing import Optional,Callable,Coroutine,Any
from telegram.ext import JobQueue,Job
from database import get_all_reminders,get_habit_name_by_id,remove_reminder_by_habit_id
from utils import constants as c

log=logging.getLogger(__name__)

def _jname(uid: int, hid: int) -> str: return f"{c.JOB_PREFIX_REMINDER}{uid}_{hid}"

def _rm_job_by_name(jq: JobQueue, name: str) -> bool:
	"""Removes jobs by name. Returns True if any removed."""
	jobs:tuple[Job,...]=jq.get_jobs_by_name(name)
	if not jobs: return False
	rm_count=0
	for j in jobs: j.schedule_removal(); rm_count+=1; log.info(f"Sched job '{name}' (ID:{j.id}) for removal.")
	return rm_count>0

async def sched_all_rems(db_conn: aiosqlite.Connection, jq: JobQueue):
	"""Schedules all reminders from DB on startup."""
	log.info("Scheduling reminders from DB...")
	n_sched,n_skip_del,n_skip_time,n_fail=0,0,0,0
	try:
		all_rems=await get_all_reminders() # [(uid, hid, time, job_name_db)]
		if not all_rems: log.info("No reminders in DB."); return
		log.info(f"Found {len(all_rems)} reminders. Scheduling...")
		try: from handlers.reminders.jobs import rem_cb
		except ImportError: log.critical("! Import rem_cb failed! Reminders NOT scheduled."); return
		for uid,hid,rem_time,stored_jname in all_rems:
			expected_jname=_jname(uid,hid)
			try:
				hname=await get_habit_name_by_id(hid)
				if not hname: log.warning(f"Habit {hid} for rem (u:{uid}) missing. Skip & rm orphan."); n_skip_del+=1; await remove_reminder_by_habit_id(hid); _rm_job_by_name(jq,expected_jname); _rm_job_by_name(jq,stored_jname) if stored_jname and stored_jname!=expected_jname else None; continue
			except (aiosqlite.Error,ConnectionError) as e: log.error(f"DB err check h:{hid} exist sched: {e}. Skip."); n_fail+=1; continue
			_rm_job_by_name(jq,expected_jname) # Clean existing
			if stored_jname and stored_jname!=expected_jname: log.warning(f"Stored jname '{stored_jname}'!=expected '{expected_jname}' h:{hid}. Removing both."); _rm_job_by_name(jq,stored_jname)
			try: # Schedule new job
				jdata={"user_id":uid,"habit_id":hid,"habit_name":hname}
				job=jq.run_daily(callback=rem_cb,time=rem_time,chat_id=uid,user_id=uid,name=expected_jname,data=jdata)
				if job: n_sched+=1; log.debug(f"Sched job '{expected_jname}' h:{hid} at {rem_time:%H:%M:%S}")
				else: log.error(f"Failed sched job '{expected_jname}' (run_daily=None)."); n_fail+=1
			except ValueError as e: log.error(f"ValueError sched job '{expected_jname}': {e}. Time={rem_time}"); n_fail+=1
			except Exception as e: log.error(f"Err sched job '{expected_jname}': {e}",exc_info=True); n_fail+=1
		log.info(f"Rem sched done. Sched:{n_sched}, SkipDel:{n_skip_del}, SkipTime:{n_skip_time}, Fail:{n_fail}")
	except (aiosqlite.Error,ConnectionError) as e: log.error(f"DB err fetch all rems: {e}",exc_info=True)
	except Exception as e: log.error(f"Err sched_all_rems: {e}",exc_info=True)

async def add_rem_job(jq: JobQueue, uid: int, hid: int, hname: str, rem_time: datetime.time, cb_func: Callable) -> str|None:
	"""Adds/updates reminder job. Returns job name or None."""
	jname=_jname(uid,hid); log.info(f"Add/Upd rem job '{jname}' h:{hid} at {rem_time:%H:%M:%S}")
	_rm_job_by_name(jq,jname) # Remove existing first
	try:
		jdata={"user_id":uid,"habit_id":hid,"habit_name":hname}
		job=jq.run_daily(callback=cb_func,time=rem_time,chat_id=uid,user_id=uid,name=jname,data=jdata)
		if job: log.info(f"Scheduled job '{jname}' (ID:{job.id})"); return jname
		else: log.error(f"Failed sched job '{jname}' (run_daily=None)."); return None
	except ValueError as e: log.error(f"ValueError sched job '{jname}': {e}. Time={rem_time}"); return None
	except Exception as e: log.error(f"Err sched job '{jname}': {e}",exc_info=True); return None

async def rm_rem_job_by_hid(hid: int, jq: JobQueue) -> bool:
	"""Removes job from queue and DB. Returns True if DB entry found/removed."""
	log.info(f"Attempt remove rem job/DB h:{hid}")
	try:
		job_name_db=await remove_reminder_by_habit_id(hid) # Handles DB
		if job_name_db:
			log.info(f"Rem h:{hid} rem DB. Job name:'{job_name_db}'. Attempt queue removal.")
			job_removed_q=_rm_job_by_name(jq,job_name_db)
			if not job_removed_q: log.warning(f"DB rem h:{hid} removed, but no active job '{job_name_db}' in queue.")
			return True
		else: log.warning(f"No rem found DB h:{hid}. No job rem attempted."); return False
	except (aiosqlite.Error,ConnectionError) as e: log.error(f"DB err rem rem h:{hid}: {e}",exc_info=True); return False
	except Exception as e: log.error(f"Err rem rem h:{hid}: {e}",exc_info=True); return False