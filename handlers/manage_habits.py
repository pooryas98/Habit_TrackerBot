import logging
from telegram import Update, InlineKeyboardMarkup
from telegram.ext import (
    CommandHandler, ConversationHandler, CallbackContext, CallbackQueryHandler
)
from utils import localization as lang, constants as c, keyboards
from database import db_manager
from .reminders import remove_job_if_exists
from utils.checks import require_membership
from utils.helpers import cancel_conversation # Import generic cancel helper

logger = logging.getLogger(__name__)

# States
ASK_HABIT_TO_DELETE, CONFIRM_DELETE = c.DELETE_HABIT_STATES

@require_membership
async def select_habit_to_delete(update: Update, context: CallbackContext) -> int:
    """Starts conversation to delete a habit. Shows list."""
    user = update.effective_user
    if not user or not update.message: return ConversationHandler.END

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
        await update.message.reply_text(lang.ERR_DATABASE_CONNECTION)
    except Exception as e:
         logger.error(f"Error fetching habits for deletion: {e}", exc_info=True)
         await update.message.reply_text(lang.MSG_ERROR_GENERAL)
    return ConversationHandler.END

async def ask_confirm_delete(update: Update, context: CallbackContext) -> int:
    """Handles selection from keyboard, asks for confirmation."""
    query = update.callback_query
    if not query: return ConversationHandler.END
    await query.answer()

    if not query.data or not query.data.startswith(c.CALLBACK_SELECT_HABIT_DELETE):
        await query.edit_message_text(lang.ERR_GENERIC_CALLBACK)
        return ConversationHandler.END

    try:
        habit_id = int(query.data.split('_', 1)[1])
        habit_name = await db_manager.get_habit_name_by_id(habit_id)
        if not habit_name:
            await query.edit_message_text(lang.ERR_HABIT_NOT_FOUND_GENERIC)
            return ConversationHandler.END

        context.user_data['habit_to_delete_id'] = habit_id
        context.user_data['habit_to_delete_name'] = habit_name

        reply_markup = keyboards.yes_no_keyboard(
            yes_cb=f"{c.CALLBACK_CONFIRM_DELETE_HABIT}{habit_id}", # Use yes_cb
            no_cb=c.CALLBACK_CANCEL_DELETE                       # Use no_cb
        )
        await query.edit_message_text(lang.PROMPT_CONFIRM_DELETE.format(habit_name=habit_name), reply_markup=reply_markup)
        return CONFIRM_DELETE
    except (IndexError, ValueError):
        logger.error(f"Could not parse habit_id from cb: {query.data}", exc_info=True)
        await query.edit_message_text(lang.ERR_GENERIC_CALLBACK)
    except ConnectionError:
        await query.edit_message_text(lang.ERR_DATABASE_CONNECTION)
    except Exception as e:
         logger.error(f"Error preparing delete confirmation: {e}", exc_info=True)
         await query.edit_message_text(lang.MSG_ERROR_GENERAL)
    _clear_delete_context(context)
    return ConversationHandler.END

async def perform_delete(update: Update, context: CallbackContext) -> int:
    """Handles 'Yes' confirmation button."""
    query = update.callback_query
    if not query: return ConversationHandler.END
    await query.answer()

    habit_id = context.user_data.get('habit_to_delete_id')
    habit_name = context.user_data.get('habit_to_delete_name', lang.DEFAULT_HABIT_NAME)
    user = query.from_user
    job_queue = context.job_queue

    if not query.data or not query.data.startswith(c.CALLBACK_CONFIRM_DELETE_HABIT):
         await query.edit_message_text(lang.ERR_GENERIC_CALLBACK)
         _clear_delete_context(context)
         return ConversationHandler.END

    try:
        callback_habit_id = int(query.data[len(c.CALLBACK_CONFIRM_DELETE_HABIT):])
        if callback_habit_id != habit_id:
            logger.error(f"Mismatch habit_id ({callback_habit_id}) vs context ({habit_id}) during deletion.")
            await query.edit_message_text(lang.ERR_DELETE_FAILED_CONTEXT)
            _clear_delete_context(context)
            return ConversationHandler.END
    except (IndexError, ValueError):
         await query.edit_message_text(lang.ERR_GENERIC_CALLBACK)
         _clear_delete_context(context)
         return ConversationHandler.END

    if not habit_id or not job_queue:
        logger.warning(f"Context missing habit_id or job_queue in perform_delete.")
        await query.edit_message_text(lang.ERR_DELETE_FAILED_CONTEXT if not habit_id else lang.ERR_DELETE_FAILED_INTERNAL)
        _clear_delete_context(context)
        return ConversationHandler.END

    try:
        logger.info(f"User {user.id} confirmed deletion of habit {habit_id} ('{habit_name}')")
        job_name_to_remove = await db_manager.remove_reminder_by_habit_id(habit_id)
        if job_name_to_remove:
            if not remove_job_if_exists(job_name_to_remove, job_queue):
                 logger.warning(f"Reminder job '{job_name_to_remove}' for habit {habit_id} not found in queue.")

        deleted_from_db = await db_manager.delete_habit_and_log(habit_id, user.id)
        if deleted_from_db:
            await query.edit_message_text(lang.CONFIRM_HABIT_DELETED.format(habit_name=habit_name))
        else:
            await query.edit_message_text(lang.ERR_DELETE_FAILED_DB.format(habit_name=habit_name))
    except ConnectionError:
         await query.edit_message_text(lang.ERR_DATABASE_CONNECTION)
    except Exception as e:
         logger.error(f"Error during habit deletion: {e}", exc_info=True)
         await query.edit_message_text(lang.ERR_DELETE_FAILED_INTERNAL)

    _clear_delete_context(context)
    return ConversationHandler.END

def _clear_delete_context(context: CallbackContext):
    """Clears user_data for this conversation."""
    context.user_data.pop('habit_to_delete_id', None)
    context.user_data.pop('habit_to_delete_name', None)

async def cancel_delete(update: Update, context: CallbackContext) -> int:
    """Cancels the delete_habit conversation using the generic helper."""
    return await cancel_conversation(
        update,
        context,
        clear_context_func=_clear_delete_context,
        log_message="Delete habit conversation cancelled."
    )

def delete_habit_conv_handler() -> ConversationHandler:
    """Creates the ConversationHandler for deleting habits."""
    return ConversationHandler(
        entry_points=[CommandHandler(c.CMD_DELETE_HABIT, select_habit_to_delete)],
        states={
            ASK_HABIT_TO_DELETE: [CallbackQueryHandler(ask_confirm_delete, pattern=f"^{c.CALLBACK_SELECT_HABIT_DELETE}")],
            CONFIRM_DELETE: [
                CallbackQueryHandler(perform_delete, pattern=f"^{c.CALLBACK_CONFIRM_DELETE_HABIT}"),
                CallbackQueryHandler(cancel_delete, pattern=f"^{c.CALLBACK_CANCEL_DELETE}$") # Use updated cancel_delete
            ],
        },
        fallbacks=[
            CommandHandler(c.CMD_CANCEL, cancel_delete), # Use updated cancel_delete
            CallbackQueryHandler(cancel_delete, pattern=f"^{c.CALLBACK_CANCEL_DELETE}$") # Also for the explicit 'No' button
            ],
         persistent=False,
         name="delete_habit_conversation"
    )