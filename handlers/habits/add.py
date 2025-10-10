import logging
from telegram import Update
from telegram.ext import Application,CommandHandler,MessageHandler,filters,ConversationHandler,CallbackContext,CallbackQueryHandler
from database import DatabaseService
from utils import localization as lang,constants as c,helpers,keyboards
from handlers.common.membership import require_membership

log=logging.getLogger(__name__)
ASK_N,ASK_D,ASK_C=c.ADD_HABIT_STATES

def _clr(ctx:CallbackContext):
	for k in ('add_n','add_d','add_c'): ctx.user_data.pop(k,None)
	log.debug("Cleared add ctx.")

async def _save_habit(upd: Update, ctx: CallbackContext) -> None:
	"""Helper to save habit data from context and end conversation."""
	m=upd.effective_message or (upd.callback_query and upd.callback_query.message)
	user=upd.effective_user; ud=ctx.user_data
	if not m or not user or ud is None or 'add_n' not in ud:
		if m: await m.reply_text(lang.ERR_HABIT_ADD_FAILED_CONTEXT)
		_clr(ctx); return
	hname=ud['add_n']; desc=ud.get('add_d'); cat=ud.get('add_c')
	try:
		db_service: DatabaseService = ctx.bot_data['db_service']
		hid = await db_service.add_habit(user.id, hname, desc, cat)
		msg=lang.CONFIRM_HABIT_ADDED.format(habit_name=helpers.escape_html(hname)) if hid else lang.ERR_HABIT_ADD_FAILED
		# If called from a button, edit the message. Otherwise, reply.
		if upd.callback_query: await upd.callback_query.edit_message_text(msg)
		else: await m.reply_text(msg)
	except ConnectionError: await m.reply_text(lang.ERR_DATABASE_CONNECTION)
	except Exception as e: log.error(f"Err saving habit '{hname}' u:{user.id}: {e}",exc_info=True); await m.reply_text(lang.ERR_HABIT_ADD_FAILED)
	_clr(ctx)

@require_membership
async def start(upd: Update, ctx: CallbackContext) -> int:
	m=upd.effective_message
	if not m: return ConversationHandler.END
	await m.reply_text(lang.PROMPT_HABIT_NAME); return ASK_N

async def recv_n(upd: Update, ctx: CallbackContext) -> int:
	m=upd.effective_message; ud=ctx.user_data
	if not m or not m.text or ud is None: return ASK_N
	hname=m.text.strip()
	if not hname: await m.reply_text(f"{lang.ERR_INVALID_INPUT}\n{lang.PROMPT_HABIT_NAME}"); return ASK_N
	ud['add_n']=hname; log.debug(f"Recv name: '{hname}'")
	await m.reply_text(lang.PROMPT_HABIT_DESCRIPTION.format(habit_name=helpers.escape_html(hname)), reply_markup=keyboards.get_skip_keyboard(c.CALLBACK_SKIP_DESCRIPTION))
	return ASK_D

async def skip_d(upd: Update, ctx: CallbackContext) -> int:
	q=upd.callback_query; ud=ctx.user_data
	if not q or ud is None or 'add_n' not in ud: return ConversationHandler.END
	await q.answer()
	ud['add_d'] = None
	hname=ud.get('add_n',lang.DEFAULT_HABIT_NAME)
	log.debug("User skipped description.")
	await q.edit_message_text(lang.PROMPT_HABIT_CATEGORY.format(habit_name=helpers.escape_html(hname)), reply_markup=keyboards.get_skip_keyboard(c.CALLBACK_SKIP_CATEGORY))
	return ASK_C

async def recv_d(upd: Update, ctx: CallbackContext) -> int:
	m=upd.effective_message; ud=ctx.user_data
	if not m or not m.text or ud is None or 'add_n' not in ud:
		if m: await m.reply_text(lang.ERR_HABIT_ADD_FAILED_CONTEXT)
		_clr(ctx); return ConversationHandler.END
	desc_raw=m.text.strip()
	ud['add_d']=desc_raw
	hname=ud.get('add_n',lang.DEFAULT_HABIT_NAME)
	log.debug(f"Recv desc: {desc_raw[:40]+'...'}")
	await m.reply_text(lang.PROMPT_HABIT_CATEGORY.format(habit_name=helpers.escape_html(hname)), reply_markup=keyboards.get_skip_keyboard(c.CALLBACK_SKIP_CATEGORY))
	return ASK_C

async def skip_c(upd: Update, ctx: CallbackContext) -> int:
	q=upd.callback_query; ud=ctx.user_data
	if not q or ud is None: return ConversationHandler.END
	await q.answer()
	ud['add_c'] = None
	log.debug("User skipped category.")
	await _save_habit(upd, ctx)
	return ConversationHandler.END

async def recv_c(upd: Update, ctx: CallbackContext) -> int:
	m=upd.effective_message; ud=ctx.user_data
	if not m or not m.text or ud is None or 'add_n' not in ud:
		if m: await m.reply_text(lang.ERR_HABIT_ADD_FAILED_CONTEXT)
		_clr(ctx); return ConversationHandler.END
	cat_raw=m.text.strip()
	ud['add_c']=cat_raw
	log.debug(f"Recv cat: {cat_raw}")
	await _save_habit(upd, ctx)
	return ConversationHandler.END

async def cancel(upd: Update, ctx: CallbackContext) -> int:
	return await helpers.cancel_conv(upd,ctx,clear_ctx_func=_clr,log_msg="Add habit conv cancelled.")

def get_handler()->ConversationHandler:
	text_f=filters.TEXT & ~filters.COMMAND
	return ConversationHandler(
		entry_points=[
			CommandHandler(c.CMD_ADD_HABIT,start),
			MessageHandler(filters.TEXT & filters.Regex(f"^{lang.BUTTON_MENU_ADD_HABIT}$"), start)
		],
		states={
			ASK_N:[MessageHandler(text_f,recv_n)],
			ASK_D:[
				CallbackQueryHandler(skip_d, pattern=f"^{c.CALLBACK_SKIP_DESCRIPTION}$"),
				MessageHandler(text_f,recv_d)
			],
			ASK_C:[
				CallbackQueryHandler(skip_c, pattern=f"^{c.CALLBACK_SKIP_CATEGORY}$"),
				MessageHandler(text_f,recv_c)
			],
		},
		fallbacks=[CommandHandler(c.CMD_CANCEL,cancel)],
		persistent=False,name="add_habit_conv"
	)

def register_add_habit_handlers(app: Application):
	app.add_handler(get_handler())
	log.info("Registered add_habit conv handler.")