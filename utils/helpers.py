from datetime import datetime, time, date, timedelta, tzinfo
import re, html, logging
from typing import Optional, Callable
from telegram import Update
from telegram.ext import CallbackContext, ConversationHandler
from . import localization as lang
from config import USER_TIMEZONE

logger = logging.getLogger(__name__)
EXAMPLE_TIME_FORMAT = "HH:MM (e.g., 09:00, 17:30)"

def get_today_date() -> date: return datetime.now(USER_TIMEZONE).date()

def parse_reminder_time(time_str: str) -> Optional[time]:
    """Parses HH:MM or H into naive time object."""
    time_str = time_str.strip()
    if match := re.fullmatch(r"(\d{1,2}):(\d{2})", time_str):
        try: h, m = int(match[1]), int(match[2]); return time(h, m) if 0 <= h <= 23 and 0 <= m <= 59 else None
        except ValueError: pass
    if match := re.fullmatch(r"(\d{1,2})", time_str):
        try: h = int(match[1]); return time(h, 0) if 0 <= h <= 23 else None
        except ValueError: pass
    return None

def format_time_user_friendly(t: time) -> str: return t.strftime("%H:%M")
def format_date_user_friendly(d: date) -> str: return d.strftime("%Y-%m-%d")
def escape_html(text: Optional[str]) -> str: return html.escape(str(text)) if text is not None else ""

async def cancel_conversation(
    update: Update, ctx: CallbackContext,
    clear_ctx_func: Optional[Callable[[CallbackContext], None]] = None,
    log_msg: str = "Conversation cancelled."
) -> int:
    """Handles conversation cancel: sends msg, clears context, logs, returns END."""
    if update.callback_query:
        await update.callback_query.answer()
        try: await update.callback_query.edit_message_text(lang.MSG_CANCELLED)
        except Exception as e:
            logger.debug(f"Could not edit msg on cancel: {e}")
            if update.effective_message:
                try: await update.effective_message.reply_text(lang.MSG_CANCELLED)
                except Exception as e2: logger.warning(f"Could not send cancel msg: {e2}")
    elif update.effective_message: await update.effective_message.reply_text(lang.MSG_CANCELLED)

    if clear_ctx_func: clear_ctx_func(ctx)
    user_id = update.effective_user.id if update.effective_user else 'Unknown'
    logger.debug(f"{log_msg} User ID: {user_id}")
    return ConversationHandler.END