import logging
from typing import Optional
from telegram import Update,InlineKeyboardMarkup
from telegram.ext import Application,CommandHandler,MessageHandler,filters,ConversationHandler,CallbackContext,CallbackQueryHandler
from database import DatabaseService
from utils import localization as lang,constants as c,keyboards,helpers
from handlers.common.membership import require_membership

log=logging.getLogger(__name__)
SEL_H,SEL_F,ASK_V,CONFIRM=c.EDIT_HABIT_STATES

def _clr(ctx:CallbackContext):
	for k in ('edit_hid','edit_hname','edit_fld'): ctx.user_data.pop(k,None)
	log.debug("Cleared edit ctx.")

async def _err(target, msg: str):
	try:
		if hasattr(target,'answer'): await target.answer(msg,show_alert=True)
		if hasattr(target,'edit_message_text'): await target.edit_message_text(msg)
		elif hasattr(target,'reply_text'): await target.reply_text(msg)
	except Exception as e: log.error(f"Failed send err msg edit: {e}")

@require_membership
async def start(upd: Update, ctx: CallbackContext) -> int:
	user=upd.effective_user; m=upd.effective_message
	if not user or not m: return ConversationHandler.END
	try:
		# Get the database service from context
		db_service: DatabaseService = ctx.bot_data['db_service']
		# Use the new service method
		habits = await db_service.get_user_habits(user.id)
		if not habits: await m.reply_text(lang.MSG_NO_HABITS_TO_EDIT); return ConversationHandler.END
		kbd=keyboards.select_habit_keyboard(habits,c.CALLBACK_SELECT_HABIT_EDIT)
		await m.reply_text(lang.PROMPT_SELECT_HABIT_TO_EDIT,reply_markup=InlineKeyboardMarkup(kbd))
		return SEL_H
	except ConnectionError: await m.reply_text(lang.ERR_DATABASE_CONNECTION); return ConversationHandler.END
	except Exception as e: log.error(f"Err fetch habits edit (u:{user.id}): {e}",exc_info=True); await m.reply_text(lang.MSG_ERROR_GENERAL); return ConversationHandler.END

async def sel_h_cb(upd: Update, ctx: CallbackContext) -> int:
	q=upd.callback_query; ud=ctx.user_data
	if not q or not q.data or not q.message or ud is None: return ConversationHandler.END
	await q.answer()
	try:
		# Get the database service from context
		db_service: DatabaseService = ctx.bot_data['db_service']
		# Use the new service method
		if not q.data.startswith(c.CALLBACK_SELECT_HABIT_EDIT): raise ValueError(f"Invalid edit cb: {q.data}")
		hid=int(q.data.split('_',1)[1])
		hname = await db_service.get_habit_name_by_id(hid)
		if not hname: await q.edit_message_text(lang.ERR_HABIT_NOT_FOUND_GENERIC); _clr(ctx); return ConversationHandler.END
		ud['edit_hid']=hid; ud['edit_hname']=hname
		log.debug(f"U {q.from_user.id} sel h '{hname}' ({hid}) edit.")
		await q.edit_message_text(lang.PROMPT_SELECT_FIELD_TO_EDIT.format(habit_name=helpers.escape_html(hname)),reply_markup=keyboards.edit_habit_field_keyboard(hid))
		return SEL_F
	except (IndexError,ValueError) as e: log.error(f"Err parse hid cb '{q.data}': {e}"); await _err(q,lang.ERR_GENERIC_CALLBACK); _clr(ctx); return ConversationHandler.END
	except ConnectionError: await _err(q,lang.ERR_DATABASE_CONNECTION); _clr(ctx); return ConversationHandler.END
	except Exception as e: log.error(f"Err sel h edit: {e}",exc_info=True); await _err(q,lang.MSG_ERROR_GENERAL); _clr(ctx); return ConversationHandler.END

async def sel_f_cb(upd: Update, ctx: CallbackContext) -> int:
	q=upd.callback_query; ud=ctx.user_data
	if not q or not q.data or not q.message or ud is None: return ConversationHandler.END
	hid=ud.get('edit_hid'); orig_name=ud.get('edit_hname',lang.DEFAULT_HABIT_NAME)
	if not hid: log.warning("edit_hid miss sel_f_cb."); await _err(q,lang.ERR_EDIT_FAILED_CONTEXT); _clr(ctx); return ConversationHandler.END
	await q.answer()
	try:
		if not q.data.startswith(c.CALLBACK_EDIT_FIELD_PREFIX): raise ValueError(f"Invalid field cb: {q.data}")
		parts=q.data[len(c.CALLBACK_EDIT_FIELD_PREFIX):].split('_',1)
		if len(parts)!=2: raise ValueError("CB fmt incorrect.")
		fld,cb_hid_str=parts; cb_hid=int(cb_hid_str)
		if cb_hid!=hid: log.error(f"HID mismatch! Ctx:{hid}, CB:{cb_hid}"); raise ValueError("HID mismatch.")
		if fld not in ("name","description","category"): log.error(f"Invalid field: '{fld}'"); await _err(q,lang.ERR_EDIT_FAILED_INVALID_FIELD); _clr(ctx); return ConversationHandler.END
		ud['edit_fld']=fld
		log.debug(f"User wants edit '{fld}' h:{hid}")
		prompts={"name":lang.PROMPT_EDIT_NAME,"description":lang.PROMPT_EDIT_DESCRIPTION,"category":lang.PROMPT_EDIT_CATEGORY}
		fmt_args={"habit_name":helpers.escape_html(orig_name)}
		reply_markup = keyboards.get_skip_keyboard(c.CALLBACK_SKIP_EDIT) if fld in ("description", "category") else None
		await q.edit_message_text(prompts[fld].format(**fmt_args), reply_markup=reply_markup)
		return ASK_V
	except (IndexError,ValueError) as e: log.error(f"Err parse field/ID cb '{q.data}': {e}"); await _err(q,lang.ERR_GENERIC_CALLBACK); _clr(ctx); return ConversationHandler.END
	except Exception as e: log.error(f"Err sel f edit: {e}",exc_info=True); await _err(q,lang.MSG_ERROR_GENERAL); _clr(ctx); return ConversationHandler.END

