from datetime import datetime, time, date, timedelta, tzinfo
import re
from typing import Optional, Callable # Added Callable
import html
import logging # Added logging
from telegram import Update
from telegram.ext import CallbackContext, ConversationHandler
from . import localization as lang # Assuming localization is in the same directory

# Import the configured timezone
from config import USER_TIMEZONE

logger = logging.getLogger(__name__) # Added logger

EXAMPLE_TIME_FORMAT = "HH:MM (e.g., 09:00, 17:30)"

def get_today_date() -> date:
    """Gets today's date based on configured USER_TIMEZONE."""
    return datetime.now(USER_TIMEZONE).date()

def parse_reminder_time(time_str: str) -> Optional[time]:
    """Parses HH:MM or H time string into a naive time object."""
    time_str = time_str.strip()
    match_hhmm = re.fullmatch(r"(\d{1,2}):(\d{2})", time_str)
    if match_hhmm:
        try:
            hour, minute = int(match_hhmm.group(1)), int(match_hhmm.group(2))
            if 0 <= hour <= 23 and 0 <= minute <= 59: return time(hour, minute)
        except ValueError: pass

    match_h = re.fullmatch(r"(\d{1,2})", time_str)
    if match_h:
        try:
            hour = int(match_h.group(1))
            if 0 <= hour <= 23: return time(hour, 0) # Assume :00
        except ValueError: pass

    return None

def format_time_user_friendly(t: time) -> str:
    """Formats time object into HH:MM string."""
    return t.strftime("%H:%M")

def format_date_user_friendly(d: date) -> str:
    """Formats date object into YYYY-MM-DD string."""
    return d.strftime("%Y-%m-%d")

def escape_html(text: Optional[str]) -> str:
    """Basic HTML escaping for user text (escapes &, <, >)."""
    return html.escape(str(text)) if text is not None else ""

# --- Generic Cancellation Helper (from Pass 1) ---
async def cancel_conversation(
    update: Update,
    context: CallbackContext,
    clear_context_func: Optional[Callable[[CallbackContext], None]] = None,
    log_message: str = "Conversation cancelled."
) -> int:
    """
    Handles conversation cancellation: sends message, clears context, logs, returns END.
    """
    message = lang.MSG_CANCELLED

    if update.callback_query:
        await update.callback_query.answer()
        try:
            await update.callback_query.edit_message_text(message)
        except Exception as e:
            logger.debug(f"Could not edit message on cancel callback: {e}")
            # Try sending if edit fails
            if update.effective_message:
                try: await update.effective_message.reply_text(message)
                except Exception as e2: logger.warning(f"Could not send cancel message either: {e2}")
    elif update.effective_message:
        await update.effective_message.reply_text(message)

    if clear_context_func:
        clear_context_func(context)

    user_id = update.effective_user.id if update.effective_user else 'Unknown'
    logger.debug(f"{log_message} User ID: {user_id}")

    return ConversationHandler.END