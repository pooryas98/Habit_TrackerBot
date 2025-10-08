import logging
from telegram import Update
from telegram.ext import Application,CommandHandler,MessageHandler,filters,ConversationHandler,CallbackContext
from database import DatabaseService
from utils import localization as lang,constants as c,helpers
from handlers.common.membership import require_membership

log=logging.getLogger(__name__)
ASK_N,ASK_D,ASK_C=c.ADD_HABIT_STATES

def _clr(ctx:CallbackContext):
	for k in ('add_n','add_d','add_c'): ctx.user_data.pop(k,None)
	log.debug("Cleared add ctx.")

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
	await m.reply_text(lang.PROMPT_HABIT_DESCRIPTION.format(habit_name=helpers.escape_html(hname),cmd_skip=lang.CMD_SKIP))
	return ASK_D

async def recv_d(upd: Update, ctx: CallbackContext) -> int:
	m=upd.effective_message; ud=ctx.user_data
	if not m or not m.text or ud is None or 'add_n' not in ud:
		if m: await m.reply_text(lang.ERR_HABIT_ADD_FAILED_CONTEXT)
		_clr(ctx); return ConversationHandler.END
	desc_raw=m.text.strip(); hname=ud.get('add_n',lang.DEFAULT_HABIT_NAME)
	is_skip=desc_raw.lower() in ('/skip',lang.CMD_SKIP.lower())
	ud['add_d']=None if is_skip else desc_raw
	log.debug(f"Recv desc: {'SKIP' if is_skip else desc_raw[:40]+'...'}")
	await m.reply_text(lang.PROMPT_HABIT_CATEGORY.format(habit_name=helpers.escape_html(hname),cmd_skip=lang.CMD_SKIP))
	return ASK_C

async def recv_c(upd: Update, ctx: CallbackContext) -> int:
	m=upd.effective_message; user=upd.effective_user; ud=ctx.user_data
	if not m or not m.text or not user or ud is None or 'add_n' not in ud:
		if m: await m.reply_text(lang.ERR_HABIT_ADD_FAILED_CONTEXT)
		_clr(ctx); return ConversationHandler.END
	cat_raw=m.text.strip(); hname=ud['add_n']; desc=ud.get('add_d')
	is_skip=cat_raw.lower() in ('/skip',lang.CMD_SKIP.lower())
	cat=None if is_skip else cat_raw
	log.debug(f"Recv cat: {'SKIP' if is_skip else cat}")
	try:
		# Get the database service from context
		db_service: DatabaseService = ctx.bot_data['db_service']
		# Use the new service method
		hid = await db_service.add_habit(user.id, hname, desc, cat)
		msg=lang.CONFIRM_HABIT_ADDED.format(habit_name=helpers.escape_html(hname)) if hid else lang.ERR_HABIT_ADD_FAILED
		await m.reply_text(msg)
	except ConnectionError: await m.reply_text(lang.ERR_DATABASE_CONNECTION)
	except Exception as e: log.error(f"Err saving habit '{hname}' u:{user.id}: {e}",exc_info=True); await m.reply_text(lang.ERR_HABIT_ADD_FAILED)
	_clr(ctx); return ConversationHandler.END

async def cancel(upd: Update, ctx: CallbackContext) -> int:
	return await helpers.cancel_conv(upd,ctx,clear_ctx_func=_clr,log_msg="Add habit conv cancelled.")

def get_handler()->ConversationHandler:
	skip_f=filters.Regex(f'(?i)^(/skip|{lang.CMD_SKIP})$'); text_f=filters.TEXT & ~filters.COMMAND
	return ConversationHandler(
		entry_points=[CommandHandler(c.CMD_ADD_HABIT,start)],
		states={
			ASK_N:[MessageHandler(text_f,recv_n)],
			ASK_D:[MessageHandler(text_f|skip_f,recv_d)],
			ASK_C:[MessageHandler(text_f|skip_f,recv_c)],
		},
		fallbacks=[CommandHandler(c.CMD_CANCEL,cancel)],
		persistent=False,name="add_habit_conv"
	)

def register_add_habit_handlers(app: Application):
	app.add_handler(get_handler())
	log.info("Registered add_habit conv handler.")