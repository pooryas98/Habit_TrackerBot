import logging
from telegram import Update, InlineKeyboardMarkup
from telegram.ext import CommandHandler, MessageHandler, filters, ConversationHandler, CallbackContext, CallbackQueryHandler
from utils import localization as lang, constants as c, keyboards, helpers
from database import db_manager
from utils.checks import require_membership

logger = logging.getLogger(__name__)
S_SELECT_HABIT, S_SELECT_FIELD, S_ASK_VALUE, S_CONFIRM = c.EDIT_HABIT_STATES

def _clear_ctx(ctx: CallbackContext):
    for key in ('edit_habit_id', 'edit_habit_name', 'edit_field'): ctx.user_data.pop(key, None)

async def _handle_db_or_general_error(msg_or_query, error):
    text = lang.ERR_DATABASE_CONNECTION if isinstance(error, ConnectionError) else lang.MSG_ERROR_GENERAL
    if hasattr(msg_or_query, 'edit_message_text'): await msg_or_query.edit_message_text(text)
    elif hasattr(msg_or_query, 'reply_text'): await msg_or_query.reply_text(text)

@require_membership
async def start_edit(update: Update, ctx: CallbackContext) -> int:
    """Entry point: Displays habits to choose."""
    user, msg = update.effective_user, update.effective_message
    if not user or not msg: return ConversationHandler.END
    try:
        habits = await db_manager.get_user_habits(user.id)
        if not habits: await msg.reply_text(lang.MSG_NO_HABITS_TO_EDIT); return ConversationHandler.END
        kbd_rows = keyboards.select_habit_keyboard(habits, c.CALLBACK_SELECT_HABIT_EDIT)
        await msg.reply_text(lang.PROMPT_SELECT_HABIT_TO_EDIT, reply_markup=InlineKeyboardMarkup(kbd_rows))
        return S_SELECT_HABIT
    except (ConnectionError, Exception) as e: logger.error(f"Err fetching habits for edit: {e}", exc_info=True); await _handle_db_or_general_error(msg, e)
    return ConversationHandler.END

async def select_field(update: Update, ctx: CallbackContext) -> int:
    """Handles habit selection (button), asks which field to edit."""
    query = update.callback_query
    if not query or not query.data or not query.message or not ctx.user_data: return ConversationHandler.END
    await query.answer()
    try:
        if not query.data.startswith(c.CALLBACK_SELECT_HABIT_EDIT): raise ValueError("Bad CB prefix")
        habit_id = int(query.data.split('_', 1)[1])
        habit_name = await db_manager.get_habit_name_by_id(habit_id)
        if not habit_name: await query.edit_message_text(lang.ERR_HABIT_NOT_FOUND_GENERIC); _clear_ctx(ctx); return ConversationHandler.END

        ctx.user_data['edit_habit_id'] = habit_id; ctx.user_data['edit_habit_name'] = habit_name
        logger.debug(f"User {query.from_user.id} editing '{habit_name}' ({habit_id}).")
        reply_markup = keyboards.edit_habit_field_keyboard(habit_id)
        await query.edit_message_text(lang.PROMPT_SELECT_FIELD_TO_EDIT.format(habit_name=habit_name), reply_markup=reply_markup)
        return S_SELECT_FIELD
    except (IndexError, ValueError, ConnectionError, Exception) as e:
        err_msg = lang.ERR_GENERIC_CALLBACK if isinstance(e, (IndexError, ValueError)) else None
        logger.error(f"Error processing habit selection for edit: {e}", exc_info=True)
        await _handle_db_or_general_error(query, e if not err_msg else err_msg) # Pass specific msg if needed
        _clear_ctx(ctx); return ConversationHandler.END

