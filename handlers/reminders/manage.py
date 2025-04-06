import logging
from telegram import Update,InlineKeyboardMarkup
from telegram.ext import Application,CommandHandler,MessageHandler,filters,ConversationHandler,CallbackContext,CallbackQueryHandler,JobQueue
from typing import cast,List,Tuple
from database import get_user_habits,get_habit_name_by_id,add_or_update_reminder_db,get_user_reminders
from scheduling.reminder_scheduler import add_rem_job,rm_rem_job_by_hid
from utils import localization as lang,constants as c,keyboards,helpers
from handlers.common.membership import require_membership
from .jobs import rem_cb

log=logging.getLogger(__name__)
SEL_H,ASK_T=c.SET_REMINDER_STATES

def _clr(ctx:CallbackContext): ctx.user_data.pop('rem_hid',None); ctx.user_data.pop('rem_hname',None); log.debug("Cleared set_rem ctx.")

@require_membership
async def ask_h(upd: Update,ctx:CallbackContext)->int:
	user=upd.effective_user; m=upd.effective_message
	if not user or not m: return ConversationHandler.END
	try:
		habits=await get_user_habits(user.id)
		if not habits: await m.reply_text(lang.MSG_NO_HABITS_FOR_REMINDER); return ConversationHandler.END
		kbd=keyboards.select_habit_keyboard(habits,c.CALLBACK_SELECT_REMINDER_HABIT)
		await m.reply_text(lang.PROMPT_SELECT_REMINDER_HABIT_LIST,reply_markup=InlineKeyboardMarkup(kbd))
		return SEL_H
	except ConnectionError: await m.reply_text(lang.ERR_DATABASE_CONNECTION); return ConversationHandler.END
	except Exception as e: log.error(f"Err fetch habits rem (u:{user.id}): {e}",exc_info=True); await m.reply_text(lang.MSG_ERROR_GENERAL); return ConversationHandler.END

async def sel_h_cb(upd: Update,ctx:CallbackContext)->int:
	q=upd.callback_query; ud=ctx.user_data
	if not q or not q.data or not q.message or ud is None: return ConversationHandler.END
	await q.answer()
	try:
		if not q.data.startswith(c.CALLBACK_SELECT_REMINDER_HABIT): raise ValueError("Invalid rem cb")
		hid=int(q.data.split('_',1)[1])
		hname=await get_habit_name_by_id(hid)
		if not hname: await q.edit_message_text(lang.ERR_HABIT_NOT_FOUND_GENERIC); _clr(ctx); return ConversationHandler.END
		ud['rem_hid']=hid; ud['rem_hname']=hname
		log.debug(f"U {q.from_user.id} sel h '{hname}'({hid}) rem.")
		await q.edit_message_text(lang.PROMPT_REMINDER_TIME.format(habit_name=helpers.escape_html(hname)))
		return ASK_T
	except (IndexError,ValueError) as e: log.error(f"Err parse hid rem cb '{q.data}': {e}"); await q.edit_message_text(lang.ERR_GENERIC_CALLBACK); _clr(ctx); return ConversationHandler.END
	except ConnectionError: await q.edit_message_text(lang.ERR_DATABASE_CONNECTION); _clr(ctx); return ConversationHandler.END
	except Exception as e: log.error(f"Err proc rem habit sel: {e}",exc_info=True); await q.edit_message_text(lang.MSG_ERROR_GENERAL); _clr(ctx); return ConversationHandler.END

async def set_t_cb(upd: Update,ctx:CallbackContext)->int:
	m=upd.effective_message; user=upd.effective_user; ud=ctx.user_data; jq=cast(JobQueue,ctx.job_queue)
	if not m or not m.text or not user or ud is None or not jq: log.error("set_t_cb miss state."); _clr(ctx); await m.reply_text(lang.MSG_ERROR_GENERAL) if m else None; return ConversationHandler.END
	hid=ud.get('rem_hid'); hname=ud.get('rem_hname')
	if not hid or not hname: log.warning("Ctx miss data(hid/name) set_t_cb."); await m.reply_text(lang.ERR_REMINDER_SET_FAILED_CONTEXT); _clr(ctx); return ConversationHandler.END
	t_str=m.text.strip(); ptime=helpers.parse_reminder_time(t_str)
	if not ptime: await m.reply_text(f"{lang.ERR_REMINDER_INVALID_TIME.format(example=helpers.EXAMPLE_TIME_FORMAT)}\n\n{lang.PROMPT_REMINDER_TIME.format(habit_name=helpers.escape_html(hname))}"); return ASK_T
	log.info(f"U {user.id} set rem {ptime:%H:%M} h:{hid} ('{hname}')")
	job_ok,db_ok,new_jname=False,False,""
	try:
		new_jname=await add_rem_job(jq=jq,uid=user.id,hid=hid,hname=hname,rem_time=ptime,cb_func=rem_cb)
		if not new_jname: await m.reply_text(lang.ERR_REMINDER_SET_FAILED_SCHEDULE); raise RuntimeError("Failed schedule job")
		job_ok=True; log.info(f"Sched/upd job: {new_jname}")
		db_ok=await add_or_update_reminder_db(user.id,hid,ptime,new_jname)
		if not db_ok: log.error(f"Failed save rem job {new_jname} DB. Rolling back."); await rm_rem_job_by_hid(hid,jq); await m.reply_text(lang.ERR_REMINDER_SET_FAILED_DB); raise RuntimeError("Failed save DB")
		fmt_t=helpers.format_time_user_friendly(ptime)
		await m.reply_text(lang.CONFIRM_REMINDER_SET.format(habit_name=helpers.escape_html(hname),time_str=fmt_t))
	except ConnectionError:
		await m.reply_text(lang.ERR_DATABASE_CONNECTION)
		if job_ok and not db_ok and new_jname: log.warning(f"DB err post-sched job {new_jname}. Remove."); await rm_rem_job_by_hid(hid,jq)
	except Exception as e:
		log.error(f"Err setting rem h:{hid} u:{user.id}: {e}",exc_info=True)
		if not db_ok: await m.reply_text(lang.ERR_REMINDER_SET_FAILED) # General error if DB didn't fail first
		if job_ok and not db_ok and new_jname: log.warning(f"Err post-sched job {new_jname}. Remove."); await rm_rem_job_by_hid(hid,jq)
	_clr(ctx); return ConversationHandler.END

