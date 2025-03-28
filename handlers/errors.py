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
    """Logs errors, notifies developer (if configured), and sends user-friendly message."""
    # Log the error before anything else
    logger.error("Exception while handling an update:", exc_info=context.error)

    # Don't try to notify if the error is within the error handler itself
    if context.error and isinstance(context.error, Exception) and "error_handler" in str(context.error):
         return

    # Format traceback
    tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
    tb_string = "".join(tb_list)

    # Format update/context data for logging/developer message
    update_str = update.to_dict() if isinstance(update, Update) else str(update)
    # Limit length to avoid hitting Telegram message limits
    max_len_per_section = 500
    context_str = f"ChatData: {str(context.chat_data)[:max_len_per_section]}\nUserDate: {str(context.user_data)[:max_len_per_section]}"

    dev_message = (
        f"⚠️ Exception occurred!\n\n"
        f"Error: {html.escape(str(context.error))}\n\n"
        f"<pre>Update: {html.escape(json.dumps(update_str, indent=1, ensure_ascii=False)[:max_len_per_section])}</pre>\n\n"
        f"<pre>Context: {html.escape(context_str)}</pre>\n\n"
        f"<pre>Traceback:\n{html.escape(tb_string[-2000:])}</pre>" # Last part of traceback
    )

    # Send detailed error to developer(s) if configured
    if DEVELOPER_CHAT_ID:
        try:
            await context.bot.send_message(
                chat_id=DEVELOPER_CHAT_ID,
                text=dev_message[:4096], # Ensure message doesn't exceed max length
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.error(f"Failed to send detailed error to developer ({DEVELOPER_CHAT_ID}): {e}", exc_info=True)

    # Send user-friendly message (if possible)
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(lang.MSG_ERROR_GENERAL)
        except Exception as e:
            # Log failure to send user message, but don't crash the error handler
            logger.error(f"Failed to send user-facing error message: {e}", exc_info=True)

