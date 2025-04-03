import logging, datetime
from telegram import Update, InlineKeyboardMarkup
from telegram.ext import CommandHandler, MessageHandler, filters, ConversationHandler, CallbackContext, JobQueue, CallbackQueryHandler, Job
from telegram.error import BadRequest, Forbidden
from typing import cast, Optional, List, Tuple
import aiosqlite
from utils import localization as lang, helpers, keyboards, constants as c
from database import db_manager
from utils.checks import require_membership

logger = logging.getLogger(__name__)
S_SELECT_HABIT, S_ASK_TIME = c.SET_REMINDER_STATES

async def reminder_callback(ctx: CallbackContext):
    """JobQueue callback to send a reminder message."""
    job = ctx.job
    if not job or not isinstance(job.data, dict): return
    user_id, habit_id, name = job.data.get("user_id"), job.data.get("habit_id"), job.data.get("habit_name")
    if not user_id or not habit_id: return
    jq = ctx.job_queue
    if not jq: logger.error(f"JobQueue missing in reminder_callback job {job.name}"); return

    try:
        if not name: # Fetch if missing
            name = await db_manager.get_habit_name_by_id(habit_id)
            if not name: logger.warning(f"Habit {habit_id} not found sending job {job.name}. Removing."); await _remove_reminder_job(jq, habit_id, job.name); return
        logger.info(f"Executing reminder job {job.name} for user {user_id}")
        await ctx.bot.send_message(chat_id=user_id, text=lang.MSG_REMINDER_ALERT.format(habit_name=name))
    except ConnectionError: logger.error(f"DB conn unavailable in reminder_callback job {job.name}")
    except (BadRequest, Forbidden) as e: logger.warning(f"Failed send job {job.name} to u {user_id} ({e}). Removing."); await _remove_reminder_job(jq, habit_id, job.name)
    except Exception as e: logger.error(f"Unexpected err send job {job.name}: {e}", exc_info=True)

def remove_job_if_exists(name: str, jq: Optional[JobQueue]) -> bool:
    """Removes jobs by name. Returns True if any removed."""
    if not jq or not (current_jobs := jq.get_jobs_by_name(name)): return False
    for job in current_jobs: job.schedule_removal()
    logger.info(f"Scheduled removal for job(s) '{name}'")
    return True

async def _remove_reminder_job(jq: Optional[JobQueue], habit_id: int, job_name: Optional[str] = None) -> bool:
    """Removes reminder from DB and job from queue. Returns True if anything removed."""
    logger.debug(f"Attempting remove reminder/job h {habit_id}.")
    removed_db, removed_jq = False, False
    try:
        if deleted_job_name := await db_manager.remove_reminder_by_habit_id(habit_id):
             removed_db = True; job_name = deleted_job_name
        if job_name and jq: removed_jq = remove_job_if_exists(job_name, jq)
        logger.info(f"Removal h {habit_id}: DB={removed_db}, JQ={removed_jq} (Job: '{job_name}')")
        return removed_db or removed_jq
    except ConnectionError:
        logger.error(f"DB conn unavailable during _remove_reminder_job h {habit_id}")
        if job_name and jq: removed_jq = remove_job_if_exists(job_name, jq); logger.warning(f"DB removal failed; JQ removed={removed_jq}"); return removed_jq
    except Exception as e: logger.error(f"Error removing reminder/job: {e}", exc_info=True)
    return False

# --- Set Reminder Conversation ---
def _clear_ctx(ctx: CallbackContext): ctx.user_data.pop('reminder_habit_id', None); ctx.user_data.pop('reminder_habit_name', None)

@require_membership
async def ask_habit(update: Update, ctx: CallbackContext) -> int:
    """Entry point: Asks user to select a habit."""
    msg, user = update.effective_message, update.effective_user
    if not msg or not user: return ConversationHandler.END
    try:
        habits = await db_manager.get_user_habits(user.id)
        if not habits: await msg.reply_text(lang.MSG_NO_HABITS_FOR_REMINDER); return ConversationHandler.END
        keyboard = keyboards.select_habit_keyboard(habits, c.CALLBACK_SELECT_REMINDER_HABIT)
        await msg.reply_text(lang.PROMPT_SELECT_REMINDER_HABIT_LIST, reply_markup=InlineKeyboardMarkup(keyboard))
        return S_SELECT_HABIT
    except ConnectionError: await msg.reply_text(lang.ERR_DATABASE_CONNECTION)
    except Exception as e: logger.error(f"Err fetch habits for reminder: {e}", exc_info=True); await msg.reply_text(lang.MSG_ERROR_GENERAL)
    return ConversationHandler.END

