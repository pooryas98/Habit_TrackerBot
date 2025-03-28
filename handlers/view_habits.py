# handlers/view_habits.py

import logging
import math # For pagination calculation
from telegram import Update, InlineKeyboardMarkup
# --- ADD THESE IMPORTS ---
from telegram.helpers import escape_markdown
from telegram.constants import ParseMode
# --- END ADD ---
from telegram.ext import CommandHandler, CallbackContext, CallbackQueryHandler
from telegram.error import BadRequest
from typing import Dict, Any

# --- Corrected import assuming escape_html is in helpers ---
from utils import localization as lang, helpers, keyboards, constants as c
# --- End corrected import ---
from database import db_manager # Import db_manager module

logger = logging.getLogger(__name__)

# --- Today View ---
async def _generate_today_message(user_id: int) -> Dict[str, Any]:
    """
    Helper function to generate the text and keyboard for the /today command.
    Fetches habits and their statuses for the given user for today's date.
    Uses HTML parse mode.

    Args:
        user_id (int): The ID of the user.

    Returns:
        Dict[str, Any]: A dictionary containing 'text' (str), 'reply_markup' (InlineKeyboardMarkup or None),
                        and 'parse_mode'. Returns error message content on DB failure.
    """
    try:
        today = helpers.get_today_date()
        habits = await db_manager.get_user_habits(user_id)
        statuses = await db_manager.get_todays_habit_statuses(user_id, today)

        if not habits:
            # Return plain text if no habits
            return {"text": lang.MSG_NO_HABITS_TODAY, "reply_markup": None, "parse_mode": None}

        today_str = helpers.format_date_user_friendly(today)
        # Using HTML requires escaping user input (habit names)
        message_text = lang.MSG_TODAY_HEADER.format(today_date=today_str) + "\n\n"
        habits_with_status_for_keyboard = []

        for habit_id, name, _, _ in habits:
            status = statuses.get(habit_id, 'pending') # Default to pending if no log entry
            status_text = lang.STATUS_DONE if status == 'done' else lang.STATUS_PENDING
            # Escape name for HTML
            safe_name = helpers.escape_html(name)
            message_text += f"- {safe_name}: {status_text}\n"
            habits_with_status_for_keyboard.append((habit_id, name, status)) # Keyboard uses raw name

        reply_markup = keyboards.today_habits_keyboard(habits_with_status_for_keyboard)
        # Explicitly set HTML parse mode for the generated message
        return {"text": message_text, "reply_markup": reply_markup, "parse_mode": ParseMode.HTML}

    except ConnectionError:
         logger.error("Database connection unavailable for _generate_today_message")
         # Return plain text error message
         return {"text": lang.ERR_DATABASE_CONNECTION, "reply_markup": None, "parse_mode": None}
    except Exception as e:
         logger.error(f"Error generating today message content for user {user_id}: {e}", exc_info=True)
         # Return plain text error message
         return {"text": lang.MSG_ERROR_GENERAL, "reply_markup": None, "parse_mode": None}


async def show_today(update: Update, context: CallbackContext) -> None:
    """
    Displays the list of habits and their status for today using an inline keyboard.
    Triggered by the /today command.
    """
    if not update.effective_message or not update.effective_user: return
    user_id = update.effective_user.id

    # Generate message content (handles DB connection and parse_mode internally)
    message_content = await _generate_today_message(user_id)

    await update.effective_message.reply_text(
        text=message_content['text'],
        reply_markup=message_content['reply_markup'],
        parse_mode=message_content.get('parse_mode') # Use the mode from the helper
    )

