# handlers/reminders.py

import logging
from telegram import Update, InlineKeyboardMarkup
from telegram.ext import (
    CommandHandler, MessageHandler, filters, ConversationHandler, CallbackContext, JobQueue, CallbackQueryHandler, Job
)
from telegram.error import BadRequest, Forbidden
import datetime
from typing import cast, Optional, List, Tuple
import aiosqlite

from config import USER_TIMEZONE
from utils import localization as lang, helpers, keyboards, constants as c
from database import db_manager
# --- Add imports ---
from utils.checks import require_membership
# --- End imports ---

logger = logging.getLogger(__name__)

# Updated Conversation States
(SELECT_REMINDER_HABIT, ASK_REMINDER_TIME) = c.SET_REMINDER_STATES

# --- Reminder Callback Function (Job Execution) ---
async def reminder_callback(context: CallbackContext):
    """The function called by the JobQueue to send a reminder."""
    job = context.job
    if not job or not isinstance(job, Job) or not job.data or not isinstance(job.data, dict):
        logger.warning("Reminder job callback missing or invalid data.")
        return

    user_id = job.data.get("user_id")
    habit_id = job.data.get("habit_id")
    habit_name = job.data.get("habit_name")

    if not user_id or not habit_id:
        logger.error(f"Incomplete critical data in reminder job: {job.data}")
        return

    jq = context.job_queue
    if not jq: logger.error(f"JobQueue not found in reminder_callback context for job {job.name}.")

    try:
        db_conn = await db_manager.get_db_connection()
        if not habit_name:
            habit_name = await db_manager.get_habit_name_by_id(habit_id)
            if not habit_name:
                 logger.warning(f"Habit {habit_id} not found when trying to send reminder for job {job.name}. Removing job.")
                 await _remove_reminder_and_job(jq, habit_id, job.name)
                 return

        logger.info(f"Executing reminder job {job.name}: Habit '{habit_name}' (ID: {habit_id}) for user {user_id}")
        await context.bot.send_message(chat_id=user_id, text=lang.MSG_REMINDER_ALERT.format(habit_name=habit_name))
        logger.info(f"Reminder sent successfully for job {job.name}")

    except ConnectionError: logger.error(f"Database connection unavailable in reminder_callback for job {job.name}")
    except (BadRequest, Forbidden) as e:
        logger.warning(f"Failed to send reminder for job {job.name} to user {user_id}. Error: {e}. Removing reminder.")
        await _remove_reminder_and_job(jq, habit_id, job.name)
    except Exception as e: logger.error(f"Unexpected error sending reminder for job {job.name}: {e}", exc_info=True)


# --- Helper to remove jobs ---
def remove_job_if_exists(name: str, job_queue: Optional[JobQueue]) -> bool:
    if not job_queue: logger.error(f"Cannot remove job '{name}', JobQueue is missing."); return False
    current_jobs = job_queue.get_jobs_by_name(name)
    if not current_jobs: logger.debug(f"No job found with name '{name}' to remove."); return False
    removed = False
    for job in current_jobs: job.schedule_removal(); removed = True; logger.info(f"Scheduled removal for job '{job.name}'")
    return removed

async def _remove_reminder_and_job(jq: Optional[JobQueue], habit_id: int, job_name: Optional[str] = None) -> bool:
    logger.warning(f"Attempting to remove reminder and job for habit {habit_id}.")
    removed_db, removed_jq = False, False
    try:
        if not job_name:
            reminder_details = await db_manager.get_reminder_by_habit_id(habit_id)
            if reminder_details: job_name = reminder_details[2]
        deleted_job_name = await db_manager.remove_reminder_by_habit_id(habit_id)
        if deleted_job_name is not None: removed_db = True; job_name = deleted_job_name
        else:
             logger.debug(f"Reminder for habit {habit_id} not found in DB (or DB error).")
             if not job_name: logger.warning(f"Could not determine job name for habit {habit_id} to remove from queue.")
        if job_name and jq: removed_jq = remove_job_if_exists(job_name, jq)
        logger.info(f"Removal result for habit {habit_id}: DB removed={removed_db}, JobQueue removed={removed_jq} (using job name '{job_name}')")
        return removed_db or removed_jq
    except ConnectionError:
        logger.error(f"Database connection unavailable during _remove_reminder_and_job for habit {habit_id}")
        if job_name and jq: removed_jq = remove_job_if_exists(job_name, jq); logger.warning(f"DB removal failed due to connection error, but queue removal attempted (removed={removed_jq})"); return removed_jq
        return False
    except Exception as e: logger.error(f"Unexpected error during _remove_reminder_and_job: {e}", exc_info=True); return False


# --- Conversation for Setting Reminder ---

