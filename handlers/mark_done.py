from telegram import Update, error as telegram_error, InlineKeyboardMarkup
from telegram.ext import CommandHandler, CallbackQueryHandler, CallbackContext
from datetime import date
import logging

from utils import localization as lang, helpers, keyboards, constants as c
from database import db_manager # Import db_manager module
from .view_habits import _generate_today_message # Keep for refresh logic

logger = logging.getLogger(__name__)

async def mark_done_command(update: Update, context: CallbackContext) -> None:
    """
    Handles the /done command.
    If arguments are provided, attempts to mark the habit by name.
    If no arguments, displays a keyboard for the user to select a habit.
    """
    user = update.effective_user
    message = update.effective_message
    if not user or not message: return

    if context.args:
        # --- Handle marking by name ---
        habit_name_query = " ".join(context.args).strip()
        await _mark_habit_by_name_logic(message, user.id, habit_name_query)
    else:
        # --- Handle showing selection keyboard ---
        try:
            user_habits = await db_manager.get_user_habits(user.id)
            # Filter out habits already done today? Maybe not, allow re-clicking confirmation.
            # For simplicity, show all habits.
            if not user_habits:
                await message.reply_text(lang.MSG_NO_HABITS_TO_MARK_DONE)
                return

            # Use the generic select_habit_keyboard
            keyboard_rows = keyboards.select_habit_keyboard(user_habits, c.CALLBACK_SELECT_HABIT_DONE)
            reply_markup = InlineKeyboardMarkup(keyboard_rows)
            await message.reply_text(lang.PROMPT_MARK_DONE_SELECT, reply_markup=reply_markup)

        except ConnectionError:
            logger.error("Database connection unavailable for mark_done_command (keyboard)")
            await message.reply_text(lang.ERR_DATABASE_CONNECTION)
        except Exception as e:
            logger.error(f"Error fetching habits for /done keyboard: {e}", exc_info=True)
            await message.reply_text(lang.MSG_ERROR_GENERAL)


async def _mark_habit_by_name_logic(message, user_id: int, habit_name_query: str):
    """
    Internal logic to find a habit by name and mark it done.
    Used by both command with args and potentially other flows.

    Args:
        message: The telegram.Message object to reply to.
        user_id: The ID of the user performing the action.
        habit_name_query: The name of the habit provided by the user.
    """
    try:
        habit = await db_manager.find_habit_by_name(user_id, habit_name_query)

        if not habit:
            await message.reply_text(lang.ERR_HABIT_NOT_FOUND.format(habit_name=habit_name_query))
            return

        habit_id, habit_name = habit
        today = helpers.get_today_date()
        result = await db_manager.mark_habit_done_db(user_id, habit_id, today)

        # --- CORRECTED ---
        # Removed the elif result == "not_found" block
        if result == "success":
            await message.reply_text(lang.CONFIRM_HABIT_MARKED_DONE.format(habit_name=habit_name))
        elif result == "already_done":
            await message.reply_text(lang.ERR_HABIT_ALREADY_DONE.format(habit_name=habit_name))
        else: # "error"
            await message.reply_text(lang.ERR_MARK_DONE_FAILED)
        # --- END CORRECTION ---

    except ConnectionError:
         logger.error("Database connection unavailable for _mark_habit_by_name_logic")
         await message.reply_text(lang.ERR_DATABASE_CONNECTION)
    except Exception as e:
         logger.error(f"Error in _mark_habit_by_name_logic: {e}", exc_info=True)
         await message.reply_text(lang.ERR_MARK_DONE_FAILED)


async def mark_done_button_press(update: Update, context: CallbackContext) -> None:
    """
    Handles pressing the 'Done' inline button from /today view.
    """
    query = update.callback_query
    if not query or not query.message: return
    # Answer callback query immediately to remove the "loading" state on the button
    await query.answer()

    try:
        # Validate callback data prefix
        if not query.data or not query.data.startswith(c.CALLBACK_MARK_DONE):
             raise ValueError(f"Invalid callback data prefix: {query.data}")
        # Extract habit_id
        habit_id = int(query.data.split('_', 1)[1])
    except (ValueError, TypeError, IndexError):
        logger.error(f"Could not parse habit_id from callback data: {query.data}", exc_info=True)
        # Notify user about the error via an alert
        await query.answer(text=lang.ERR_MARK_DONE_FAILED_ID, show_alert=True)
        return

    user = query.from_user

    try:
        today = helpers.get_today_date()
        # Get habit name for user feedback messages
        habit_name = await db_manager.get_habit_name_by_id(habit_id)
        if not habit_name:
             logger.warning(f"mark_done_button: Habit ID {habit_id} not found when user {user.id} clicked done.")
             await query.answer(text=lang.ERR_MARK_DONE_FAILED_NOT_FOUND, show_alert=True)
             # Refresh the view to remove the potentially stale button
             await _refresh_today_view_edit(context, query.message.chat.id, query.message.message_id, user.id)
             return

        # Attempt to mark the habit as done in the database
        result = await db_manager.mark_habit_done_db(user.id, habit_id, today)

        if result == "success":
            logger.info(f"User {user.id} marked habit {habit_id} ('{habit_name}') as done via button.")
            # Refresh the /today message to show the updated status
            await _refresh_today_view_edit(context, query.message.chat.id, query.message.message_id, user.id)
        elif result == "already_done":
            logger.info(f"User {user.id} clicked done for already done habit {habit_id} ('{habit_name}').")
            # Inform the user via an alert, no need to refresh if status hasn't changed visually (already has checkmark)
            await query.answer(text=lang.ERR_HABIT_ALREADY_DONE.format(habit_name=habit_name), show_alert=True)
            # Optional: Still refresh if the keyboard generation logic might change subtly
            # await _refresh_today_view_edit(context, query.message.chat.id, query.message.message_id, user.id)
        # 'not_found' isn't returned by mark_habit_done_db, handled by get_habit_name_by_id check
        else: # result == "error"
            logger.error(f"DB error occurred marking habit {habit_id} ('{habit_name}') done for user {user.id}.")
            await query.answer(text=lang.ERR_MARK_DONE_FAILED, show_alert=True)

    except ConnectionError:
         logger.error("Database connection unavailable for mark_done_button_press")
         await query.answer(text=lang.ERR_DATABASE_CONNECTION, show_alert=True)
    except Exception as e:
         logger.error(f"Error in mark_done_button_press: {e}", exc_info=True)
         await query.answer(text=lang.ERR_MARK_DONE_FAILED, show_alert=True)


