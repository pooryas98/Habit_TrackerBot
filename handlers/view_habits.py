# handlers/view_habits.py

import logging
from telegram import Update, InlineKeyboardMarkup
from telegram.ext import CommandHandler, CallbackContext
from typing import Dict, Any
# import aiosqlite # Not needed directly here

from utils import localization as lang, helpers, keyboards, constants as c
from database import db_manager # Import db_manager module

logger = logging.getLogger(__name__)

# Updated Helper: No longer needs db passed explicitly
async def _generate_today_message(user_id: int) -> Dict[str, Any]:
    """Helper function to generate the text and keyboard for /today."""
    try:
        # Uses global connection internally via db_manager calls
        today = helpers.get_today_date()
        habits = await db_manager.get_user_habits(user_id)
        statuses = await db_manager.get_todays_habit_statuses(user_id, today)

        if not habits:
            return {"text": lang.MSG_NO_HABITS_TODAY, "reply_markup": None}

        today_str = helpers.format_date_user_friendly(today)
        message_text = lang.MSG_TODAY_HEADER.format(today_date=today_str) + "\n\n"
        habits_with_status_for_keyboard = []

        for habit_id, name, _, _ in habits:
            status = statuses.get(habit_id, 'pending')
            status_text = lang.STATUS_DONE if status == 'done' else lang.STATUS_PENDING
            message_text += f"- {name}: {status_text}\n"
            habits_with_status_for_keyboard.append((habit_id, name, status))

        reply_markup = keyboards.today_habits_keyboard(habits_with_status_for_keyboard)
        return {"text": message_text, "reply_markup": reply_markup}

    except ConnectionError:
         logger.error("Database connection unavailable for _generate_today_message")
         # Return error message structure to be handled by caller
         return {"text": lang.ERR_DATABASE_CONNECTION, "reply_markup": None}
    except Exception as e:
         logger.error(f"Error generating today message content: {e}", exc_info=True)
         return {"text": lang.MSG_ERROR_GENERAL, "reply_markup": None}


async def show_today(update: Update, context: CallbackContext) -> None:
    """Displays the list of habits and their status for today."""
    if not update.effective_message or not update.effective_user: return
    user_id = update.effective_user.id

    # Call helper which handles DB connection internally
    message_content = await _generate_today_message(user_id)
    await update.effective_message.reply_text(
        text=message_content['text'],
        reply_markup=message_content['reply_markup']
    )


async def show_history(update: Update, context: CallbackContext) -> None:
    """Displays recent habit history."""
    if not update.effective_message or not update.effective_user: return
    user_id = update.effective_user.id

    try:
        # Use db_manager directly
        limit = 15
        log_entries = await db_manager.get_habit_log(user_id, limit=limit)

        if not log_entries:
            await update.effective_message.reply_text(lang.MSG_NO_HISTORY)
            return

        message_text = lang.MSG_HISTORY_HEADER.format(limit=limit) + "\n\n"
        for log_date, habit_name, status in log_entries:
            status_icon = "✅" if status == 'done' else "❌"
            date_str = helpers.format_date_user_friendly(log_date)
            message_text += f"{date_str}: {status_icon} {habit_name}\n"

        if len(log_entries) == limit:
             message_text += f"\n{lang.MSG_HISTORY_MORE_AVAILABLE}"

        await update.effective_message.reply_text(message_text)

    except ConnectionError:
        logger.error("Database connection unavailable for /history")
        await update.effective_message.reply_text(lang.ERR_DATABASE_CONNECTION)
    except Exception as e:
        logger.error(f"Error generating /history view for user {user_id}: {e}", exc_info=True)
        await update.effective_message.reply_text(lang.MSG_ERROR_GENERAL)

async def show_stats(update: Update, context: CallbackContext) -> None:
    """Displays habit completion statistics."""
    if not update.effective_message or not update.effective_user: return
    user_id = update.effective_user.id

    try:
        # Use db_manager directly
        days_period = 30
        habit_stats = await db_manager.get_completion_stats(user_id, days_back=days_period)

        if not habit_stats:
            await update.effective_message.reply_text(lang.MSG_NO_STATS_DATA)
            return

        message_text = lang.MSG_STATS_HEADER.format(days=days_period) + "\n\n"
        for habit_id, stats in habit_stats.items():
            message_text += f"📊 **{stats['name']}**:\n"
            message_text += lang.MSG_STATS_COMPLETION.format(
                rate=stats['completion_rate'], done=stats['done_count'], total=stats['total_days']
            ) + "\n"
            message_text += lang.MSG_STATS_STREAK.format(
                current=stats['current_streak'], max_streak=stats['max_streak']
            ) + "\n\n"

        await update.effective_message.reply_text(message_text, parse_mode='Markdown')

    except ConnectionError:
        logger.error("Database connection unavailable for /stats")
        await update.effective_message.reply_text(lang.ERR_DATABASE_CONNECTION)
    except Exception as e:
        logger.error(f"Error generating /stats view for user {user_id}: {e}", exc_info=True)
        await update.effective_message.reply_text(lang.MSG_ERROR_GENERAL)


def today_handler():
    return CommandHandler(c.CMD_TODAY, show_today)

def history_handler():
    return CommandHandler(c.CMD_HISTORY, show_history)

def stats_handler():
    return CommandHandler(c.CMD_STATS, show_stats)