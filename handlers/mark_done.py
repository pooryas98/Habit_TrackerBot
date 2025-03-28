# handlers/mark_done.py

from telegram import Update, error as telegram_error
from telegram.ext import CommandHandler, CallbackQueryHandler, CallbackContext
from datetime import date
import logging

from utils import localization as lang, helpers, keyboards, constants as c
from database import db_manager # Import db_manager module
from .view_habits import _generate_today_message

logger = logging.getLogger(__name__)

async def mark_done_by_name(update: Update, context: CallbackContext) -> None:
    """Marks a habit done using '/done habit_name' command."""
    user = update.effective_user
    message = update.effective_message
    if not user or not message: return

    if not context.args:
        await message.reply_text(lang.PROMPT_MARK_DONE_WHICH + "\n" + lang.EXAMPLE_MARK_DONE)
        return

    habit_name_query = " ".join(context.args).strip()

    try:
        # Call db_manager directly
        habit = await db_manager.find_habit_by_name(user.id, habit_name_query)

        if not habit:
            await message.reply_text(lang.ERR_HABIT_NOT_FOUND.format(habit_name=habit_name_query))
            return

        habit_id, habit_name = habit
        today = helpers.get_today_date()
        result = await db_manager.mark_habit_done_db(user.id, habit_id, today)

        if result == "success":
            await message.reply_text(lang.CONFIRM_HABIT_MARKED_DONE.format(habit_name=habit_name))
        elif result == "already_done":
            await message.reply_text(lang.ERR_HABIT_ALREADY_DONE.format(habit_name=habit_name))
        elif result == "not_found":
             await message.reply_text(lang.ERR_HABIT_NOT_FOUND.format(habit_name=habit_name))
        else: # "error"
            await message.reply_text(lang.ERR_MARK_DONE_FAILED)

    except ConnectionError:
         logger.error("Database connection unavailable for mark_done_by_name")
         await message.reply_text(lang.ERR_DATABASE_CONNECTION)
    except Exception as e:
         logger.error(f"Error in mark_done_by_name: {e}", exc_info=True)
         await message.reply_text(lang.ERR_MARK_DONE_FAILED)

async def mark_done_button_press(update: Update, context: CallbackContext) -> None:
    """Handles pressing the 'Done' inline button from /today view."""
    query = update.callback_query
    if not query or not query.message: return
    await query.answer()

    try:
        if not query.data or not query.data.startswith(c.CALLBACK_MARK_DONE):
             raise ValueError(f"Invalid callback data prefix: {query.data}")
        habit_id = int(query.data.split('_', 1)[1])
    except (ValueError, TypeError, IndexError):
        logger.error(f"Could not parse habit_id from callback data: {query.data}", exc_info=True)
        await query.answer(text=lang.ERR_MARK_DONE_FAILED_ID, show_alert=True)
        return

    user = query.from_user

    try:
        # Call db_manager directly
        today = helpers.get_today_date()
        habit_name = await db_manager.get_habit_name_by_id(habit_id)
        if not habit_name:
             logger.warning(f"mark_done_button: Habit ID {habit_id} not found for user {user.id}.")
             await query.answer(text=lang.ERR_MARK_DONE_FAILED_NOT_FOUND, show_alert=True)
             await _refresh_today_view_edit(context, query.message.chat.id, query.message.message_id, user.id)
             return

        result = await db_manager.mark_habit_done_db(user.id, habit_id, today)

        if result == "success":
            logger.info(f"User {user.id} marked habit {habit_id} ('{habit_name}') as done via button.")
            await _refresh_today_view_edit(context, query.message.chat.id, query.message.message_id, user.id)
        elif result == "already_done":
            logger.info(f"User {user.id} clicked done for already done habit {habit_id} ('{habit_name}').")
            await query.answer(text=lang.ERR_HABIT_ALREADY_DONE.format(habit_name=habit_name), show_alert=True)
            await _refresh_today_view_edit(context, query.message.chat.id, query.message.message_id, user.id)
        elif result == "not_found":
             await query.answer(text=lang.ERR_MARK_DONE_FAILED_NOT_FOUND, show_alert=True)
             await _refresh_today_view_edit(context, query.message.chat.id, query.message.message_id, user.id)
        else: # result == "error"
            logger.error(f"DB error occurred marking habit {habit_id} ('{habit_name}') done for user {user.id}.")
            await query.answer(text=lang.ERR_MARK_DONE_FAILED, show_alert=True)

    except ConnectionError:
         logger.error("Database connection unavailable for mark_done_button_press")
         await query.answer(text=lang.ERR_DATABASE_CONNECTION, show_alert=True)
    except Exception as e:
         logger.error(f"Error in mark_done_button_press: {e}", exc_info=True)
         await query.answer(text=lang.ERR_MARK_DONE_FAILED, show_alert=True)


async def _refresh_today_view_edit(context: CallbackContext, chat_id: int, message_id: int, user_id: int):
    """Refetches today's habits and edits the original message."""
    try:
        # Call helper directly, it uses db_manager which uses global conn
        message_content = await _generate_today_message(user_id) # Pass only user_id
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=message_content['text'],
            reply_markup=message_content['reply_markup'],
            parse_mode=message_content.get('parse_mode')
        )
    except ConnectionError:
         logger.error("Database connection unavailable for refresh_today_view")
         # Can't edit message without data, maybe send a new error message?
         # await context.bot.send_message(chat_id=chat_id, text=lang.ERR_DATABASE_CONNECTION)
    except telegram_error.BadRequest as e:
         if "Message is not modified" in str(e):
             logger.debug("Message not modified during refresh.")
         else:
              logger.error(f"Failed to edit message for today view refresh: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"Unexpected error during today view refresh: {e}", exc_info=True)


def mark_done_command_handler():
    return CommandHandler(c.CMD_DONE, mark_done_by_name)

def mark_done_button_handler():
    return CallbackQueryHandler(mark_done_button_press, pattern=f"^{c.CALLBACK_MARK_DONE}")