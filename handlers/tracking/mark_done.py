import logging
from telegram import Update,InlineKeyboardMarkup,error as tg_error
from telegram.ext import Application,CommandHandler,CallbackContext,CallbackQueryHandler
from typing import Tuple,Optional
from database import DatabaseService
from utils import localization as lang,constants as c,keyboards,helpers
from handlers.common.membership import require_membership
from .view import _today_msg # Assumes _today_msg generates the dict for reply_text

log=logging.getLogger(__name__)

async def _mark(ctx: CallbackContext, uid: int, hid: int) -> Tuple[str, Optional[str]]:
	"""Core: mark habit done. Returns status & name."""
	try:
		# Get the database service from context
		db_service: DatabaseService = ctx.bot_data['db_service']
		# Use the new service method
		stat = await db_service.mark_habit_done(uid, hid, helpers.get_today_date())
		hname=None
		if stat!="error":
			hname = await db_service.get_habit_name_by_id(hid)
			if hname is None and stat!="already_done": log.warning(f"_mark: h:{hid} done but name miss u:{uid}."); return "not_found",None
		return stat,hname
	except ConnectionError: return "error",None
	except Exception as e: log.error(f"Err _mark h:{hid} u:{uid}: {e}",exc_info=True); return "error",None

@require_membership
async def done_cmd(upd: Update, ctx: CallbackContext) -> None:
	u=upd.effective_user; m=upd.effective_message;
	if not u or not m: return
	if ctx.args:
		q_name=" ".join(ctx.args).strip()
		if not q_name: await m.reply_text(f"{lang.PROMPT_MARK_DONE_SELECT}\\n{lang.EXAMPLE_MARK_DONE}"); return
		log.debug(f"U {u.id} mark done by name: '{q_name}'")
		try:
			# Get the database service from context
			db_service: DatabaseService = ctx.bot_data['db_service']
			# Use the new service method
			info = await db_service.find_habit_by_name(u.id, q_name)
			if not info: await m.reply_text(lang.ERR_HABIT_NOT_FOUND.format(habit_name=helpers.escape_html(q_name))); return
			hid,db_name=info; res,act_name=await _mark(ctx, u.id,hid)
			dname=helpers.escape_html(act_name or db_name)
			msgs={"success":lang.CONFIRM_HABIT_MARKED_DONE,"already_done":lang.ERR_HABIT_ALREADY_DONE,"not_found":lang.ERR_HABIT_NOT_FOUND_GENERIC,"error":lang.ERR_MARK_DONE_FAILED}
			await m.reply_text(msgs[res].format(habit_name=dname))
		except ConnectionError: await m.reply_text(lang.ERR_DATABASE_CONNECTION)
		except Exception as e: log.error(f"Error /done {q_name} u:{u.id}: {e}",exc_info=True); await m.reply_text(lang.ERR_MARK_DONE_FAILED)
	else: # No args, show keyboard
		log.debug(f"U {u.id} /done (no args), show kbd.")
		try:
			# Get the database service from context
			db_service: DatabaseService = ctx.bot_data['db_service']
			# Use the new service method
			habits = await db_service.get_user_habits(u.id)
			if not habits: await m.reply_text(lang.MSG_NO_HABITS_TO_MARK_DONE); return
			kbd=keyboards.select_habit_keyboard(habits,c.CALLBACK_SELECT_HABIT_DONE)
			await m.reply_text(lang.PROMPT_MARK_DONE_SELECT,reply_markup=InlineKeyboardMarkup(kbd))
		except ConnectionError: await m.reply_text(lang.ERR_DATABASE_CONNECTION)
		except Exception as e: log.error(f"Err fetch habits /done kbd u:{u.id}: {e}",exc_info=True); await m.reply_text(lang.MSG_ERROR_GENERAL)