# --- Apply decorator ---
@require_membership
async def ask_reminder_habit(update: Update, context: CallbackContext) -> int:
    """ENTRY POINT: Asks user to select a habit from a list."""
    # Decorator handles membership check
    if not update.message or not update.effective_user: return ConversationHandler.END
    user_id = update.effective_user.id

    try:
        user_habits = await db_manager.get_user_habits(user_id)
        if not user_habits:
            await update.message.reply_text(lang.MSG_NO_HABITS_FOR_REMINDER)
            return ConversationHandler.END

        keyboard = keyboards.select_habit_keyboard(user_habits, c.CALLBACK_SELECT_REMINDER_HABIT)
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(lang.PROMPT_SELECT_REMINDER_HABIT_LIST, reply_markup=reply_markup)
        return SELECT_REMINDER_HABIT

    except ConnectionError:
        logger.error("Database connection unavailable for ask_reminder_habit")
        await update.message.reply_text(lang.ERR_DATABASE_CONNECTION)
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"Error fetching habits for reminder selection: {e}", exc_info=True)
        await update.message.reply_text(lang.MSG_ERROR_GENERAL)
        return ConversationHandler.END
# --- End decorator application ---

async def select_reminder_habit_callback(update: Update, context: CallbackContext) -> int:
    """Handles habit selection via button press and asks for time."""
    query = update.callback_query
    if not query: return ConversationHandler.END
    await query.answer()

    if not query.data or not query.data.startswith(c.CALLBACK_SELECT_REMINDER_HABIT):
        logger.warning(f"Invalid callback data in select_reminder_habit_callback: {query.data}")
        await query.edit_message_text(lang.ERR_GENERIC_CALLBACK)
        return ConversationHandler.END

    try:
        habit_id = int(query.data.split('_', 1)[1])
        habit_name = await db_manager.get_habit_name_by_id(habit_id)
        if not habit_name:
            logger.warning(f"Habit {habit_id} selected for reminder not found (maybe deleted?).")
            await query.edit_message_text(lang.ERR_HABIT_NOT_FOUND_GENERIC)
            return ConversationHandler.END

        context.user_data['reminder_habit_id'] = habit_id
        context.user_data['reminder_habit_name'] = habit_name
        logger.debug(f"User selected habit '{habit_name}' (ID: {habit_id}) for reminder.")

        await query.edit_message_text(lang.PROMPT_REMINDER_TIME.format(habit_name=habit_name))
        return ASK_REMINDER_TIME

    except (IndexError, ValueError):
        logger.error(f"Could not parse habit_id from callback data: {query.data}", exc_info=True)
        await query.edit_message_text(lang.ERR_GENERIC_CALLBACK)
        return ConversationHandler.END
    except ConnectionError:
        logger.error("Database connection unavailable for select_reminder_habit_callback")
        await query.edit_message_text(lang.ERR_DATABASE_CONNECTION)
        return ConversationHandler.END
    except Exception as e:
         logger.error(f"Error processing reminder habit selection: {e}", exc_info=True)
         await query.edit_message_text(lang.MSG_ERROR_GENERAL)
         return ConversationHandler.END

