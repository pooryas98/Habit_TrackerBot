import html, json, logging, traceback
from telegram import Update
from telegram.ext import CallbackContext
from telegram.constants import ParseMode
from utils import localization as lang
from config import DEVELOPER_CHAT_ID

logger = logging.getLogger(__name__)

async def error_handler(update: object, ctx: CallbackContext) -> None:
    """Logs errors, notifies dev, sends user-friendly message."""
    if ctx.error and isinstance(ctx.error, Exception) and "error_handler" in str(ctx.error): return # Avoid self-recursion
    logger.error("Exception handling update:", exc_info=ctx.error)

    tb_list = traceback.format_exception(None, ctx.error, ctx.error.__traceback__)
    tb_string = "".join(tb_list)
    update_str = update.to_dict() if isinstance(update, Update) else str(update)
    max_len, tb_max_len = 500, 2000
    ctx_str = f"ChatData: {str(ctx.chat_data)[:max_len]}\nUserDate: {str(ctx.user_data)[:max_len]}"

    dev_msg = (
        f"⚠️ Exception:\nErr: {html.escape(str(ctx.error))}\n\n"
        f"<pre>Update: {html.escape(json.dumps(update_str, indent=1, ensure_ascii=False)[:max_len])}</pre>\n\n"
        f"<pre>Context: {html.escape(ctx_str)}</pre>\n\n"
        f"<pre>Traceback:\n{html.escape(tb_string[-tb_max_len:])}</pre>"
    )

    if DEVELOPER_CHAT_ID:
        try: await ctx.bot.send_message(chat_id=DEVELOPER_CHAT_ID, text=dev_msg[:4096], parse_mode=ParseMode.HTML)
        except Exception as e: logger.error(f"Failed sending error to dev ({DEVELOPER_CHAT_ID}): {e}", exc_info=True)

    if isinstance(update, Update) and update.effective_message:
        try: await update.effective_message.reply_text(lang.MSG_ERROR_GENERAL)
        except Exception as e: logger.error(f"Failed sending user-facing error: {e}", exc_info=True)