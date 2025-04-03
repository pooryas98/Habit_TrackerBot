import logging
from telegram import Update
from telegram.ext import CommandHandler, MessageHandler, filters, ConversationHandler, CallbackContext
from utils import localization as lang, constants as c, helpers
from database import db_manager
from utils.checks import require_membership

logger = logging.getLogger(__name__)
S_NAME, S_DESC, S_CAT = c.ADD_HABIT_STATES

def _clear_ctx(ctx: CallbackContext):
    for key in ('new_habit_name', 'new_habit_description', 'new_habit_category'): ctx.user_data.pop(key, None)

@require_membership
async def ask_name(update: Update, ctx: CallbackContext) -> int:
    """Entry point: asks for habit name."""
    if update.message: await update.message.reply_text(lang.PROMPT_HABIT_NAME); return S_NAME
    return ConversationHandler.END

async def recv_name(update: Update, ctx: CallbackContext) -> int:
    """Stores name, asks for description."""
    if not update.message or not (name := update.message.text.strip()):
        if update.message: await update.message.reply_text(lang.ERR_INVALID_INPUT + "\n" + lang.PROMPT_HABIT_NAME)
        return S_NAME
    ctx.user_data['new_habit_name'] = name
    await update.message.reply_text(lang.PROMPT_HABIT_DESCRIPTION.format(habit_name=name))
    return S_DESC

async def recv_desc(update: Update, ctx: CallbackContext) -> int:
    """Stores description (optional), asks for category."""
    if not update.message or not (desc := update.message.text.strip()): return S_DESC # Should not happen with filter?
    ctx.user_data['new_habit_description'] = None if desc.lower() in ('/skip', lang.CMD_SKIP.lower()) else desc
    name = ctx.user_data.get('new_habit_name', lang.DEFAULT_HABIT_NAME)
    await update.message.reply_text(lang.PROMPT_HABIT_CATEGORY.format(habit_name=name))
    return S_CAT

async def recv_cat_save(update: Update, ctx: CallbackContext) -> int:
    """Stores category (optional), saves habit to DB."""
    msg, user = update.effective_message, update.effective_user
    if not msg or not msg.text or not user or not ctx.user_data or 'new_habit_name' not in ctx.user_data:
        logger.warning("User data missing or invalid in recv_cat_save")
        if msg: await msg.reply_text(lang.ERR_HABIT_ADD_FAILED_CONTEXT if ctx.user_data else lang.ERR_HABIT_ADD_FAILED_USER)
        _clear_ctx(ctx); return ConversationHandler.END

    cat = msg.text.strip()
    ctx.user_data['new_habit_category'] = None if cat.lower() in ('/skip', lang.CMD_SKIP.lower()) else cat
    name, desc, cat_val = ctx.user_data['new_habit_name'], ctx.user_data.get('new_habit_description'), ctx.user_data.get('new_habit_category')

    try:
        if await db_manager.add_habit_db(user.id, name, desc, cat_val): await msg.reply_text(lang.CONFIRM_HABIT_ADDED.format(habit_name=name))
        else: await msg.reply_text(lang.ERR_HABIT_ADD_FAILED)
    except ConnectionError: await msg.reply_text(lang.ERR_DATABASE_CONNECTION)
    except Exception as e: logger.error(f"Error saving habit: {e}", exc_info=True); await msg.reply_text(lang.ERR_HABIT_ADD_FAILED)
    _clear_ctx(ctx); return ConversationHandler.END

async def cancel_add(update: Update, ctx: CallbackContext) -> int:
    """Cancels the add_habit conversation."""
    return await helpers.cancel_conversation(update, ctx, _clear_ctx, "Add habit cancelled.")

def add_habit_conv_handler() -> ConversationHandler:
    """Creates the ConversationHandler for adding habits."""
    skip_filter = filters.Regex(f'^({lang.CMD_SKIP}|/skip)$')
    return ConversationHandler(
        entry_points=[CommandHandler(c.CMD_ADD_HABIT, ask_name)],
        states={
            S_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, recv_name)],
            S_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND | skip_filter, recv_desc)],
            S_CAT: [MessageHandler(filters.TEXT & ~filters.COMMAND | skip_filter, recv_cat_save)],
        },
        fallbacks=[CommandHandler(c.CMD_CANCEL, cancel_add)],
        persistent=False, name="add_habit_conv"
    )