async def cancel(upd: Update, ctx: CallbackContext) -> int:
	return await helpers.cancel_conv(upd,ctx,clear_ctx_func=_clr,log_msg="Set reminder conv cancelled.")

def get_set_handler()->ConversationHandler:
	return ConversationHandler(
		entry_points=[CommandHandler(c.CMD_SET_REMINDER,ask_h)],
		states={
			SEL_H:[CallbackQueryHandler(sel_h_cb,pattern=f"^{c.CALLBACK_SELECT_REMINDER_HABIT}")],
			ASK_T:[MessageHandler(filters.TEXT & ~filters.COMMAND,set_t_cb)],
		},
		fallbacks=[CommandHandler(c.CMD_CANCEL,cancel)], persistent=False,name="set_reminder_conv"
	)

@require_membership
async def list_cmd(upd: Update, ctx: CallbackContext) -> None:
	user=upd.effective_user; m=upd.effective_message;
	if not user or not m: return
	log.info(f"U {user.id} req /manage_reminders")
	try:
		u_rems=await get_user_reminders(user.id)
		if not u_rems: await m.reply_text(lang.MSG_NO_REMINDERS); return
		kbd_data:List[Tuple[int,str,str]]=[]
		for hid,rem_t,_jname in u_rems:
			hname=await get_habit_name_by_id(hid)
			if hname: kbd_data.append((hid,hname,helpers.format_time_user_friendly(rem_t)))
			else: log.warning(f"Rem for deleted h:{hid} (u:{user.id}). Skip.")
		if not kbd_data: await m.reply_text(lang.MSG_NO_REMINDERS); return # Check again if all were deleted
		await m.reply_text(lang.PROMPT_MANAGE_REMINDERS,reply_markup=keyboards.reminder_management_keyboard(kbd_data))
	except ConnectionError: await m.reply_text(lang.ERR_DATABASE_CONNECTION)
	except Exception as e: log.error(f"Err list rem u:{user.id}: {e}",exc_info=True); await m.reply_text(lang.MSG_ERROR_GENERAL)

async def del_rem_cb(upd: Update, ctx: CallbackContext) -> None:
	q=upd.callback_query; user=upd.effective_user; jq=cast(JobQueue,ctx.job_queue)
	if not q or not q.message or not q.data or not user or not jq: return
	await q.answer()
	hid = -1
	try:
		if not q.data.startswith(c.CALLBACK_DELETE_REMINDER): raise ValueError("Invalid del rem cb")
		hid=int(q.data.split('_',1)[1])
		log.info(f"U {user.id} req del rem h:{hid}")
		hname=await get_habit_name_by_id(hid) or lang.DEFAULT_HABIT_NAME
		removed=await rm_rem_job_by_hid(hid,jq)
		msg_key=lang.CONFIRM_REMINDER_DELETED if removed else lang.ERR_REMINDER_DELETE_FAILED
		await q.edit_message_text(msg_key.format(habit_name=helpers.escape_html(hname)))
	except (IndexError,ValueError) as e: log.error(f"Err parse hid del rem cb '{q.data}': {e}"); await q.edit_message_text(lang.ERR_GENERIC_CALLBACK)
	except ConnectionError: await q.edit_message_text(lang.ERR_DATABASE_CONNECTION)
	except Exception as e: log.error(f"Err del rem btn (h:{hid}): {e}",exc_info=True); await q.edit_message_text(lang.ERR_REMINDER_DELETE_FAILED_INTERNAL)

def register_reminder_management_handlers(app: Application):
	app.add_handler(get_set_handler())
	app.add_handler(CommandHandler(c.CMD_MANAGE_REMINDERS,list_cmd))
	app.add_handler(CallbackQueryHandler(del_rem_cb,pattern=f"^{c.CALLBACK_DELETE_REMINDER}"))
	log.info("Registered rem management handlers.")