@require_membership
async def done_btn(upd: Update, ctx: CallbackContext) -> None:
	"""Handles 'Mark Done' btn from /today."""
	q=upd.callback_query; u=upd.effective_user;
	if not q or not q.message or not q.data or not u: return
	await q.answer()
	try:
		if not q.data.startswith(c.CALLBACK_MARK_DONE): raise ValueError("Invalid done cb")
		hid=int(q.data.split('_',1)[1])
		log.debug(f"U {u.id} press mark done btn h:{hid}")
		res,hname=await _mark(ctx, u.id,hid)
		safe_name=helpers.escape_html(hname or lang.DEFAULT_HABIT_NAME)
		chat_id, msg_id = q.message.chat.id, q.message.message_id
		if res=="success":
			log.info(f"U {u.id} marked h:{hid} ('{hname}') done btn.")
			await _refresh_today(ctx,chat_id,msg_id,u.id)
			await q.answer(text=lang.CONFIRM_HABIT_MARKED_DONE_SHORT.format(habit_name=safe_name))
		elif res=="already_done": await q.answer(text=lang.ERR_HABIT_ALREADY_DONE.format(habit_name=safe_name),show_alert=False)
		elif res=="not_found":
			await q.answer(text=lang.ERR_MARK_DONE_FAILED_NOT_FOUND,show_alert=True)
			await _refresh_today(ctx,chat_id,msg_id,u.id) # Refresh even if not found (habit deleted)
		else: await q.answer(text=lang.ERR_MARK_DONE_FAILED,show_alert=True)
	except (IndexError,ValueError) as e: log.error(f"Err parse hid done_btn cb '{q.data}': {e}"); await q.answer(lang.ERR_MARK_DONE_FAILED_ID,show_alert=True)
	except Exception as e: log.error(f"Err done_btn u:{u.id}: {e}",exc_info=True); await q.answer(lang.ERR_MARK_DONE_FAILED,show_alert=True)

@require_membership
async def done_sel(upd: Update, ctx: CallbackContext) -> None:
	"""Handles habit selection from /done kbd."""
	q=upd.callback_query; u=upd.effective_user;
	if not q or not q.message or not q.data or not u: return
	await q.answer()
	try:
		if not q.data.startswith(c.CALLBACK_SELECT_HABIT_DONE): raise ValueError("Invalid done_sel cb")
		hid=int(q.data.split('_',1)[1])
		log.debug(f"U {u.id} sel h:{hid} from /done kbd.")
		res,hname=await _mark(ctx, u.id,hid)
		safe_name=helpers.escape_html(hname or lang.DEFAULT_HABIT_NAME)
		msgs={"success":lang.CONFIRM_HABIT_MARKED_DONE,"already_done":lang.ERR_HABIT_ALREADY_DONE,"not_found":lang.ERR_HABIT_NOT_FOUND_GENERIC,"error":lang.ERR_MARK_DONE_FAILED}
		final_msg=msgs[res].format(habit_name=safe_name)
		await q.edit_message_text(text=final_msg,reply_markup=None)
	except (IndexError,ValueError) as e: log.error(f"Err parse hid done_sel cb '{q.data}': {e}"); await q.edit_message_text(lang.ERR_GENERIC_CALLBACK)
	except ConnectionError: await q.edit_message_text(lang.ERR_DATABASE_CONNECTION)
	except Exception as e: log.error(f"Err done_sel u:{u.id}: {e}",exc_info=True); await q.edit_message_text(lang.ERR_MARK_DONE_FAILED)

async def _refresh_today(ctx: CallbackContext, chat_id: int, msg_id: int, uid: int):
	"""Helper: refresh /today msg."""
	log.debug(f"Refresh /today msg (C:{chat_id}, M:{msg_id}) u:{uid}")
	try:
		content=await _today_msg(ctx, uid)
		await ctx.bot.edit_message_text(chat_id=chat_id,message_id=msg_id,**content)
		log.debug(f"Edited /today msg {msg_id}.")
	except ConnectionError: log.error(f"DB err _refresh_today u:{uid}.")
	except tg_error.BadRequest as e:
		if "Message is not modified" in str(e): log.debug(f"Msg {msg_id} not modified.")
		else: log.error(f"BadReq err refresh /today {msg_id}: {e}",exc_info=True)
	except Exception as e: log.error(f"Err _refresh_today msg {msg_id}: {e}",exc_info=True)

def register_mark_done_handlers(app: Application):
	app.add_handler(CommandHandler(c.CMD_DONE, done_cmd))
	app.add_handler(CallbackQueryHandler(done_btn, pattern=f"^{c.CALLBACK_MARK_DONE}"))
	app.add_handler(CallbackQueryHandler(done_sel, pattern=f"^{c.CALLBACK_SELECT_HABIT_DONE}"))
	log.info("Registered mark_done handlers.")