async def mark_done_select_habit_callback(update: Update, context: CallbackContext) -> None:
    """
    Handles habit selection via button press from the `/done` command (when no args).
    """
    query = update.callback_query
    if not query or not query.message: return
    await query.answer()

    try:
        if not query.data or not query.data.startswith(c.CALLBACK_SELECT_HABIT_DONE):
             raise ValueError(f"Invalid callback data prefix: {query.data}")
        habit_id = int(query.data.split('_', 1)[1])
    except (ValueError, TypeError, IndexError):
        logger.error(f"Could not parse habit_id from select done callback data: {query.data}", exc_info=True)
        await query.edit_message_text(lang.ERR_GENERIC_CALLBACK)
        return

    user = query.from_user

    try:
        habit_name = await db_manager.get_habit_name_by_id(habit_id)
        if not habit_name:
            logger.warning(f"mark_done_select_habit: Habit ID {habit_id} not found for user {user.id}.")
            await query.edit_message_text(lang.ERR_HABIT_NOT_FOUND_GENERIC)
            return

        today = helpers.get_today_date()
        result = await db_manager.mark_habit_done_db(user.id, habit_id, today)

        # Edit the original message (which showed the selection keyboard)
        if result == "success":
            logger.info(f"User {user.id} marked habit {habit_id} ('{habit_name}') as done via selection keyboard.")
            await query.edit_message_text(lang.CONFIRM_HABIT_MARKED_DONE.format(habit_name=habit_name))
        elif result == "already_done":
            logger.info(f"User {user.id} selected already done habit {habit_id} ('{habit_name}').")
            await query.edit_message_text(lang.ERR_HABIT_ALREADY_DONE.format(habit_name=habit_name))
        else: # result == "error"
            logger.error(f"DB error occurred marking habit {habit_id} ('{habit_name}') done via selection for user {user.id}.")
            await query.edit_message_text(lang.ERR_MARK_DONE_FAILED)

    except ConnectionError:
         logger.error("Database connection unavailable for mark_done_select_habit_callback")
         await query.edit_message_text(lang.ERR_DATABASE_CONNECTION)
    except Exception as e:
         logger.error(f"Error in mark_done_select_habit_callback: {e}", exc_info=True)
         await query.edit_message_text(lang.ERR_MARK_DONE_FAILED)


async def _refresh_today_view_edit(context: CallbackContext, chat_id: int, message_id: int, user_id: int):
    """
    Refetches today's habits and edits the original /today message.

    Args:
        context: The CallbackContext.
        chat_id: The chat ID of the message to edit.
        message_id: The message ID of the message to edit.
        user_id: The user ID for whom to fetch habits.
    """
    try:
        # Generate the updated message content (text and keyboard)
        message_content = await _generate_today_message(user_id) # Pass only user_id
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=message_content['text'],
            reply_markup=message_content['reply_markup'],
            parse_mode=message_content.get('parse_mode') # Use parse_mode if provided by helper
        )
    except ConnectionError:
         logger.error("Database connection unavailable during _refresh_today_view_edit")
         # Cannot edit message without data, maybe send a new error message?
         # Consider sending a new message if editing fails crucially.
         # await context.bot.send_message(chat_id=chat_id, text=lang.ERR_DATABASE_CONNECTION)
    except telegram_error.BadRequest as e:
         # Ignore common error when the message content hasn't actually changed
         if "Message is not modified" in str(e):
             logger.debug("Message not modified during refresh, likely already up-to-date.")
         else:
              logger.error(f"Failed to edit message for today view refresh: {e}", exc_info=True)
              # Potentially send a new message as fallback here too?
    except Exception as e:
        logger.error(f"Unexpected error during today view refresh (_refresh_today_view_edit): {e}", exc_info=True)
        # Potentially send a new message as fallback


# --- Handler Registration Functions ---
def mark_done_command_handler():
    """Returns the CommandHandler for the /done command."""
    return CommandHandler(c.CMD_DONE, mark_done_command)

def mark_done_button_handler():
    """Returns the CallbackQueryHandler for the 'Done' button in /today view."""
    # Pattern matches callbacks starting with 'done_'
    return CallbackQueryHandler(mark_done_button_press, pattern=f"^{c.CALLBACK_MARK_DONE}")

def mark_done_select_habit_handler():
    """Returns the CallbackQueryHandler for habit selection buttons from /done command."""
    # Pattern matches callbacks starting with 'seldone_'
    return CallbackQueryHandler(mark_done_select_habit_callback, pattern=f"^{c.CALLBACK_SELECT_HABIT_DONE}")
