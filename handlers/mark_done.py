from telegram import Update, error as tg_error, InlineKeyboardMarkup
from telegram.ext import CallbackContext
import logging
from typing import Tuple, Optional
from utils import localization as lang, helpers, keyboards, constants as c
from database import db_manager
from .view_habits import _generate_today_message # For refresh

logger = logging.getLogger(__name__)

async def _perform_mark_done(user_id: int, habit_id: int) -> Tuple[str, Optional[str]]:
    """Core logic: marks done in DB. Returns status ('success', 'already_done', 'not_found', 'error') & name."""
    try:
        name = await db_manager.get_habit_name_by_id(habit_id)
        if not name: logger.warning(f"_perform_mark_done: H {habit_id} not found u {user_id}."); return "not_found", None
        result = await db_manager.mark_habit_done_db(user_id, habit_id, helpers.get_today_date())
        return result, name
    except ConnectionError: return "error", None
    except Exception as e: logger.error(f"Err in _perform_mark_done h {habit_id}: {e}", exc_info=True); return "error", None

async def mark_done_command(update: Update, ctx: CallbackContext) -> None:
    """Handles /done [name] or /done (shows keyboard)."""
    user, msg = update.effective_user, update.effective_message
    if not user or not msg: return

    if ctx.args:
        query_name = " ".join(ctx.args).strip()
        try:
            habit_info = await db_manager.find_habit_by_name(user.id, query_name)
            if not habit_info: await msg.reply_text(lang.ERR_HABIT_NOT_FOUND.format(habit_name=helpers.escape_html(query_name))); return
            habit_id, _ = habit_info
            result, name = await _perform_mark_done(user.id, habit_id)
            safe_name = helpers.escape_html(name or query_name)
            responses = {"success": lang.CONFIRM_HABIT_MARKED_DONE, "already_done": lang.ERR_HABIT_ALREADY_DONE}
            await msg.reply_text(responses.get(result, lang.ERR_MARK_DONE_FAILED).format(habit_name=safe_name))
        except ConnectionError: await msg.reply_text(lang.ERR_DATABASE_CONNECTION)
        except Exception as e: logger.error(f"Err in /done name lookup: {e}", exc_info=True); await msg.reply_text(lang.ERR_MARK_DONE_FAILED)
    else: # No args, show selection keyboard
        try:
            habits = await db_manager.get_user_habits(user.id)
            if not habits: await msg.reply_text(lang.MSG_NO_HABITS_TO_MARK_DONE); return
            kbd_rows = keyboards.select_habit_keyboard(habits, c.CALLBACK_SELECT_HABIT_DONE)
            await msg.reply_text(lang.PROMPT_MARK_DONE_SELECT, reply_markup=InlineKeyboardMarkup(kbd_rows))
        except ConnectionError: await msg.reply_text(lang.ERR_DATABASE_CONNECTION)
        except Exception as e: logger.error(f"Err getting habits for /done kbd: {e}", exc_info=True); await msg.reply_text(lang.MSG_ERROR_GENERAL)

async def mark_done_button_press(update: Update, ctx: CallbackContext) -> None:
    """Handles 'Done' button press from /today view."""
    query = update.callback_query
    if not query or not query.message or not query.data: return
    await query.answer()
    try: habit_id = int(query.data.split('_', 1)[1])
    except (ValueError, TypeError, IndexError): await query.answer(text=lang.ERR_MARK_DONE_FAILED_ID, show_alert=True); return

    user = query.from_user
    result, name = await _perform_mark_done(user.id, habit_id)
    safe_name = helpers.escape_html(name or lang.DEFAULT_HABIT_NAME)

    if result == "success":
        logger.info(f"User {user.id} marked habit {habit_id} done via button.")
        await _refresh_today_view_edit(ctx, query.message.chat.id, query.message.message_id, user.id)
    elif result == "already_done": await query.answer(text=lang.ERR_HABIT_ALREADY_DONE.format(habit_name=safe_name), show_alert=True)
    elif result == "not_found":
         await query.answer(text=lang.ERR_MARK_DONE_FAILED_NOT_FOUND, show_alert=True)
         await _refresh_today_view_edit(ctx, query.message.chat.id, query.message.message_id, user.id) # Refresh anyway
    else: # error
        err_msg = lang.ERR_DATABASE_CONNECTION if isinstance(ctx.error, ConnectionError) else lang.ERR_MARK_DONE_FAILED
        await query.answer(text=err_msg, show_alert=True)

async def mark_done_select_habit_callback(update: Update, ctx: CallbackContext) -> None:
    """Handles habit selection button press from /done keyboard."""
    query = update.callback_query
    if not query or not query.message or not query.data: return
    await query.answer()
    try: habit_id = int(query.data.split('_', 1)[1])
    except (ValueError, TypeError, IndexError): await query.edit_message_text(lang.ERR_GENERIC_CALLBACK); return

    user = query.from_user
    result, name = await _perform_mark_done(user.id, habit_id)
    safe_name = helpers.escape_html(name or lang.DEFAULT_HABIT_NAME)
    responses = {
        "success": lang.CONFIRM_HABIT_MARKED_DONE,
        "already_done": lang.ERR_HABIT_ALREADY_DONE,
        "not_found": lang.ERR_HABIT_NOT_FOUND_GENERIC,
    }
    err_msg = lang.ERR_DATABASE_CONNECTION if isinstance(ctx.error, ConnectionError) else lang.ERR_MARK_DONE_FAILED
    await query.edit_message_text(responses.get(result, err_msg).format(habit_name=safe_name))

async def _refresh_today_view_edit(ctx: CallbackContext, chat_id: int, msg_id: int, user_id: int):
    """Refetches today's habits and edits original /today message."""
    try:
        content = await _generate_today_message(user_id)
        await ctx.bot.edit_message_text(chat_id=chat_id, message_id=msg_id, **content)
    except ConnectionError: logger.error("DB conn unavailable during _refresh_today_view_edit")
    except tg_error.BadRequest as e:
         if "Message is not modified" not in str(e): logger.error(f"Failed edit msg refresh: {e}", exc_info=True)
         else: logger.debug("Msg not modified during refresh.")
    except Exception as e: logger.error(f"Error during today refresh: {e}", exc_info=True)