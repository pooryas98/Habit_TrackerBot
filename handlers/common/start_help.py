import logging
from telegram import Update
from telegram.ext import Application,CommandHandler,CallbackContext
from database import DatabaseService
from utils import localization as lang,constants as c
from .membership import require_membership

log=logging.getLogger(__name__)

@require_membership
async def start_cmd(upd: Update, ctx: CallbackContext) -> None:
	usr=upd.effective_user; msg=upd.effective_message;
	if not usr or not msg: log.warning("/start no user/msg."); return
	try:
		# Get the database service from context
		db_service: DatabaseService = ctx.bot_data['db_service']
		# Use the new service method
		await db_service.add_user_if_not_exists(usr.id)
		log.info(f"User {usr.id} ({usr.username or 'NoUN'}) started.")
		await msg.reply_text(lang.MSG_WELCOME.format(user_name=usr.first_name))
		await help_cmd(upd,ctx) # Call help after welcome
	except ConnectionError: await msg.reply_text(lang.ERR_DATABASE_CONNECTION)
	except Exception as e: log.error(f"Err /start u:{usr.id}: {e}",exc_info=True)

@require_membership
async def help_cmd(upd: Update, ctx: CallbackContext) -> None:
	msg=upd.effective_message;
	if not msg: log.warning("/help no msg."); return
	try: await msg.reply_text(lang.MSG_HELP,disable_web_page_preview=True)
	except Exception as e: log.error(f"Err sending help: {e}",exc_info=True)

def register_start_help_handlers(app: Application):
	app.add_handler(CommandHandler(c.CMD_START,start_cmd))
	app.add_handler(CommandHandler(c.CMD_HELP,help_cmd))
	log.info("Registered /start & /help handlers.")