import logging
from telegram import Update, InlineKeyboardMarkup
from telegram.ext import (
    CommandHandler, MessageHandler, filters, ConversationHandler, CallbackContext, CallbackQueryHandler
)
from typing import Optional
from utils import localization as lang, constants as c, keyboards, helpers
from database import db_manager
from utils.checks import require_membership
from utils.helpers import cancel_conversation # Import generic cancel helper

logger = logging.getLogger(__name__)

# States
SELECT_HABIT_TO_EDIT, SELECT_FIELD_TO_EDIT, ASK_NEW_VALUE, CONFIRM_EDIT_SAVE = c.EDIT_HABIT_STATES

@require_membership
async def start_edit_habit(update: Update, context: CallbackContext) -> int:
    """Starts edit habit conversation: displays habits to choose."""
    user = update.effective_user
    message = update.effective_message
    if not user or not message: return ConversationHandler.END

    try:
        user_habits = await db_manager.get_user_habits(user.id)
        if not user_habits:
            await message.reply_text(lang.MSG_NO_HABITS_TO_EDIT)
            return ConversationHandler.END

        keyboard_rows = keyboards.select_habit_keyboard(user_habits, c.CALLBACK_SELECT_HABIT_EDIT)
        reply_markup = InlineKeyboardMarkup(keyboard_rows)
        await message.reply_text(lang.PROMPT_SELECT_HABIT_TO_EDIT, reply_markup=reply_markup)
        return SELECT_HABIT_TO_EDIT
    except ConnectionError:
        logger.error("DB connection unavailable for start_edit_habit")
        await message.reply_text(lang.ERR_DATABASE_CONNECTION)
    except Exception as e:
        logger.error(f"Error fetching habits for edit list: {e}", exc_info=True)
        await message.reply_text(lang.MSG_ERROR_GENERAL)
    return ConversationHandler.END

async def select_field_to_edit(update: Update, context: CallbackContext) -> int:
    """Handles habit selection (button), asks which field to edit."""
    query = update.callback_query
    if not query or not query.message or not context.user_data: return ConversationHandler.END
    await query.answer()

    try:
        if not query.data or not query.data.startswith(c.CALLBACK_SELECT_HABIT_EDIT):
            raise ValueError(f"Invalid callback prefix: {query.data}")
        habit_id = int(query.data.split('_', 1)[1])

        habit_name = await db_manager.get_habit_name_by_id(habit_id)
        if not habit_name:
            await query.edit_message_text(lang.ERR_HABIT_NOT_FOUND_GENERIC)
            _clear_edit_context(context)
            return ConversationHandler.END

        context.user_data['edit_habit_id'] = habit_id
        context.user_data['edit_habit_name'] = habit_name
        logger.debug(f"User {query.from_user.id} selected habit '{habit_name}' (ID: {habit_id}) for editing.")

        reply_markup = keyboards.edit_habit_field_keyboard(habit_id)
        await query.edit_message_text(lang.PROMPT_SELECT_FIELD_TO_EDIT.format(habit_name=habit_name), reply_markup=reply_markup)
        return SELECT_FIELD_TO_EDIT
    except (IndexError, ValueError):
        logger.error(f"Could not parse habit_id from edit selection cb: {query.data}", exc_info=True)
        await query.edit_message_text(lang.ERR_GENERIC_CALLBACK)
    except ConnectionError:
        await query.edit_message_text(lang.ERR_DATABASE_CONNECTION)
    except Exception as e:
        logger.error(f"Error processing habit selection for edit: {e}", exc_info=True)
        await query.edit_message_text(lang.MSG_ERROR_GENERAL)
    _clear_edit_context(context)
    return ConversationHandler.END

async def ask_new_value(update: Update, context: CallbackContext) -> int:
    """Handles field selection (button), prompts for new value."""
    query = update.callback_query
    if not query or not query.message or not context.user_data: return ConversationHandler.END
    await query.answer()

    habit_id = context.user_data.get('edit_habit_id')
    habit_name = context.user_data.get('edit_habit_name', lang.DEFAULT_HABIT_NAME)
    if not habit_id:
        logger.warning("edit_habit_id missing from context in ask_new_value")
        await query.edit_message_text(lang.ERR_EDIT_FAILED_CONTEXT)
        _clear_edit_context(context)
        return ConversationHandler.END

    try:
        if not query.data or not query.data.startswith(c.CALLBACK_EDIT_FIELD_PREFIX):
            raise ValueError(f"Invalid callback prefix: {query.data}")

        parts = query.data[len(c.CALLBACK_EDIT_FIELD_PREFIX):].split('_', 1)
        field_to_edit = parts[0]
        callback_habit_id = int(parts[1])

        if callback_habit_id != habit_id:
            logger.error(f"Habit ID mismatch in edit cb: context={habit_id}, callback={callback_habit_id}")
            await query.edit_message_text(lang.ERR_EDIT_FAILED_CONTEXT)
            _clear_edit_context(context)
            return ConversationHandler.END

        if field_to_edit not in ["name", "description", "category"]:
            await query.edit_message_text(lang.ERR_EDIT_FAILED_INVALID_FIELD)
            _clear_edit_context(context)
            return ConversationHandler.END

        context.user_data['edit_field'] = field_to_edit
        logger.debug(f"User wants to edit field '{field_to_edit}' for habit {habit_id}")

        prompt_text = ""
        if field_to_edit == "name": prompt_text = lang.PROMPT_EDIT_NAME.format(habit_name=habit_name)
        elif field_to_edit == "description": prompt_text = lang.PROMPT_EDIT_DESCRIPTION.format(habit_name=habit_name)
        elif field_to_edit == "category": prompt_text = lang.PROMPT_EDIT_CATEGORY.format(habit_name=habit_name)

        await query.edit_message_text(prompt_text)
        return ASK_NEW_VALUE
    except (IndexError, ValueError):
        logger.error(f"Could not parse field/habit_id from edit field cb: {query.data}", exc_info=True)
        await query.edit_message_text(lang.ERR_GENERIC_CALLBACK)
    except Exception as e:
        logger.error(f"Error processing field selection for edit: {e}", exc_info=True)
        await query.edit_message_text(lang.MSG_ERROR_GENERAL)
    _clear_edit_context(context)
    return ConversationHandler.END

