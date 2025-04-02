import logging
from telegram import Update
from telegram.ext import (
    CommandHandler, MessageHandler, filters, ConversationHandler, CallbackContext
)
from utils import localization as lang, constants as c
from database import db_manager
from utils.checks import require_membership
from utils.helpers import cancel_conversation # Import generic cancel helper

logger = logging.getLogger(__name__)

# States
ASK_NAME, ASK_DESCRIPTION, ASK_CATEGORY = c.ADD_HABIT_STATES

@require_membership
async def ask_habit_name(update: Update, context: CallbackContext) -> int:
    """Starts conversation: asks for habit name."""
    if not update.message: return ConversationHandler.END
    await update.message.reply_text(lang.PROMPT_HABIT_NAME)
    return ASK_NAME

async def receive_habit_name(update: Update, context: CallbackContext) -> int:
    """Stores name, asks for description."""
    if not update.message or not update.message.text: return ASK_NAME
    habit_name = update.message.text.strip()
    if not habit_name:
        await update.message.reply_text(lang.ERR_INVALID_INPUT + "\n" + lang.PROMPT_HABIT_NAME)
        return ASK_NAME

    context.user_data['new_habit_name'] = habit_name
    await update.message.reply_text(lang.PROMPT_HABIT_DESCRIPTION.format(habit_name=habit_name))
    return ASK_DESCRIPTION

async def receive_habit_description(update: Update, context: CallbackContext) -> int:
    """Stores description (optional), asks for category."""
    if not update.message or not update.message.text: return ASK_DESCRIPTION
    description = update.message.text.strip()
    if description.lower() in ['/skip', lang.CMD_SKIP.lower()]:
        context.user_data['new_habit_description'] = None
    else:
        context.user_data['new_habit_description'] = description

    habit_name = context.user_data.get('new_habit_name', lang.DEFAULT_HABIT_NAME)
    await update.message.reply_text(lang.PROMPT_HABIT_CATEGORY.format(habit_name=habit_name))
    return ASK_CATEGORY

async def receive_habit_category_and_save(update: Update, context: CallbackContext) -> int:
    """Stores category (optional), saves habit to DB."""
    if not update.message or not update.message.text: return ASK_CATEGORY
    if not context.user_data or 'new_habit_name' not in context.user_data:
         logger.warning("User data missing 'new_habit_name' in final step.")
         await update.message.reply_text(lang.ERR_HABIT_ADD_FAILED_CONTEXT)
         return ConversationHandler.END

    category = update.message.text.strip()
    if category.lower() in ['/skip', lang.CMD_SKIP.lower()]:
        context.user_data['new_habit_category'] = None
    else:
        context.user_data['new_habit_category'] = category

    user = update.effective_user
    if not user:
        logger.warning("No effective user found in receive_habit_category_and_save")
        await update.message.reply_text(lang.ERR_HABIT_ADD_FAILED_USER)
        return ConversationHandler.END

    name = context.user_data['new_habit_name']
    description = context.user_data.get('new_habit_description')
    category_val = context.user_data.get('new_habit_category')

    try:
        habit_id = await db_manager.add_habit_db(user.id, name, description, category_val)
        if habit_id:
            await update.message.reply_text(lang.CONFIRM_HABIT_ADDED.format(habit_name=name))
        else:
            await update.message.reply_text(lang.ERR_HABIT_ADD_FAILED)
    except ConnectionError:
        logger.error("DB connection unavailable for add_habit")
        await update.message.reply_text(lang.ERR_DATABASE_CONNECTION)
    except Exception as e:
         logger.error(f"Error saving habit: {e}", exc_info=True)
         await update.message.reply_text(lang.ERR_HABIT_ADD_FAILED)

    _clear_add_habit_context(context)
    return ConversationHandler.END

def _clear_add_habit_context(context: CallbackContext):
    """Clears user_data for this conversation."""
    context.user_data.pop('new_habit_name', None)
    context.user_data.pop('new_habit_description', None)
    context.user_data.pop('new_habit_category', None)

async def cancel(update: Update, context: CallbackContext) -> int:
    """Cancels the add_habit conversation using the generic helper."""
    return await cancel_conversation(
        update,
        context,
        clear_context_func=_clear_add_habit_context,
        log_message="Add habit conversation cancelled."
    )

def add_habit_conv_handler() -> ConversationHandler:
    """Creates the ConversationHandler for adding habits."""
    return ConversationHandler(
        entry_points=[CommandHandler(c.CMD_ADD_HABIT, ask_habit_name)],
        states={
            ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_habit_name)],
            ASK_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND | filters.Regex(f'^({lang.CMD_SKIP}|/skip)$'), receive_habit_description)],
            ASK_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND | filters.Regex(f'^({lang.CMD_SKIP}|/skip)$'), receive_habit_category_and_save)],
        },
        fallbacks=[CommandHandler(c.CMD_CANCEL, cancel)], # Use the updated cancel
        persistent=False,
        name="add_habit_conversation"
    )