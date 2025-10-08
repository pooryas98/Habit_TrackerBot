import logging
from telegram import Update,InlineKeyboardMarkup
from telegram.ext import Application,CommandHandler,ConversationHandler,CallbackContext,CallbackQueryHandler,JobQueue
from typing import cast
from database import DatabaseService
from scheduling.reminder_scheduler import rm_rem_job_by_hid
from utils import localization as lang,constants as c,keyboards,helpers
from handlers.common.membership import require_membership

log=logging.getLogger(__name__)
ASK_H,CONFIRM=c.DELETE_HABIT_STATES

def _clr(ctx:CallbackContext): ctx.user_data.pop('del_hid',None); ctx.user_data.pop('del_hname',None); log.debug("Cleared del ctx.")

async def _err(target, msg: str):
	try:
		if hasattr(target,'answer'): await target.answer(msg,show_alert=True)
		if hasattr(target,'edit_message_text'): await target.edit_message_text(msg)
		elif hasattr(target,'reply_text'): await target.reply_text(msg)
	except Exception as e: log.error(f"Failed send err msg del: {e}")

@require_membership
async def start(upd: Update, ctx: CallbackContext) -> int:
	user=upd.effective_user; m=upd.effective_message
	if not user or not m: return ConversationHandler.END
	try:
		# Get the database service from context
		db_service: DatabaseService = ctx.bot_data['db_service']
		# Use the new service method
		habits = await db_service.get_user_habits(user.id)
		if not habits: await m.reply_text(lang.MSG_NO_HABITS_TO_DELETE); return ConversationHandler.END
		kbd=keyboards.select_habit_keyboard(habits,c.CALLBACK_SELECT_HABIT_DELETE)
		await m.reply_text(lang.PROMPT_SELECT_HABIT_TO_DELETE,reply_markup=InlineKeyboardMarkup(kbd))
		return ASK_H
	except ConnectionError: await m.reply_text(lang.ERR_DATABASE_CONNECTION); return ConversationHandler.END
	except Exception as e: log.error(f"Err fetch habits del (u:{user.id}): {e}",exc_info=True); await m.reply_text(lang.MSG_ERROR_GENERAL); return ConversationHandler.END

async def ask_confirm_cb(upd: Update, ctx: CallbackContext) -> int:
	q=upd.callback_query; ud=ctx.user_data
	if not q or not q.data or not q.message or ud is None: return ConversationHandler.END
	await q.answer()
	try:
		# Get the database service from context
		db_service: DatabaseService = ctx.bot_data['db_service']
		# Use the new service method
		if not q.data.startswith(c.CALLBACK_SELECT_HABIT_DELETE): raise ValueError("Invalid del cb")
		hid=int(q.data.split('_',1)[1])
		hname = await db_service.get_habit_name_by_id(hid)
		if not hname: await q.edit_message_text(lang.ERR_HABIT_NOT_FOUND_GENERIC); _clr(ctx); return ConversationHandler.END
		ud['del_hid']=hid; ud['del_hname']=hname
		log.debug(f"U {q.from_user.id} sel h '{hname}' ({hid}) for del.")
		yes_cb=f"{c.CALLBACK_CONFIRM_DELETE_HABIT}{hid}"; no_cb=c.CALLBACK_CANCEL_DELETE
		await q.edit_message_text(lang.PROMPT_CONFIRM_DELETE.format(habit_name=helpers.escape_html(hname)),reply_markup=keyboards.yes_no_keyboard(yes_cb,no_cb))
		return CONFIRM
	except (IndexError,ValueError) as e: log.error(f"Err parse hid del cb '{q.data}': {e}"); await _err(q,lang.ERR_GENERIC_CALLBACK); _clr(ctx); return ConversationHandler.END
	except ConnectionError: await _err(q,lang.ERR_DATABASE_CONNECTION); _clr(ctx); return ConversationHandler.END
	except Exception as e: log.error(f"Err prep del confirm: {e}",exc_info=True); await _err(q,lang.MSG_ERROR_GENERAL); _clr(ctx); return ConversationHandler.END

async def perform_del_cb(upd: Update, ctx: CallbackContext) -> int:
	q=upd.callback_query; user=upd.effective_user; ud=ctx.user_data; jq=cast(JobQueue,ctx.job_queue)
	if not q or not q.data or not user or ud is None or not jq: log.error("perform_del_cb miss state."); return ConversationHandler.END
	await q.answer()
	hid_ctx=ud.get('del_hid'); hname_ctx=ud.get('del_hname',lang.DEFAULT_HABIT_NAME)
	hid = -1
	try:
		if not q.data.startswith(c.CALLBACK_CONFIRM_DELETE_HABIT): raise ValueError("Invalid cb confirm del.")
		hid_cb=int(q.data[len(c.CALLBACK_CONFIRM_DELETE_HABIT):])
		if hid_ctx is None or hid_cb != hid_ctx: log.error(f"HID mismatch del! Ctx:{hid_ctx}, CB:{hid_cb}"); await _err(q,lang.ERR_DELETE_FAILED_CONTEXT); _clr(ctx); return ConversationHandler.END
		hid=hid_ctx
		log.info(f"U {user.id} confirm del h:{hid} ('{hname_ctx}')")
		job_rem=await rm_rem_job_by_hid(hid,jq)
		log.info(f"Rem assoc rem job h:{hid}.") if job_rem else log.debug(f"No active rem job/fail rem h:{hid}.")
		# Get the database service from context
		db_service: DatabaseService = ctx.bot_data['db_service']
		# Use the new service method
		db_del = await db_service.delete_habit_and_log(hid, user.id)
		msg_key=lang.CONFIRM_HABIT_DELETED if db_del else lang.ERR_DELETE_FAILED_DB
		await q.edit_message_text(msg_key.format(habit_name=helpers.escape_html(hname_ctx)))
	except (IndexError,ValueError) as e: log.error(f"Err parse hid confirm del cb '{q.data}': {e}"); await _err(q,lang.ERR_GENERIC_CALLBACK)
	except ConnectionError: await _err(q,lang.ERR_DATABASE_CONNECTION)
	except Exception as e: log.error(f"Err during habit del h:{hid}: {e}",exc_info=True); await _err(q,lang.ERR_DELETE_FAILED_INTERNAL)
	_clr(ctx); return ConversationHandler.END

async def cancel(upd: Update, ctx: CallbackContext) -> int:
	return await helpers.cancel_conv(upd,ctx,clear_ctx_func=_clr,log_msg="Delete habit conv cancelled.")

def get_handler()->ConversationHandler:
	return ConversationHandler(
		entry_points=[CommandHandler(c.CMD_DELETE_HABIT,start)],
		states={
			ASK_H:[CallbackQueryHandler(ask_confirm_cb,pattern=f"^{c.CALLBACK_SELECT_HABIT_DELETE}")],
			CONFIRM:[
				CallbackQueryHandler(perform_del_cb,pattern=f"^{c.CALLBACK_CONFIRM_DELETE_HABIT}"),
				CallbackQueryHandler(cancel,pattern=f"^{c.CALLBACK_CANCEL_DELETE}$")]},
		fallbacks=[
			CommandHandler(c.CMD_CANCEL,cancel),
			CallbackQueryHandler(cancel,pattern=f"^{c.CALLBACK_CANCEL_DELETE}$")], # Also handle cancel button
		persistent=False,name="delete_habit_conv"
	)

def register_delete_habit_handlers(app: Application):
	app.add_handler(get_handler())
	log.info("Registered delete_habit conv handler.")