# --- History View ---
async def _generate_history_content(user_id: int, offset: int = 0, limit: int = c.HISTORY_PAGE_LIMIT) -> Dict[str, Any]:
    """
    Helper function to generate the text and keyboard for the /history command (supports pagination).
    Uses HTML parse mode.

    Args:
        user_id (int): The user's ID.
        offset (int): The starting offset for fetching log entries.
        limit (int): The maximum number of entries per page.

    Returns:
        Dict[str, Any]: Dictionary with 'text', 'reply_markup', and 'parse_mode'.
    """
    try:
        log_entries = await db_manager.get_habit_log(user_id, limit=limit, offset=offset)
        total_count = await db_manager.get_habit_log_count(user_id)

        if total_count == 0:
            # Return plain text if no history
            return {"text": lang.MSG_NO_HISTORY, "reply_markup": None, "parse_mode": None}

        current_page = (offset // limit) + 1
        total_pages = math.ceil(total_count / limit)

        message_text = lang.MSG_HISTORY_HEADER.format(page_num=current_page, total_pages=total_pages) + "\n\n"
        if not log_entries and offset > 0:
             message_text += lang.MSG_NO_HISTORY
        else:
            for log_date, habit_name, status in log_entries:
                status_icon = "✅" if status == 'done' else "❌"
                date_str = helpers.format_date_user_friendly(log_date)
                # Escape name for HTML
                safe_habit_name = helpers.escape_html(habit_name)
                message_text += f"{date_str}: {status_icon} {safe_habit_name}\n"

        if total_pages > 1:
             message_text += f"\n{lang.MSG_HISTORY_FOOTER}"

        reply_markup = keyboards.history_pagination_keyboard(offset, total_count, limit)
        # Specify HTML parse mode for history view
        return {"text": message_text, "reply_markup": reply_markup, "parse_mode": ParseMode.HTML}

    except ConnectionError:
        logger.error(f"Database connection unavailable generating history for user {user_id}")
        # Return plain text error message
        return {"text": lang.ERR_DATABASE_CONNECTION, "reply_markup": None, "parse_mode": None}
    except Exception as e:
        logger.error(f"Error generating history content for user {user_id}: {e}", exc_info=True)
        # Return plain text error message
        return {"text": lang.MSG_ERROR_GENERAL, "reply_markup": None, "parse_mode": None}


async def show_history(update: Update, context: CallbackContext) -> None:
    """
    Displays recent habit history, supporting pagination via inline keyboard.
    Triggered by the /history command.
    """
    if not update.effective_message or not update.effective_user: return
    user_id = update.effective_user.id

    # Generate content for the first page (offset 0)
    message_content = await _generate_history_content(user_id, offset=0)

    await update.effective_message.reply_text(
        text=message_content['text'],
        reply_markup=message_content['reply_markup'],
        parse_mode=message_content.get('parse_mode') # Use mode from helper
    )


async def show_history_paginated(update: Update, context: CallbackContext) -> None:
    """
    Handles button presses for history pagination. Edits the original message.
    """
    query = update.callback_query
    if not query or not query.message or not query.from_user: return
    await query.answer() # Acknowledge button press

    try:
        # Validate callback data
        if not query.data or not query.data.startswith(c.CALLBACK_HISTORY_PAGE):
            raise ValueError("Invalid callback data for history pagination")
        offset = int(query.data.split('_', 1)[1])
    except (ValueError, TypeError, IndexError):
        logger.error(f"Failed to parse offset from history pagination callback: {query.data}", exc_info=True)
        await query.answer(text=lang.ERR_GENERIC_CALLBACK, show_alert=True)
        return

    user_id = query.from_user.id

    # Generate content for the requested page
    message_content = await _generate_history_content(user_id, offset=offset)

    # Edit the original message
    try:
        await query.edit_message_text(
            text=message_content['text'],
            reply_markup=message_content['reply_markup'],
            parse_mode=message_content.get('parse_mode') # Use mode from helper
        )
    except BadRequest as e:
        if "Message is not modified" in str(e):
            logger.debug(f"History page content not modified for offset {offset}.")
        else:
            logger.error(f"Failed to edit history message: {e}", exc_info=True)
            # Maybe notify user differently if edit fails?
    except Exception as e:
        logger.error(f"Unexpected error editing history message: {e}", exc_info=True)


# --- Stats View ---

async def show_stats(update: Update, context: CallbackContext) -> None:
    """
    Displays habit completion statistics (streaks, completion rate) over the last 30 days.
    Triggered by the /stats command. Uses MarkdownV2 formatting.
    """
    if not update.effective_message or not update.effective_user: return
    user_id = update.effective_user.id

    try:
        days_period = 30 # Lookback period for stats
        habit_stats = await db_manager.get_completion_stats(user_id, days_back=days_period)

        if not habit_stats:
            # Use the pre-escaped string from localization.py
            await update.effective_message.reply_text(
                lang.MSG_NO_STATS_DATA,
                parse_mode=ParseMode.MARKDOWN_V2
            )
            return

        # Use the pre-escaped MSG_STATS_HEADER from localization.py
        message_text = lang.MSG_STATS_HEADER.format(days=days_period) + "\n\n"

        for habit_id, stats in habit_stats.items():
            # Escape the user-provided habit name for MarkdownV2
            safe_habit_name = escape_markdown(stats['name'], version=2)

            # --- FIX: Escape numeric values before formatting ---
            # Convert numbers to strings *then* escape them
            rate_str = escape_markdown(str(stats['completion_rate']), version=2)
            done_str = escape_markdown(str(stats['done_count']), version=2)
            total_str = escape_markdown(str(stats['total_days']), version=2)
            current_str = escape_markdown(str(stats['current_streak']), version=2)
            max_str = escape_markdown(str(stats['max_streak']), version=2)
            # --- End FIX ---

            # Use the pre-escaped strings from localization.py for the templates
            # And the newly escaped variable strings
            message_text += f"📊 *{safe_habit_name}*:\n"
            # Use the escaped string versions of the numbers
            message_text += lang.MSG_STATS_COMPLETION.format(
                rate=rate_str, done=done_str, total=total_str
            ) + "\n"
            message_text += lang.MSG_STATS_STREAK.format(
                current=current_str, max_streak=max_str
            ) + "\n\n"

        # Send with MarkdownV2 parsing
        await update.effective_message.reply_text(
            message_text,
            parse_mode=ParseMode.MARKDOWN_V2
        )

    except ConnectionError:
        logger.error("Database connection unavailable for /stats")
        # Use plain text for error messages, or pre-escape them in localization.py if needed
        await update.effective_message.reply_text(lang.ERR_DATABASE_CONNECTION, parse_mode=None)
    except BadRequest as e:
         # Catch potential MarkdownV2 parsing errors during development/testing
         logger.error(f"BadRequest sending /stats message (likely MarkdownV2 issue): {e}", exc_info=True)
         await update.effective_message.reply_text(
              # Provide a more user-friendly error in production if desired
              f"Error displaying stats (formatting issue): {helpers.escape_html(str(e))}\nPlease report this error.",
              parse_mode=ParseMode.HTML # Use HTML for the error message itself
         )
    except Exception as e:
        logger.error(f"Error generating /stats view for user {user_id}: {e}", exc_info=True)
        await update.effective_message.reply_text(lang.MSG_ERROR_GENERAL, parse_mode=None)


# --- Handler Registration Functions --- (No changes needed here)
def today_handler():
    """Returns CommandHandler for /today."""
    return CommandHandler(c.CMD_TODAY, show_today)

def history_handler():
    """Returns CommandHandler for /history."""
    return CommandHandler(c.CMD_HISTORY, show_history)

def history_pagination_handler():
    """Returns CallbackQueryHandler for history pagination buttons."""
    return CallbackQueryHandler(show_history_paginated, pattern=f"^{c.CALLBACK_HISTORY_PAGE}")

def stats_handler():
    """Returns CommandHandler for /stats."""
    return CommandHandler(c.CMD_STATS, show_stats)