async def receive_reminder_time_and_set(update: Update, context: CallbackContext) -> int:
    """Receives time, sets the reminder job, and saves to DB."""
    if not update.message or not update.message.text: return ASK_REMINDER_TIME
    if 'reminder_habit_id' not in context.user_data or 'reminder_habit_name' not in context.user_data:
        logger.warning("User data missing habit info in receive_reminder_time_and_set.")
        await update.message.reply_text(lang.ERR_REMINDER_SET_FAILED_CONTEXT)
        _clear_reminder_context(context)
        return ConversationHandler.END

    time_str = update.message.text.strip()
    parsed_time = helpers.parse_reminder_time(time_str)
    habit_name = context.user_data['reminder_habit_name']

    if not parsed_time:
        await update.message.reply_text(lang.ERR_REMINDER_INVALID_TIME.format(example=helpers.EXAMPLE_TIME_FORMAT))
        await update.message.reply_text(lang.PROMPT_REMINDER_TIME.format(habit_name=habit_name))
        return ASK_REMINDER_TIME

    job_queue = cast(JobQueue, context.job_queue)
    if not job_queue:
         logger.error("JobQueue not found in receive_reminder_time_and_set")
         await update.message.reply_text(lang.ERR_REMINDER_SET_FAILED_SCHEDULE)
         _clear_reminder_context(context)
         return ConversationHandler.END

    user_id = update.effective_user.id
    habit_id = context.user_data['reminder_habit_id']
    job_name = f"{c.JOB_PREFIX_REMINDER}{user_id}_{habit_id}"

    try:
        await _remove_reminder_and_job(job_queue, habit_id)
        job = job_queue.run_daily(
            callback=reminder_callback, time=parsed_time, name=job_name,
            chat_id=user_id, user_id=user_id,
            data={"user_id": user_id, "habit_id": habit_id, "habit_name": habit_name}
        )
        if not job or not job.name: raise RuntimeError("JobQueue.run_daily did not return a valid job object.")
        logger.info(f"Scheduled job '{job.name}' for habit {habit_id} at {parsed_time} ({USER_TIMEZONE.key if hasattr(USER_TIMEZONE,'key') else USER_TIMEZONE})")

        db_success = await db_manager.add_or_update_reminder_db(user_id, habit_id, parsed_time, job_name)

        if db_success:
            formatted_time = helpers.format_time_user_friendly(parsed_time)
            await update.message.reply_text(lang.CONFIRM_REMINDER_SET.format(habit_name=habit_name, time_str=formatted_time))
        else:
            await update.message.reply_text(lang.ERR_REMINDER_SET_FAILED_DB)
            logger.warning(f"DB save failed for reminder job {job_name}. Attempting job removal.")
            remove_job_if_exists(job_name, job_queue)

    except ConnectionError:
        logger.error("Database connection unavailable for receive_reminder_time_and_set")
        await update.message.reply_text(lang.ERR_DATABASE_CONNECTION)
        if 'job' in locals() and job and job.name: remove_job_if_exists(job.name, job_queue)
    except Exception as e:
        logger.error(f"Failed to schedule job or save reminder {job_name}: {e}", exc_info=True)
        await update.message.reply_text(lang.ERR_REMINDER_SET_FAILED)
        remove_job_if_exists(job_name, job_queue)

    _clear_reminder_context(context)
    return ConversationHandler.END


async def cancel_reminder_conv(update: Update, context: CallbackContext) -> int:
    message = lang.MSG_CANCELLED
    edit_failed = False
    if update.callback_query:
         await update.callback_query.answer()
         try:
             await update.callback_query.edit_message_text(message)
         except Exception as e:
              logger.debug(f"Could not edit message on cancel: {e}")
              edit_failed = True
              if update.effective_message:
                   try: await update.effective_message.reply_text(message)
                   except Exception as e2: logger.warning(f"Could not send cancel message either: {e2}")
    elif update.effective_message:
        await update.effective_message.reply_text(message)

    _clear_reminder_context(context)
    logger.debug(f"Set reminder conversation cancelled by user {update.effective_user.id if update.effective_user else 'Unknown'}")
    return ConversationHandler.END

def _clear_reminder_context(context: CallbackContext):
    context.user_data.pop('reminder_habit_id', None)
    context.user_data.pop('reminder_habit_name', None)

# --- Use decorated function in entry_points ---
def set_reminder_conv_handler():
    """Creates the ConversationHandler for setting reminders."""
    # ask_reminder_habit is already decorated
    return ConversationHandler(
        entry_points=[CommandHandler(c.CMD_SET_REMINDER, ask_reminder_habit)], # Use original name
        states={
            SELECT_REMINDER_HABIT: [
                CallbackQueryHandler(select_reminder_habit_callback, pattern=f"^{c.CALLBACK_SELECT_REMINDER_HABIT}")
            ],
            ASK_REMINDER_TIME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_reminder_time_and_set)
            ],
        },
        fallbacks=[
            CommandHandler(c.CMD_CANCEL, cancel_reminder_conv),
        ],
        persistent=False,
        name="set_reminder_conversation"
    )
# --- End change ---

# --- Manage/Delete Reminders ---
# No changes needed below this line for membership check in this file
async def list_reminders(update: Update, context: CallbackContext) -> None:
    # ... (implementation unchanged) ...
    if not update.effective_message or not update.effective_user: return
    user_id = update.effective_user.id
    try:
        user_reminders_db = await db_manager.get_user_reminders(user_id)
        if not user_reminders_db:
            await update.effective_message.reply_text(lang.MSG_NO_REMINDERS); return
        reminders_for_keyboard: List[Tuple[int, str, str]] = []
        for habit_id, reminder_time, _ in user_reminders_db:
            habit_name = await db_manager.get_habit_name_by_id(habit_id)
            if habit_name:
                time_str = helpers.format_time_user_friendly(reminder_time)
                reminders_for_keyboard.append((habit_id, habit_name, time_str))
            else: logger.warning(f"Reminder found for non-existent habit ID {habit_id} (user {user_id}). Skipping.")
        if not reminders_for_keyboard: await update.effective_message.reply_text(lang.MSG_NO_REMINDERS); return
        reply_markup = keyboards.reminder_management_keyboard(reminders_for_keyboard)
        await update.effective_message.reply_text(lang.PROMPT_MANAGE_REMINDERS, reply_markup=reply_markup)
    except ConnectionError: logger.error("Database connection unavailable for list_reminders"); await update.effective_message.reply_text(lang.ERR_DATABASE_CONNECTION)
    except Exception as e: logger.error(f"Error listing reminders: {e}", exc_info=True); await update.effective_message.reply_text(lang.MSG_ERROR_GENERAL)


