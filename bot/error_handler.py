import logging,html,json,traceback
from config import settings
from telegram import Update
from telegram.ext import CallbackContext
from telegram.constants import ParseMode
from telegram.error import TelegramError
from utils import localization as lang

log=logging.getLogger(__name__)
class ErrorHandlerError(Exception): pass # Specific exception

async def handle_error(upd: object, ctx: CallbackContext) -> None:
	"""Central error handler: logs, notifies dev, sends user message."""
	err = getattr(ctx, "error", None)

	# Prevent recursive errors
	if isinstance(err, ErrorHandlerError):
		log.critical("Recursive err in handler!")
		return

	# Build safe diagnostic strings
	try:
		log.error("Exception during update:", exc_info=err)
	except Exception:
		log.error("Exception during update (unable to attach exc_info).")

	try:
		tb_list = traceback.format_exception(None, err, getattr(err, "__traceback__", None))
		tb_s = "".join(tb_list)
	except Exception:
		tb_s = "N/A"

	try:
		if isinstance(upd, Update):
			upd_s_obj = upd.to_dict()
		else:
			upd_s_obj = str(upd)
	except Exception:
		upd_s_obj = "N/A"

	try:
		chat_slice = str(getattr(ctx, "chat_data", ""))[:200]
		user_slice = str(getattr(ctx, "user_data", ""))[:200]
		ctx_s = f"Chat:{chat_slice} User:{user_slice}"
	except Exception:
		ctx_s = "N/A"

	e_err = html.escape(str(err)) if err is not None else "N/A"
	try:
		e_upd = html.escape(json.dumps(upd_s_obj, indent=1, ensure_ascii=False)[:600])
	except Exception:
		e_upd = "N/A"
	e_ctx = html.escape(ctx_s)
	e_tb = html.escape(tb_s[-1200:]) if tb_s else "N/A"

	dev_msg = (
		f"⚠️ <b>Exc</b> ⚠️\n"
		f"<b>Err:</b><pre>{e_err}</pre>\n"
		f"<b>Upd:</b><pre>{e_upd}</pre>\n"
		f"<b>Ctx:</b><pre>{e_ctx}</pre>\n"
		f"<b>TB:</b><pre>{e_tb}</pre>"
	)

	if settings.developer_chat_id:
		try:
			await ctx.bot.send_message(
				chat_id=settings.developer_chat_id,
				text=dev_msg[:4096],
				parse_mode=ParseMode.HTML,
			)
			log.debug(f"Err notify sent dev {settings.developer_chat_id}.")
		except TelegramError as e:
			log.error(
				f"Failed send err dev {settings.developer_chat_id}: {e}. Orig err: {err}",
				exc_info=True,
			)
		except Exception as e:
			log.error(
				f"Unexpected err sending notify: {e}. Orig err: {err}",
				exc_info=True,
			)

	if isinstance(upd, Update) and upd.effective_message:
		try:
			await upd.effective_message.reply_text(lang.MSG_ERROR_GENERAL)
		except Exception as e:
			log.error(f"Failed send user err msg: {e}", exc_info=True)