async def select_habit_cb(update: Update, ctx: CallbackContext) -> int:
    """Handles habit selection (button), asks for time."""
    query = update.callback_query
    if not query or not query.data or not query.message: return ConversationHandler.END
    await query.answer()
    if not query.data.startswith(c.CALLBACK_SELECT_REMINDER_HABIT): await query.edit_message_text(lang.ERR_GENERIC_CALLBACK); return ConversationHandler.END

    try:
        habit_id = int(query.data.split('_', 1)[1])
        name = await db_manager.get_habit_name_by_id(habit_id)
        if not name: await query.edit_message_text(lang.ERR_HABIT_NOT_FOUND_GENERIC); return ConversationHandler.END
        ctx.user_data['reminder_habit_id'], ctx.user_data['reminder_habit_name'] = habit_id, name
        logger.debug(f"User selected habit '{name}' ({habit_id}) for reminder.")
        await query.edit_message_text(lang.PROMPT_REMINDER_TIME.format(habit_name=name))
        return S_ASK_TIME
    except (IndexError, ValueError): await query.edit_message_text(lang.ERR_GENERIC_CALLBACK)
    except ConnectionError: await query.edit_message_text(lang.ERR_DATABASE_CONNECTION)
    except Exception as e: logger.error(f"Err process reminder habit selection: {e}", exc_info=True); await query.edit_message_text(lang.MSG_ERROR_GENERAL)
    _clear_ctx(ctx); return ConversationHandler.END

async def recv_time_set(update: Update, ctx: CallbackContext) -> int:
    """Receives time, sets job, saves to DB."""
    msg, user = update.effective_message, update.effective_user
    if not msg or not msg.text or not user: return S_ASK_TIME # Should not happen?
    if 'reminder_habit_id' not in ctx.user_data or 'reminder_habit_name' not in ctx.user_data:
        await msg.reply_text(lang.ERR_REMINDER_SET_FAILED_CONTEXT); _clear_ctx(ctx); return ConversationHandler.END

    time_str, name = msg.text.strip(), ctx.user_data['reminder_habit_name']
    parsed_time = helpers.parse_reminder_time(time_str)
    if not parsed_time:
        await msg.reply_text(lang.ERR_REMINDER_INVALID_TIME.format(example=helpers.EXAMPLE_TIME_FORMAT))
        await msg.reply_text(lang.PROMPT_REMINDER_TIME.format(habit_name=name)); return S_ASK_TIME

    jq = cast(JobQueue, ctx.job_queue)
    if not jq: logger.error("JobQueue missing!"); await msg.reply_text(lang.ERR_REMINDER_SET_FAILED_SCHEDULE); _clear_ctx(ctx); return ConversationHandler.END

    habit_id = ctx.user_data['reminder_habit_id']
    job_name = f"{c.JOB_PREFIX_REMINDER}{user.id}_{habit_id}"
    job = None # Define job var scope

    try:
        await _remove_reminder_job(jq, habit_id) # Remove old first
        job = jq.run_daily(callback=reminder_callback, time=parsed_time, name=job_name, chat_id=user.id, user_id=user.id, data={"user_id": user.id, "habit_id": habit_id, "habit_name": name})
        if not job or not job.name: raise RuntimeError("JobQueue.run_daily failed")
        logger.info(f"Scheduled job '{job.name}' h {habit_id} at {parsed_time}")

        if await db_manager.add_or_update_reminder_db(user.id, habit_id, parsed_time, job_name):
            fmt_time = helpers.format_time_user_friendly(parsed_time)
            await msg.reply_text(lang.CONFIRM_REMINDER_SET.format(habit_name=name, time_str=fmt_time))
        else:
            await msg.reply_text(lang.ERR_REMINDER_SET_FAILED_DB)
            logger.warning(f"DB save failed job {job_name}. Removing job."); remove_job_if_exists(job_name, jq)
    except ConnectionError: await msg.reply_text(lang.ERR_DATABASE_CONNECTION); remove_job_if_exists(job_name, jq)
    except Exception as e:
        logger.error(f"Failed scheduling/saving reminder {job_name}: {e}", exc_info=True)
        await msg.reply_text(lang.ERR_REMINDER_SET_FAILED); remove_job_if_exists(job_name, jq)

    _clear_ctx(ctx); return ConversationHandler.END

async def cancel_rem_conv(update: Update, ctx: CallbackContext) -> int:
    """Cancels the set_reminder conversation."""
    return await helpers.cancel_conversation(update, ctx, _clear_ctx, "Set reminder cancelled.")

def set_reminder_conv_handler():
    """Creates the ConversationHandler for setting reminders."""
    return ConversationHandler(
        entry_points=[CommandHandler(c.CMD_SET_REMINDER, ask_habit)],
        states={
            S_SELECT_HABIT: [CallbackQueryHandler(select_habit_cb, pattern=f"^{c.CALLBACK_SELECT_REMINDER_HABIT}")],
            S_ASK_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, recv_time_set)],
        },
        fallbacks=[CommandHandler(c.CMD_CANCEL, cancel_rem_conv)],
        persistent=False, name="set_reminder_conv"
    )

