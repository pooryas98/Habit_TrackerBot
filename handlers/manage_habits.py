# handlers/manage_habits.py

import logging
from telegram import Update, InlineKeyboardMarkup
from telegram.ext import (
    CommandHandler, ConversationHandler, CallbackContext, CallbackQueryHandler, MessageHandler, filters
)
from typing import List, Tuple

from utils import localization as lang
from utils import constants as c
from utils import keyboards
from database import db_manager
from .reminders import remove_job_if_exists
# --- Add imports ---
from utils.checks import require_membership
# --- End imports ---

logger = logging.getLogger(__name__)

# States
ASK_HABIT_TO_DELETE, CONFIRM_DELETE = c.DELETE_HABIT_STATES

# --- Apply decorator ---
@require_membership
async def select_habit_to_delete(update: Update, context: CallbackContext) -> int:
    """Starts the conversation to delete a habit. Shows a list of habits."""
    # Decorator handles membership check
    user = update.effective_user
    if not user: return ConversationHandler.END # Should not happen if decorator worked
    if not update.message: return ConversationHandler.END

    try:
        user_habits = await db_manager.get_user_habits(user.id)

        if not user_habits:
            await update.message.reply_text(lang.MSG_NO_HABITS_TO_DELETE)
            return ConversationHandler.END

        keyboard = keyboards.select_habit_keyboard(user_habits, c.CALLBACK_SELECT_HABIT_DELETE)
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(lang.PROMPT_SELECT_HABIT_TO_DELETE, reply_markup=reply_markup)
        return ASK_HABIT_TO_DELETE

    except ConnectionError:
        logger.error("Database connection unavailable for select_habit_to_delete")
        await update.message.reply_text(lang.ERR_DATABASE_CONNECTION)
        return ConversationHandler.END
    except Exception as e:
         logger.error(f"Error fetching habits for deletion list: {e}", exc_info=True)
         await update.message.reply_text(lang.MSG_ERROR_GENERAL)
         return ConversationHandler.END
# --- End decorator application ---


async def ask_confirm_delete(update: Update, context: CallbackContext) -> int:
    """Handles selection from the inline keyboard and asks for confirmation."""
    query = update.callback_query
    if not query: return ConversationHandler.END
    await query.answer()

    if not query.data or not query.data.startswith(c.CALLBACK_SELECT_HABIT_DELETE):
        logger.warning(f"Invalid callback data in delete habit flow: {query.data}")
        await query.edit_message_text(lang.ERR_GENERIC_CALLBACK)
        return ConversationHandler.END

    try:
        habit_id = int(query.data.split('_', 1)[1])
        habit_name = await db_manager.get_habit_name_by_id(habit_id)
        if not habit_name:
            logger.warning(f"Habit {habit_id} selected for deletion not found.")
            await query.edit_message_text(lang.ERR_HABIT_NOT_FOUND_GENERIC)
            return ConversationHandler.END

        context.user_data['habit_to_delete_id'] = habit_id
        context.user_data['habit_to_delete_name'] = habit_name

        reply_markup = keyboards.yes_no_keyboard(
            yes_callback=f"{c.CALLBACK_CONFIRM_DELETE_HABIT}{habit_id}",
            no_callback=c.CALLBACK_CANCEL_DELETE
        )

        await query.edit_message_text(
            lang.PROMPT_CONFIRM_DELETE.format(habit_name=habit_name),
            reply_markup=reply_markup
        )
        return CONFIRM_DELETE

    except (IndexError, ValueError):
        logger.error(f"Could not parse habit_id from callback data: {query.data}", exc_info=True)
        await query.edit_message_text(lang.ERR_GENERIC_CALLBACK)
        return ConversationHandler.END
    except ConnectionError:
        logger.error("Database connection unavailable for ask_confirm_delete")
        await query.edit_message_text(lang.ERR_DATABASE_CONNECTION)
        return ConversationHandler.END
    except Exception as e:
         logger.error(f"Error preparing delete confirmation: {e}", exc_info=True)
         await query.edit_message_text(lang.MSG_ERROR_GENERAL)
         return ConversationHandler.END


