import logging
from telegram import Update, InlineKeyboardMarkup
from telegram.ext import CommandHandler, ConversationHandler, CallbackContext, CallbackQueryHandler
from utils import localization as lang, constants as c, keyboards, helpers
from database import db_manager
from .reminders import remove_job_if_exists
from utils.checks import require_membership

logger = logging.getLogger(__name__)
S_ASK_DELETE, S_CONFIRM = c.DELETE_HABIT_STATES

def _clear_ctx(ctx: CallbackContext): ctx.user_data.pop('habit_to_delete_id', None); ctx.user_data.pop('habit_to_delete_name', None)

@require_membership
async def select_habit_delete(update: Update, ctx: CallbackContext) -> int:
    """Entry point: Show list of habits to delete."""
    user, msg = update.effective_user, update.effective_message
    if not user or not msg: return ConversationHandler.END
    try:
        habits = await db_manager.get_user_habits(user.id)
        if not habits: await msg.reply_text(lang.MSG_NO_HABITS_TO_DELETE); return ConversationHandler.END
        kbd = keyboards.select_habit_keyboard(habits, c.CALLBACK_SELECT_HABIT_DELETE)
        await msg.reply_text(lang.PROMPT_SELECT_HABIT_TO_DELETE, reply_markup=InlineKeyboardMarkup(kbd))
        return S_ASK_DELETE
    except ConnectionError: await msg.reply_text(lang.ERR_DATABASE_CONNECTION)
    except Exception as e: logger.error(f"Err fetching habits for deletion: {e}", exc_info=True); await msg.reply_text(lang.MSG_ERROR_GENERAL)
    return ConversationHandler.END

async def ask_confirm(update: Update, ctx: CallbackContext) -> int:
    """Handles selection, asks for confirmation."""
    query = update.callback_query
    if not query or not query.data or not query.message: return ConversationHandler.END
    await query.answer()
    if not query.data.startswith(c.CALLBACK_SELECT_HABIT_DELETE): await query.edit_message_text(lang.ERR_GENERIC_CALLBACK); return ConversationHandler.END

    try:
        habit_id = int(query.data.split('_', 1)[1])
        name = await db_manager.get_habit_name_by_id(habit_id)
        if not name: await query.edit_message_text(lang.ERR_HABIT_NOT_FOUND_GENERIC); return ConversationHandler.END
        ctx.user_data['habit_to_delete_id'], ctx.user_data['habit_to_delete_name'] = habit_id, name
        yes_cb = f"{c.CALLBACK_CONFIRM_DELETE_HABIT}{habit_id}"
        no_cb = c.CALLBACK_CANCEL_DELETE
        await query.edit_message_text(lang.PROMPT_CONFIRM_DELETE.format(habit_name=name), reply_markup=keyboards.yes_no_keyboard(yes_cb, no_cb))
        return S_CONFIRM
    except (IndexError, ValueError): logger.error(f"Could not parse habit_id from cb: {query.data}"); await query.edit_message_text(lang.ERR_GENERIC_CALLBACK)
    except ConnectionError: await query.edit_message_text(lang.ERR_DATABASE_CONNECTION)
    except Exception as e: logger.error(f"Err preparing delete confirm: {e}", exc_info=True); await query.edit_message_text(lang.MSG_ERROR_GENERAL)
    _clear_ctx(ctx); return ConversationHandler.END

async def do_delete(update: Update, ctx: CallbackContext) -> int:
    """Handles 'Yes' confirmation button."""
    query, user, jq = update.callback_query, update.effective_user, ctx.job_queue
    if not query or not query.data or not user or not jq or not ctx.user_data: return ConversationHandler.END # Should not happen
    await query.answer()

    habit_id, name = ctx.user_data.get('habit_to_delete_id'), ctx.user_data.get('habit_to_delete_name', lang.DEFAULT_HABIT_NAME)
    if not query.data.startswith(c.CALLBACK_CONFIRM_DELETE_HABIT): await query.edit_message_text(lang.ERR_GENERIC_CALLBACK); _clear_ctx(ctx); return ConversationHandler.END

    try: cb_habit_id = int(query.data[len(c.CALLBACK_CONFIRM_DELETE_HABIT):])
    except (IndexError, ValueError): await query.edit_message_text(lang.ERR_GENERIC_CALLBACK); _clear_ctx(ctx); return ConversationHandler.END

    if cb_habit_id != habit_id:
        logger.error(f"Mismatch habit_id ({cb_habit_id}) vs context ({habit_id}) in deletion.")
        await query.edit_message_text(lang.ERR_DELETE_FAILED_CONTEXT); _clear_ctx(ctx); return ConversationHandler.END

    if not habit_id: logger.warning("habit_id missing in do_delete"); await query.edit_message_text(lang.ERR_DELETE_FAILED_CONTEXT); _clear_ctx(ctx); return ConversationHandler.END

    try:
        logger.info(f"User {user.id} confirmed delete habit {habit_id} ('{name}')")
        if job_name := await db_manager.remove_reminder_by_habit_id(habit_id):
            if not remove_job_if_exists(job_name, jq): logger.warning(f"Reminder job '{job_name}' for h {habit_id} not in queue.")
        if await db_manager.delete_habit_and_log(habit_id, user.id): await query.edit_message_text(lang.CONFIRM_HABIT_DELETED.format(habit_name=name))
        else: await query.edit_message_text(lang.ERR_DELETE_FAILED_DB.format(habit_name=name))
    except ConnectionError: await query.edit_message_text(lang.ERR_DATABASE_CONNECTION)
    except Exception as e: logger.error(f"Err during habit deletion: {e}", exc_info=True); await query.edit_message_text(lang.ERR_DELETE_FAILED_INTERNAL)
    _clear_ctx(ctx); return ConversationHandler.END

async def cancel_delete(update: Update, ctx: CallbackContext) -> int:
    """Cancels the delete_habit conversation."""
    return await helpers.cancel_conversation(update, ctx, _clear_ctx, "Delete habit cancelled.")

def delete_habit_conv_handler() -> ConversationHandler:
    """Creates the ConversationHandler for deleting habits."""
    return ConversationHandler(
        entry_points=[CommandHandler(c.CMD_DELETE_HABIT, select_habit_delete)],
        states={
            S_ASK_DELETE: [CallbackQueryHandler(ask_confirm, pattern=f"^{c.CALLBACK_SELECT_HABIT_DELETE}")],
            S_CONFIRM: [
                CallbackQueryHandler(do_delete, pattern=f"^{c.CALLBACK_CONFIRM_DELETE_HABIT}"),
                CallbackQueryHandler(cancel_delete, pattern=f"^{c.CALLBACK_CANCEL_DELETE}$") # Handle No button
            ],
        },
        fallbacks=[CommandHandler(c.CMD_CANCEL, cancel_delete), CallbackQueryHandler(cancel_delete, pattern=f"^{c.CALLBACK_CANCEL_DELETE}$")], # Also explicit No
         persistent=False, name="delete_habit_conv"
    )