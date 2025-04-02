import html
import json
import logging
import traceback
from telegram import Update
from telegram.ext import CallbackContext
from telegram.constants import ParseMode
from utils import localization as lang
from config import DEVELOPER_CHAT_ID

logger = logging.getLogger(__name__)

async def error_handler(update: object, context: CallbackContext) -> None:
    """Logs errors, notifies developer, sends user-friendly message."""
    logger.error("Exception while handling update:", exc_info=context.error)

    if context.error and isinstance(context.error, Exception) and "error_handler" in str(context.error): return # Avoid self-recursion

    tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
    tb_string = "".join(tb_list)

    update_str = update.to_dict() if isinstance(update, Update) else str(update)
    max_len = 500 # Limit log/message section length
    context_str = f"ChatData: {str(context.chat_data)[:max_len]}\nUserDate: {str(context.user_data)[:max_len]}"

    dev_message = (
        f"⚠️ Exception:\nError: {html.escape(str(context.error))}\n\n"
        f"<pre>Update: {html.escape(json.dumps(update_str, indent=1, ensure_ascii=False)[:max_len])}</pre>\n\n"
        f"<pre>Context: {html.escape(context_str)}</pre>\n\n"
        f"<pre>Traceback:\n{html.escape(tb_string[-2000:])}</pre>" # Last part of traceback
    )

    if DEVELOPER_CHAT_ID:
        try:
            await context.bot.send_message(chat_id=DEVELOPER_CHAT_ID, text=dev_message[:4096], parse_mode=ParseMode.HTML)
        except Exception as e:
            logger.error(f"Failed to send error to developer ({DEVELOPER_CHAT_ID}): {e}", exc_info=True)

    # Send user-friendly message if possible
    if isinstance(update, Update) and update.effective_message:
        try: await update.effective_message.reply_text(lang.MSG_ERROR_GENERAL)
        except Exception as e: logger.error(f"Failed to send user-facing error msg: {e}", exc_info=True)