# --- Manage/Delete Reminders ---
async def list_reminders(update: Update, ctx: CallbackContext) -> None:
    """Lists active reminders with delete buttons."""
    msg, user = update.effective_message, update.effective_user
    if not msg or not user: return
    try:
        reminders_db = await db_manager.get_user_reminders(user.id)
        if not reminders_db: await msg.reply_text(lang.MSG_NO_REMINDERS); return
        kbd_data: List[Tuple[int, str, str]] = []
        for hid, rem_time, _ in reminders_db:
            name = await db_manager.get_habit_name_by_id(hid)
            if name: kbd_data.append((hid, name, helpers.format_time_user_friendly(rem_time)))
            else: logger.warning(f"Reminder for deleted habit {hid} (u {user.id}). Skipping.")
        if not kbd_data: await msg.reply_text(lang.MSG_NO_REMINDERS); return
        await msg.reply_text(lang.PROMPT_MANAGE_REMINDERS, reply_markup=keyboards.reminder_management_keyboard(kbd_data))
    except ConnectionError: await msg.reply_text(lang.ERR_DATABASE_CONNECTION)
    except Exception as e: logger.error(f"Err listing reminders: {e}", exc_info=True); await msg.reply_text(lang.MSG_ERROR_GENERAL)

async def delete_reminder_button(update: Update, ctx: CallbackContext) -> None:
    """Handles delete reminder button press."""
    query = update.callback_query; jq = cast(JobQueue, ctx.job_queue)
    if not query or not query.data or not query.message: return
    await query.answer()
    if not jq: logger.error("JobQueue missing"); await query.edit_message_text(lang.ERR_REMINDER_DELETE_FAILED_INTERNAL); return
    try: habit_id = int(query.data.split('_', 1)[1])
    except (ValueError, IndexError, TypeError): await query.edit_message_text(lang.ERR_GENERIC_CALLBACK); return

    try:
        name = await db_manager.get_habit_name_by_id(habit_id) or lang.DEFAULT_HABIT_NAME
        if await _remove_reminder_job(jq, habit_id): await query.edit_message_text(lang.CONFIRM_REMINDER_DELETED.format(habit_name=name))
        else: await query.edit_message_text(lang.ERR_REMINDER_DELETE_FAILED.format(habit_name=name))
    except ConnectionError: await query.edit_message_text(lang.ERR_DATABASE_CONNECTION)
    except Exception as e: logger.error(f"Err deleting reminder: {e}", exc_info=True); await query.edit_message_text(lang.ERR_REMINDER_DELETE_FAILED_INTERNAL)

async def schedule_all_reminders(db: aiosqlite.Connection, jq: JobQueue):
    """Schedules all reminders from DB on bot startup."""
    logger.info("Scheduling reminders from DB...")
    count, skipped, failures = 0, 0, 0
    try:
        reminders = []
        async with db.execute("SELECT user_id, habit_id, reminder_time, job_name FROM Reminders") as cur:
            for uid, hid, rt_str, job_n in await cur.fetchall():
                try: rt = datetime.datetime.strptime(rt_str, '%H:%M:%S').time(); reminders.append((uid, hid, rt, job_n))
                except (ValueError, TypeError): logger.warning(f"Skipping invalid time fmt reminder: {uid, hid, rt_str}")

        for user_id, habit_id, rem_time, stored_job_name in reminders:
            expected_job_name = f"{c.JOB_PREFIX_REMINDER}{user_id}_{habit_id}"
            name = await db_manager.get_habit_name_by_id(habit_id) # Check habit exists
            if not name:
                logger.warning(f"Skipping reminder for deleted habit {habit_id}. Removing orphan."); skipped += 1
                await db.execute("DELETE FROM Reminders WHERE habit_id = ?", (habit_id,)); await db.commit()
                remove_job_if_exists(expected_job_name, jq); remove_job_if_exists(stored_job_name, jq) # Clean both names
                continue
            # Remove existing jobs before scheduling
            remove_job_if_exists(expected_job_name, jq); remove_job_if_exists(stored_job_name, jq)
            try:
                if jq.run_daily(callback=reminder_callback, time=rem_time, name=expected_job_name, chat_id=user_id, user_id=user_id, data={"user_id": user_id, "habit_id": habit_id, "habit_name": name}): count += 1
                else: failures += 1; logger.error(f"Failed reschedule job {expected_job_name} (Job=None).")
            except Exception as e: failures += 1; logger.error(f"Exception scheduling job {expected_job_name}: {e}", exc_info=True)
        logger.info(f"Reminders scheduled: {count}, Skipped: {skipped}, Failures: {failures}")
    except aiosqlite.Error as e: logger.error(f"DB error scheduling reminders: {e}", exc_info=True)
    except Exception as e: logger.error(f"Unexpected error scheduling reminders: {e}", exc_info=True)