async def skip_v(upd: Update, ctx: CallbackContext) -> int:
	q=upd.callback_query; user=upd.effective_user; ud=ctx.user_data
	if not q or not user or ud is None: return ConversationHandler.END
	await q.answer()
	hid=ud.get('edit_hid'); fld=ud.get('edit_fld'); orig_name=ud.get('edit_hname',lang.DEFAULT_HABIT_NAME)
	if not hid or not fld: log.warning("Ctx miss (hid/fld) skip_v."); await _err(q,lang.ERR_EDIT_FAILED_CONTEXT); _clr(ctx); return ConversationHandler.END

	log.debug(f"Update h:{hid}, fld:'{fld}' val:SKIPPED u:{user.id}")
	try:
		db_service: DatabaseService = ctx.bot_data['db_service']
		success = await db_service.update_habit(hid, user.id, fld, None)
		if success:
			await q.edit_message_text(lang.CONFIRM_HABIT_UPDATED.format(habit_name=helpers.escape_html(orig_name)))
		else: await q.edit_message_text(lang.ERR_EDIT_FAILED_DB)
	except ConnectionError: await _err(q, lang.ERR_DATABASE_CONNECTION)
	except Exception as e: log.error(f"Err update h:{hid} DB on skip: {e}",exc_info=True); await _err(q, lang.ERR_EDIT_FAILED_DB)

	_clr(ctx); return ConversationHandler.END

async def recv_v(upd: Update, ctx: CallbackContext) -> int:
	m=upd.effective_message; user=upd.effective_user; ud=ctx.user_data
	if not m or not m.text or not user or ud is None: return ASK_V
	hid=ud.get('edit_hid'); fld=ud.get('edit_fld'); orig_name=ud.get('edit_hname',lang.DEFAULT_HABIT_NAME)
	if not hid or not fld: log.warning("Ctx miss (hid/fld) recv_v."); await m.reply_text(lang.ERR_EDIT_FAILED_CONTEXT); _clr(ctx); return ConversationHandler.END
	val_raw=m.text.strip(); new_val:Optional[str]=val_raw

	if fld=="name" and not val_raw:
		await m.reply_text(f"{lang.ERR_EDIT_FAILED_NAME_EMPTY}\n{lang.PROMPT_EDIT_NAME.format(habit_name=helpers.escape_html(orig_name))}")
		return ASK_V # Ask again

	log.debug(f"Update h:{hid}, fld:'{fld}' val:'{str(new_val)[:40]}...' u:{user.id}")
	try:
		# Get the database service from context
		db_service: DatabaseService = ctx.bot_data['db_service']
		# Use the new service method
		success = await db_service.update_habit(hid, user.id, fld, new_val)
		if success:
			final_name=new_val if fld=='name' else orig_name
			await m.reply_text(lang.CONFIRM_HABIT_UPDATED.format(habit_name=helpers.escape_html(final_name)))
		else: await m.reply_text(lang.ERR_EDIT_FAILED_DB)
	except ConnectionError: await m.reply_text(lang.ERR_DATABASE_CONNECTION)
	except Exception as e: log.error(f"Err update h:{hid} DB: {e}",exc_info=True); await m.reply_text(lang.ERR_EDIT_FAILED_DB)

	_clr(ctx); return ConversationHandler.END

async def cancel(upd: Update, ctx: CallbackContext) -> int:
	return await helpers.cancel_conv(upd,ctx,clear_ctx_func=_clr,log_msg="Edit habit conv cancelled.")

def get_handler()->ConversationHandler:
	text_f=filters.TEXT & ~filters.COMMAND
	return ConversationHandler(
		entry_points=[CommandHandler(c.CMD_EDIT_HABIT,start)],
		states={
			SEL_H:[CallbackQueryHandler(sel_h_cb,pattern=f"^{c.CALLBACK_SELECT_HABIT_EDIT}")],
			SEL_F:[CallbackQueryHandler(sel_f_cb,pattern=f"^{c.CALLBACK_EDIT_FIELD_PREFIX}")],
			ASK_V:[
				CallbackQueryHandler(skip_v, pattern=f"^{c.CALLBACK_SKIP_EDIT}$"),
				MessageHandler(text_f,recv_v)
			],
		},
		fallbacks=[CommandHandler(c.CMD_CANCEL,cancel)],persistent=False,name="edit_habit_conv"
	)

def register_edit_habit_handlers(app: Application):
	app.add_handler(get_handler())
	log.info("Registered edit_habit conv handler.")