async def delete_reminder_button(update: Update, context: CallbackContext) -> None:
    # ... (implementation unchanged) ...
    query = update.callback_query; await query.answer()
    job_queue = cast(JobQueue, context.job_queue)
    if not job_queue: logger.error("JobQueue not found"); await query.edit_message_text(lang.ERR_REMINDER_DELETE_FAILED_INTERNAL); return
    try:
        if not query.data or not query.data.startswith(c.CALLBACK_DELETE_REMINDER): raise ValueError("Invalid prefix")
        habit_id = int(query.data.split('_', 1)[1])
    except (ValueError, IndexError, TypeError): logger.error(f"Bad callback data: {query.data}", exc_info=True); await query.edit_message_text(lang.ERR_GENERIC_CALLBACK); return
    try:
        habit_name = await db_manager.get_habit_name_by_id(habit_id) or lang.DEFAULT_HABIT_NAME
        removed = await _remove_reminder_and_job(job_queue, habit_id)
        if removed: await query.edit_message_text(lang.CONFIRM_REMINDER_DELETED.format(habit_name=habit_name))
        else: await query.edit_message_text(lang.ERR_REMINDER_DELETE_FAILED.format(habit_name=habit_name))
    except ConnectionError: logger.error("DB unavailable"); await query.edit_message_text(lang.ERR_DATABASE_CONNECTION)
    except Exception as e: logger.error(f"Error deleting reminder: {e}", exc_info=True); await query.edit_message_text(lang.ERR_REMINDER_DELETE_FAILED_INTERNAL)

def manage_reminders_handler(): return CommandHandler(c.CMD_MANAGE_REMINDERS, list_reminders) # Needs decoration in main.py
def delete_reminder_button_handler(): return CallbackQueryHandler(delete_reminder_button, pattern=f"^{c.CALLBACK_DELETE_REMINDER}") # Needs decoration in main.py

async def schedule_all_reminders(db: aiosqlite.Connection, job_queue: JobQueue):
    # ... (implementation unchanged) ...
    logger.info("Scheduling reminders from database...")
    try:
        all_reminders = []
        async with db.execute("SELECT user_id, habit_id, reminder_time, job_name FROM Reminders") as cursor:
             rows = await cursor.fetchall()
             for row in rows:
                 try: rt = datetime.datetime.strptime(row[2], '%H:%M:%S').time(); all_reminders.append((row[0], row[1], rt, row[3]))
                 except (ValueError, TypeError): logger.warning(f"Skipping reminder: invalid time format {row}")
        count, skipped, failures = 0, 0, 0
        for user_id, habit_id, reminder_time, stored_job_name in all_reminders:
            expected_job_name = f"{c.JOB_PREFIX_REMINDER}{user_id}_{habit_id}"
            if stored_job_name != expected_job_name: logger.warning(f"Job name mismatch: {habit_id}. DB:'{stored_job_name}', Expected:'{expected_job_name}'.")
            habit_name = None
            async with db.execute("SELECT name FROM Habits WHERE habit_id = ?", (habit_id,)) as cursor: res = await cursor.fetchone(); habit_name = res[0] if res else None
            if not habit_name:
                logger.warning(f"Skipping reminder: deleted habit ID {habit_id}. Removing orphan.")
                skipped += 1; await db.execute("DELETE FROM Reminders WHERE habit_id = ?", (habit_id,)); await db.commit()
                remove_job_if_exists(expected_job_name, job_queue); remove_job_if_exists(stored_job_name, job_queue)
                continue
            remove_job_if_exists(expected_job_name, job_queue); remove_job_if_exists(stored_job_name, job_queue)
            try:
                job = job_queue.run_daily(callback=reminder_callback, time=reminder_time, name=expected_job_name, chat_id=user_id, user_id=user_id, data={"user_id": user_id, "habit_id": habit_id, "habit_name": habit_name})
                if job: count += 1;
                else: logger.error(f"Failed reschedule job {expected_job_name} (Job=None)."); failures += 1
            except Exception as e: logger.error(f"Exception scheduling job {expected_job_name}: {e}", exc_info=True); failures += 1
        logger.info(f"Reminders scheduled: {count}, Skipped: {skipped}, Failures: {failures}")
    except aiosqlite.Error as e: logger.error(f"DB error: {e}", exc_info=True)
    except Exception as e: logger.error(f"Unexpected error: {e}", exc_info=True)