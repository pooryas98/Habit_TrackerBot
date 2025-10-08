import logging,aiosqlite
from telegram.ext import CallbackContext,JobQueue
from telegram.error import Forbidden,BadRequest
from typing import cast,Optional
from database import DatabaseService
from scheduling.reminder_scheduler import rm_rem_job_by_hid
from utils import localization as lang

log=logging.getLogger(__name__)

async def rem_cb(ctx: CallbackContext):
	"""JobQueue func sends reminder msg."""
	job=ctx.job; jq=cast(Optional[JobQueue],ctx.job_queue)
	if not job or not isinstance(job.data,dict) or not jq: log.error(f"Rem job cb invalid job/data/jq: {job}"); return
	uid=job.data.get("user_id"); hid=job.data.get("habit_id"); hname=job.data.get("habit_name")
	if not uid or not hid:
		log.error(f"Rem job {job.name} missing uid/hid: {job.data}. Removing."); await rm_rem_job_by_hid(hid,jq) if hid else None; return
	if not hname:
		try:
			# Get the database service from context
			db_service: DatabaseService = ctx.bot_data['db_service']
			# Use the new service method
			hname = await db_service.get_habit_name_by_id(hid)
			if not hname: log.warning(f"Habit {hid} not found job {job.name}. Removing."); await rm_rem_job_by_hid(hid,jq); return
		except (aiosqlite.Error,ConnectionError): log.error(f"DB Err fetch hname job {job.name}. Using default."); hname=lang.DEFAULT_HABIT_NAME
		except Exception as e: log.error(f"Err fetch hname job {job.name}: {e}",exc_info=True); hname=lang.DEFAULT_HABIT_NAME
	log.info(f"Exec rem job '{job.name}' u:{uid}, h:{hid} ('{hname}')")
	rem_text=lang.MSG_REMINDER_ALERT.format(habit_name=hname)
	try: await ctx.bot.send_message(chat_id=uid,text=rem_text); log.info(f"Rem sent ok job '{job.name}'.")
	except Forbidden: log.warning(f"Bot blocked user {uid}. Removing job '{job.name}'."); await rm_rem_job_by_hid(hid,jq)
	except BadRequest as e: log.warning(f"BadReq sending rem job '{job.name}' user {uid}: {e}. Removing job."); await rm_rem_job_by_hid(hid,jq)
	except Exception as e: log.error(f"Err sending rem job '{job.name}' user {uid}: {e}",exc_info=True)