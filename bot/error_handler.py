import logging,html,json,traceback,config
from telegram import Update
from telegram.ext import CallbackContext
from telegram.constants import ParseMode
from telegram.error import TelegramError
from utils import localization as lang

log=logging.getLogger(__name__)
class ErrorHandlerError(Exception): pass # Specific exception

async def handle_error(upd: object, ctx: CallbackContext) -> None:
	"""Central error handler: logs, notifies dev, sends user message."""
	if isinstance(ctx.error,ErrorHandlerError): log.critical("Recursive err in handler!"); return
	log.error("Exception during update:",exc_info=ctx.error)
	tb_list=traceback.format_exception(None,ctx.error,ctx.error.__traceback__)
	tb_s="".join(tb_list)
	upd_s=upd.to_dict() if isinstance(upd,Update) else str(upd)
	ctx_s=f"Chat:{str(ctx.chat_data)[:200]} User:{str(ctx.user_data)[:200]}" # Shorter context log
	e_err=html.escape(str(ctx.error))
	e_upd=html.escape(json.dumps(upd_s,indent=1,ensure_ascii=False)[:600]) # Shorter update log
	e_ctx=html.escape(ctx_s)
	e_tb=html.escape(tb_s[-1200:]) # Shorter traceback
	dev_msg=(f"⚠️ <b>Exc</b> ⚠️\n<b>Err:</b><pre>{e_err}</pre>\n<b>Upd:</b><pre>{e_upd}</pre>\n"
			   f"<b>Ctx:</b><pre>{e_ctx}</pre>\n<b>TB:</b><pre>{e_tb}</pre>")
	if config.DEVELOPER_CHAT_ID:
		try: await ctx.bot.send_message(chat_id=config.DEVELOPER_CHAT_ID,text=dev_msg[:4096],parse_mode=ParseMode.HTML); log.debug(f"Err notify sent dev {config.DEVELOPER_CHAT_ID}.")
		except TelegramError as e: log.error(f"Failed send err dev {config.DEVELOPER_CHAT_ID}: {e}. Orig err: {ctx.error}",exc_info=True)
		except Exception as e: log.error(f"Unexpected err sending notify: {e}. Orig err: {ctx.error}",exc_info=True)
	if isinstance(upd,Update) and upd.effective_message:
		try: await upd.effective_message.reply_text(lang.MSG_ERROR_GENERAL)
		except Exception as e: log.error(f"Failed send user err msg: {e}",exc_info=True)