async def save_edited_habit(update: Update, context: CallbackContext) -> int:
    """Receives new value, validates, updates DB, ends conversation."""
    message = update.effective_message
    user = update.effective_user
    if not message or not message.text or not user or not context.user_data: return ASK_NEW_VALUE

    habit_id = context.user_data.get('edit_habit_id')
    field = context.user_data.get('edit_field')
    original_habit_name = context.user_data.get('edit_habit_name', lang.DEFAULT_HABIT_NAME)

    if not habit_id or not field:
        logger.warning("Context missing habit_id or field in save_edited_habit")
        await message.reply_text(lang.ERR_EDIT_FAILED_CONTEXT)
        _clear_edit_context(context)
        return ConversationHandler.END

    new_value_raw = message.text.strip()
    new_value: Optional[str] = None

    if field in ["description", "category"] and new_value_raw.lower() in ['/skip', lang.CMD_SKIP.lower()]:
        new_value = None
    else:
        new_value = new_value_raw
        if field == "name" and (not new_value or new_value.lower() in ['/skip', lang.CMD_SKIP.lower()]):
            await message.reply_text(lang.ERR_EDIT_FAILED_NAME_EMPTY)
            await message.reply_text(lang.PROMPT_EDIT_NAME.format(habit_name=original_habit_name))
            return ASK_NEW_VALUE

    logger.debug(f"Saving edit: habit_id={habit_id}, field='{field}', new_value='{new_value}'")
    try:
        success = await db_manager.update_habit_db(habit_id, user.id, field, new_value)
        if success:
            final_habit_name = new_value if field == 'name' else original_habit_name
            await message.reply_text(lang.CONFIRM_HABIT_UPDATED.format(habit_name=final_habit_name))
        else:
            await message.reply_text(lang.ERR_EDIT_FAILED_DB)
    except ConnectionError:
        await message.reply_text(lang.ERR_DATABASE_CONNECTION)
    except Exception as e:
         logger.error(f"Error saving edited habit: {e}", exc_info=True)
         await message.reply_text(lang.ERR_EDIT_FAILED_DB)

    _clear_edit_context(context)
    return ConversationHandler.END

def _clear_edit_context(context: CallbackContext):
    """Clears user_data for this conversation."""
    context.user_data.pop('edit_habit_id', None)
    context.user_data.pop('edit_habit_name', None)
    context.user_data.pop('edit_field', None)

async def cancel_edit(update: Update, context: CallbackContext) -> int:
    """Cancels the edit_habit conversation using the generic helper."""
    return await cancel_conversation(
        update,
        context,
        clear_context_func=_clear_edit_context,
        log_message="Edit habit conversation cancelled."
    )

def edit_habit_conv_handler() -> ConversationHandler:
    """Creates the ConversationHandler for editing habits."""
    return ConversationHandler(
        entry_points=[CommandHandler(c.CMD_EDIT_HABIT, start_edit_habit)],
        states={
            SELECT_HABIT_TO_EDIT: [CallbackQueryHandler(select_field_to_edit, pattern=f"^{c.CALLBACK_SELECT_HABIT_EDIT}")],
            SELECT_FIELD_TO_EDIT: [CallbackQueryHandler(ask_new_value, pattern=f"^{c.CALLBACK_EDIT_FIELD_PREFIX}")],
            ASK_NEW_VALUE: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_edited_habit)],
        },
        fallbacks=[
            CommandHandler(c.CMD_CANCEL, cancel_edit), # Use updated cancel_edit
            CallbackQueryHandler(cancel_edit, pattern=f"^{c.CALLBACK_CANCEL_EDIT}$") # Use updated cancel_edit
        ],
        persistent=False,
        name="edit_habit_conversation"
    )