from telegram import Update, error as telegram_error, InlineKeyboardMarkup
from telegram.ext import CommandHandler, CallbackQueryHandler, CallbackContext
import logging
from typing import Tuple, Optional

from utils import localization as lang, helpers, keyboards, constants as c
from database import db_manager
from .view_habits import _generate_today_message # For refresh logic

logger = logging.getLogger(__name__)

async def _perform_mark_done(user_id: int, habit_id: int) -> Tuple[str, Optional[str]]:
    """Core logic: marks habit done in DB, returns status & name."""
    try:
        habit_name = await db_manager.get_habit_name_by_id(habit_id)
        if not habit_name:
            logger.warning(f"_perform_mark_done: Habit {habit_id} not found for user {user_id}.")
            return "not_found", None

        today = helpers.get_today_date()
        result = await db_manager.mark_habit_done_db(user_id, habit_id, today)
        # result is 'success', 'already_done', or 'error'
        return result, habit_name
    except ConnectionError:
        return "error", None # Indicate error on connection issues
    except Exception as e:
        logger.error(f"Error in _perform_mark_done for habit {habit_id}: {e}", exc_info=True)
        return "error", None

async def mark_done_command(update: Update, context: CallbackContext) -> None:
    """Handles /done [name] or /done (shows keyboard)."""
    user = update.effective_user
    message = update.effective_message
    if not user or not message: return

    if context.args:
        habit_name_query = " ".join(context.args).strip()
        try:
            habit_info = await db_manager.find_habit_by_name(user.id, habit_name_query)
            if not habit_info:
                await message.reply_text(lang.ERR_HABIT_NOT_FOUND.format(habit_name=helpers.escape_html(habit_name_query)))
                return

            habit_id, _ = habit_info
            result, retrieved_name = await _perform_mark_done(user.id, habit_id)
            safe_name = helpers.escape_html(retrieved_name or habit_name_query) # Use helper result preferably

            if result == "success": await message.reply_text(lang.CONFIRM_HABIT_MARKED_DONE.format(habit_name=safe_name))
            elif result == "already_done": await message.reply_text(lang.ERR_HABIT_ALREADY_DONE.format(habit_name=safe_name))
            else: await message.reply_text(lang.ERR_MARK_DONE_FAILED)
        except ConnectionError: await message.reply_text(lang.ERR_DATABASE_CONNECTION)
        except Exception as e:
             logger.error(f"Error in /done name lookup: {e}", exc_info=True)
             await message.reply_text(lang.ERR_MARK_DONE_FAILED)
    else: # No args, show selection keyboard
        try:
            user_habits = await db_manager.get_user_habits(user.id)
            if not user_habits: await message.reply_text(lang.MSG_NO_HABITS_TO_MARK_DONE); return

            keyboard_rows = keyboards.select_habit_keyboard(user_habits, c.CALLBACK_SELECT_HABIT_DONE)
            await message.reply_text(lang.PROMPT_MARK_DONE_SELECT, reply_markup=InlineKeyboardMarkup(keyboard_rows))
        except ConnectionError: await message.reply_text(lang.ERR_DATABASE_CONNECTION)
        except Exception as e: logger.error(f"Error getting habits for /done keyboard: {e}", exc_info=True); await message.reply_text(lang.MSG_ERROR_GENERAL)

async def mark_done_button_press(update: Update, context: CallbackContext) -> None:
    """Handles 'Done' button press from /today view."""
    query = update.callback_query
    if not query or not query.message: return
    await query.answer()

    try:
        if not query.data or not query.data.startswith(c.CALLBACK_MARK_DONE): raise ValueError("Bad prefix")
        habit_id = int(query.data.split('_', 1)[1])
    except (ValueError, TypeError, IndexError):
        await query.answer(text=lang.ERR_MARK_DONE_FAILED_ID, show_alert=True); return

    user = query.from_user
    result, habit_name = await _perform_mark_done(user.id, habit_id)
    safe_habit_name = helpers.escape_html(habit_name or lang.DEFAULT_HABIT_NAME)

    if result == "success":
        logger.info(f"User {user.id} marked habit {habit_id} done via button.")
        await _refresh_today_view_edit(context, query.message.chat.id, query.message.message_id, user.id)
    elif result == "already_done":
        await query.answer(text=lang.ERR_HABIT_ALREADY_DONE.format(habit_name=safe_habit_name), show_alert=True)
    elif result == "not_found":
         await query.answer(text=lang.ERR_MARK_DONE_FAILED_NOT_FOUND, show_alert=True)
         await _refresh_today_view_edit(context, query.message.chat.id, query.message.message_id, user.id) # Refresh
    else: # error
        error_msg = lang.ERR_DATABASE_CONNECTION if isinstance(context.error, ConnectionError) else lang.ERR_MARK_DONE_FAILED
        await query.answer(text=error_msg, show_alert=True)

async def mark_done_select_habit_callback(update: Update, context: CallbackContext) -> None:
    """Handles habit selection button press from /done keyboard."""
    query = update.callback_query
    if not query or not query.message: return
    await query.answer()

    try:
        if not query.data or not query.data.startswith(c.CALLBACK_SELECT_HABIT_DONE): raise ValueError("Bad prefix")
        habit_id = int(query.data.split('_', 1)[1])
    except (ValueError, TypeError, IndexError):
        await query.edit_message_text(lang.ERR_GENERIC_CALLBACK); return

    user = query.from_user
    result, habit_name = await _perform_mark_done(user.id, habit_id)
    safe_habit_name = helpers.escape_html(habit_name or lang.DEFAULT_HABIT_NAME)

    if result == "success":
        await query.edit_message_text(lang.CONFIRM_HABIT_MARKED_DONE.format(habit_name=safe_habit_name))
    elif result == "already_done":
        await query.edit_message_text(lang.ERR_HABIT_ALREADY_DONE.format(habit_name=safe_habit_name))
    elif result == "not_found":
        await query.edit_message_text(lang.ERR_HABIT_NOT_FOUND_GENERIC)
    else: # error
        error_msg = lang.ERR_DATABASE_CONNECTION if isinstance(context.error, ConnectionError) else lang.ERR_MARK_DONE_FAILED
        await query.edit_message_text(error_msg)

async def _refresh_today_view_edit(context: CallbackContext, chat_id: int, message_id: int, user_id: int):
    """Refetches today's habits and edits original /today message."""
    try:
        message_content = await _generate_today_message(user_id)
        await context.bot.edit_message_text(
            chat_id=chat_id, message_id=message_id,
            text=message_content['text'], reply_markup=message_content['reply_markup'],
            parse_mode=message_content.get('parse_mode')
        )
    except ConnectionError: logger.error("DB conn unavailable during _refresh_today_view_edit")
    except telegram_error.BadRequest as e:
         if "Message is not modified" not in str(e): logger.error(f"Failed edit message refresh: {e}", exc_info=True)
         else: logger.debug("Msg not modified during refresh.")
    except Exception as e: logger.error(f"Error during today refresh: {e}", exc_info=True)

# --- Handler Registration Functions ---
def mark_done_command_handler(): return CommandHandler(c.CMD_DONE, mark_done_command)
def mark_done_button_handler(): return CallbackQueryHandler(mark_done_button_press, pattern=f"^{c.CALLBACK_MARK_DONE}")
def mark_done_select_habit_handler(): return CallbackQueryHandler(mark_done_select_habit_callback, pattern=f"^{c.CALLBACK_SELECT_HABIT_DONE}")