async def ask_value(update: Update, ctx: CallbackContext) -> int:
    """Handles field selection (button), prompts for new value."""
    query = update.callback_query
    if not query or not query.data or not query.message or not ctx.user_data: return ConversationHandler.END
    await query.answer()
    habit_id, orig_name = ctx.user_data.get('edit_habit_id'), ctx.user_data.get('edit_habit_name', lang.DEFAULT_HABIT_NAME)
    if not habit_id:
        logger.warning("edit_habit_id missing in ask_value"); await query.edit_message_text(lang.ERR_EDIT_FAILED_CONTEXT); _clear_ctx(ctx); return ConversationHandler.END

    try:
        if not query.data.startswith(c.CALLBACK_EDIT_FIELD_PREFIX): raise ValueError("Bad CB prefix")
        prefix_len = len(c.CALLBACK_EDIT_FIELD_PREFIX)
        field, cb_habit_id_str = query.data[prefix_len:].split('_', 1)
        if int(cb_habit_id_str) != habit_id: raise ValueError("Habit ID mismatch")
        if field not in ("name", "description", "category"): await query.edit_message_text(lang.ERR_EDIT_FAILED_INVALID_FIELD); _clear_ctx(ctx); return ConversationHandler.END

        ctx.user_data['edit_field'] = field
        logger.debug(f"User wants to edit field '{field}' for habit {habit_id}")
        prompts = {"name": lang.PROMPT_EDIT_NAME, "description": lang.PROMPT_EDIT_DESCRIPTION, "category": lang.PROMPT_EDIT_CATEGORY}
        await query.edit_message_text(prompts[field].format(habit_name=orig_name))
        return S_ASK_VALUE
    except (IndexError, ValueError, Exception) as e:
        err_msg = lang.ERR_GENERIC_CALLBACK if isinstance(e, (IndexError, ValueError)) else None
        logger.error(f"Error processing field selection for edit: {e}", exc_info=True)
        await _handle_db_or_general_error(query, e if not err_msg else err_msg)
        _clear_ctx(ctx); return ConversationHandler.END

async def save_edit(update: Update, ctx: CallbackContext) -> int:
    """Receives new value, validates, updates DB, ends."""
    msg, user = update.effective_message, update.effective_user
    if not msg or not msg.text or not user or not ctx.user_data: return S_ASK_VALUE # Re-ask if no text
    habit_id, field, orig_name = ctx.user_data.get('edit_habit_id'), ctx.user_data.get('edit_field'), ctx.user_data.get('edit_habit_name', lang.DEFAULT_HABIT_NAME)
    if not habit_id or not field:
        logger.warning("Context missing data in save_edit"); await msg.reply_text(lang.ERR_EDIT_FAILED_CONTEXT); _clear_ctx(ctx); return ConversationHandler.END

    val_raw = msg.text.strip()
    new_val = None if field != "name" and val_raw.lower() in ('/skip', lang.CMD_SKIP.lower()) else val_raw
    if field == "name" and (not new_val or new_val.lower() in ('/skip', lang.CMD_SKIP.lower())):
        await msg.reply_text(lang.ERR_EDIT_FAILED_NAME_EMPTY + "\n" + lang.PROMPT_EDIT_NAME.format(habit_name=orig_name)); return S_ASK_VALUE

    logger.debug(f"Saving edit: h={habit_id}, f='{field}', val='{new_val}'")
    try:
        if await db_manager.update_habit_db(habit_id, user.id, field, new_val):
            final_name = new_val if field == 'name' else orig_name
            await msg.reply_text(lang.CONFIRM_HABIT_UPDATED.format(habit_name=final_name))
        else: await msg.reply_text(lang.ERR_EDIT_FAILED_DB)
    except (ConnectionError, Exception) as e: logger.error(f"Error saving edited habit: {e}", exc_info=True); await _handle_db_or_general_error(msg, e)
    _clear_ctx(ctx); return ConversationHandler.END

async def cancel_edit(update: Update, ctx: CallbackContext) -> int:
    """Cancels the edit_habit conversation."""
    return await helpers.cancel_conversation(update, ctx, _clear_ctx, "Edit habit cancelled.")

def edit_habit_conv_handler() -> ConversationHandler:
    """Creates the ConversationHandler for editing habits."""
    return ConversationHandler(
        entry_points=[CommandHandler(c.CMD_EDIT_HABIT, start_edit)],
        states={
            S_SELECT_HABIT: [CallbackQueryHandler(select_field, pattern=f"^{c.CALLBACK_SELECT_HABIT_EDIT}")],
            S_SELECT_FIELD: [CallbackQueryHandler(ask_value, pattern=f"^{c.CALLBACK_EDIT_FIELD_PREFIX}")],
            S_ASK_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_edit)],
        },
        fallbacks=[ CommandHandler(c.CMD_CANCEL, cancel_edit), CallbackQueryHandler(cancel_edit, pattern=f"^{c.CALLBACK_CANCEL_EDIT}$")],
        persistent=False, name="edit_habit_conv"
    )