async def perform_delete(update: Update, context: CallbackContext) -> int:
    """Handles the 'Yes' confirmation button press."""
    query = update.callback_query
    if not query: return ConversationHandler.END
    await query.answer()

    habit_id = context.user_data.get('habit_to_delete_id')
    habit_name = context.user_data.get('habit_to_delete_name', lang.DEFAULT_HABIT_NAME)
    user = query.from_user
    job_queue = context.job_queue

    if not query.data or not query.data.startswith(c.CALLBACK_CONFIRM_DELETE_HABIT):
         logger.warning(f"Invalid callback data in delete confirmation: {query.data}")
         await query.edit_message_text(lang.ERR_GENERIC_CALLBACK)
         _clear_delete_context(context)
         return ConversationHandler.END

    try:
        callback_habit_id = int(query.data[len(c.CALLBACK_CONFIRM_DELETE_HABIT):])
        if callback_habit_id != habit_id:
            logger.error(f"Mismatch between callback habit_id ({callback_habit_id}) and context ({habit_id}) during deletion.")
            await query.edit_message_text(lang.ERR_DELETE_FAILED_CONTEXT)
            _clear_delete_context(context)
            return ConversationHandler.END
    except (IndexError, ValueError):
         logger.error(f"Could not parse habit_id from delete confirmation callback: {query.data}", exc_info=True)
         await query.edit_message_text(lang.ERR_GENERIC_CALLBACK)
         _clear_delete_context(context)
         return ConversationHandler.END

    if not habit_id or not job_queue:
        logger.warning(f"Context missing habit_id ({not habit_id}) or job_queue ({not job_queue}) in perform_delete.")
        await query.edit_message_text(lang.ERR_DELETE_FAILED_CONTEXT if not habit_id else lang.ERR_DELETE_FAILED_INTERNAL)
        _clear_delete_context(context)
        return ConversationHandler.END

    try:
        logger.info(f"User {user.id} confirmed deletion of habit {habit_id} ('{habit_name}')")
        job_name_to_remove = await db_manager.remove_reminder_by_habit_id(habit_id)
        job_removed = False
        if job_name_to_remove:
            job_removed = remove_job_if_exists(job_name_to_remove, job_queue)
            if not job_removed:
                 logger.warning(f"Reminder for habit {habit_id} had job_name '{job_name_to_remove}' in DB, but job was not found in queue.")

        deleted_from_db = await db_manager.delete_habit_and_log(habit_id, user.id)

        if deleted_from_db:
            await query.edit_message_text(lang.CONFIRM_HABIT_DELETED.format(habit_name=habit_name))
        else:
            logger.error(f"Failed to delete habit {habit_id} from DB for user {user.id} in final step.")
            await query.edit_message_text(lang.ERR_DELETE_FAILED_DB.format(habit_name=habit_name))

    except ConnectionError:
         logger.error("Database connection unavailable for perform_delete")
         await query.edit_message_text(lang.ERR_DATABASE_CONNECTION)
    except Exception as e:
         logger.error(f"Error during habit deletion process: {e}", exc_info=True)
         await query.edit_message_text(lang.ERR_DELETE_FAILED_INTERNAL)

    _clear_delete_context(context)
    return ConversationHandler.END


async def cancel_delete(update: Update, context: CallbackContext) -> int:
    """Handles 'No' button press or /cancel command."""
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

    logger.debug(f"Delete habit conversation cancelled by user {update.effective_user.id if update.effective_user else 'Unknown'}")
    _clear_delete_context(context)
    return ConversationHandler.END

def _clear_delete_context(context: CallbackContext):
    """Helper to clear user_data for this conversation."""
    context.user_data.pop('habit_to_delete_id', None)
    context.user_data.pop('habit_to_delete_name', None)

# --- Use decorated function in entry_points ---
def delete_habit_conv_handler() -> ConversationHandler:
    """Creates the ConversationHandler for deleting habits."""
    # select_habit_to_delete is already decorated
    return ConversationHandler(
        entry_points=[CommandHandler(c.CMD_DELETE_HABIT, select_habit_to_delete)], # Use original name
        states={
            ASK_HABIT_TO_DELETE: [CallbackQueryHandler(ask_confirm_delete, pattern=f"^{c.CALLBACK_SELECT_HABIT_DELETE}")],
            CONFIRM_DELETE: [
                CallbackQueryHandler(perform_delete, pattern=f"^{c.CALLBACK_CONFIRM_DELETE_HABIT}"),
                CallbackQueryHandler(cancel_delete, pattern=f"^{c.CALLBACK_CANCEL_DELETE}$")
            ],
        },
        fallbacks=[
            CommandHandler(c.CMD_CANCEL, cancel_delete),
            CallbackQueryHandler(cancel_delete, pattern=f"^{c.CALLBACK_CANCEL_DELETE}$")
            ],
         persistent=False,
         name="delete_habit_conversation"
    )
# --- End change ---