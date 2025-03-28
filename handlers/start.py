# handlers/start.py

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup # Added Inline imports
from telegram.ext import CommandHandler, CallbackContext
# --- ADD THIS IMPORT ---
from telegram.constants import ParseMode
# --- END ADD ---

from utils import localization as lang
from utils import constants as c
from database import db_manager
# --- Add imports ---
import config # Needed for REQUIRED_CHANNEL_IDS check in refresh
from utils.checks import CACHE_KEY_PREFIX, check_channel_membership # Import check function and prefix
# --- End imports ---

logger = logging.getLogger(__name__)

# Keep the original start and help functions
async def start(update: Update, context: CallbackContext) -> None:
    """Sends a welcome message, registers user, and shows help."""
    user = update.effective_user
    message = update.effective_message
    if not user or not message:
        return # Cannot proceed

    try:
        # Call db_manager function directly, it handles the connection
        await db_manager.add_user_if_not_exists(user.id)
        logger.info(f"User {user.id} ({user.username}) started the bot.")
        await message.reply_text(lang.MSG_WELCOME.format(user_name=user.first_name))
        await help_command(update, context) # Show help after welcome
    except ConnectionError: # Catch error if global connection is unavailable
        logger.error("Database connection unavailable for /start")
        await message.reply_text(lang.ERR_DATABASE_CONNECTION)
    except Exception as e:
        # Log the specific error from help_command or other issues
        logger.error(f"Error during /start for user {user.id}: {e}", exc_info=True)
        # If the error wasn't specifically the help message failing, send a general error.
        # The traceback shows the error originates in help_command, so this isn't strictly needed now.
        # if "help_command" not in traceback.format_exc(): # Example check
        #     await message.reply_text(lang.MSG_ERROR_GENERAL)


async def help_command(update: Update, context: CallbackContext) -> None:
    """Sends help message with available commands."""
    if update.effective_message:
        await update.effective_message.reply_text(
            lang.MSG_HELP,
            disable_web_page_preview=True,
            parse_mode=None # <--- FIX: Explicitly set parse_mode to None
        )

# --- NEW REFRESH FUNCTION ---
async def refresh_membership_command(update: Update, context: CallbackContext) -> None:
    """Clears the membership cache and re-checks the user's status."""
    user = update.effective_user
    message = update.effective_message
    if not user or not message:
        return

    # No need to check membership here, this command should always run
    if not config.REQUIRED_CHANNEL_IDS:
        await message.reply_text(" بررسی عضویت کانال فعال نیست.") # Inform user if disabled
        return

    user_id = user.id
    user_data = context.user_data if context.user_data is not None else {}
    refreshed_any = False

    # 1. Clear cache entries for this user
    logger.debug(f"User {user_id} triggered /refresh_membership. Clearing cache.")
    keys_to_delete = []
    for key in list(user_data.keys()): # Iterate over a copy of keys
        if isinstance(key, str) and key.startswith(CACHE_KEY_PREFIX):
            keys_to_delete.append(key)

    if keys_to_delete:
        for key in keys_to_delete:
            del user_data[key]
            logger.debug(f"Deleted cache key '{key}' for user {user_id}")
        refreshed_any = True
    else:
        logger.debug(f"No membership cache keys found for user {user_id} to delete.")

    # 2. Send "refreshing" message
    await message.reply_text(lang.MSG_MEMBERSHIP_REFRESHING)

    # 3. Re-run the check (this will call the API since cache is cleared)
    try:
        is_now_member = await check_channel_membership(update, context) # Use the check function directly

        # 4. Inform the user of the result
        if is_now_member:
            await message.reply_text(lang.MSG_MEMBERSHIP_REFRESHED_OK)
            logger.info(f"Membership refresh for user {user_id} successful (is member).")
        else:
            # Re-send the join message if they are still not members
            keyboard = []
            for i, channel_id in enumerate(config.REQUIRED_CHANNEL_IDS):
                try:
                    if isinstance(channel_id, str) and channel_id.startswith('@'):
                        link = f"https://t.me/{channel_id[1:]}"
                    else:
                        # Attempt to get invite link if it's a private channel ID (requires bot admin rights)
                        # This might fail if the bot doesn't have rights or it's a public channel ID entered incorrectly
                        try:
                            chat = await context.bot.get_chat(channel_id)
                            link = chat.invite_link
                            if not link:
                                logger.warning(f"Refresh: Could not get invite link for numeric channel ID {channel_id}. Bot might need exportChatInviteLink permission or it's public.")
                        except Exception as chat_err:
                            logger.warning(f"Refresh: Error getting chat info for {channel_id} to find link: {chat_err}")
                            link = None

                    button_text = f"{lang.BUTTON_JOIN_CHANNEL} {i+1}"
                    if link:
                        keyboard.append([InlineKeyboardButton(button_text, url=link)])
                    else:
                        # If no link could be found, don't add a broken button
                        logger.warning(f"Refresh: No link available for channel {channel_id}, skipping button.")

                except Exception as e:
                    logger.error(f"Refresh: Could not create join button for {channel_id}: {e}")

            reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None

            await message.reply_text(lang.MSG_MEMBERSHIP_REFRESHED_FAIL, reply_markup=reply_markup)
            logger.info(f"Membership refresh for user {user_id} completed (still not member).")

    except Exception as e:
        # Catch potential API errors during the re-check
        logger.error(f"Error during membership re-check for user {user_id}: {e}", exc_info=True)
        await message.reply_text(lang.ERR_MEMBERSHIP_REFRESH_API)
# --- END NEW REFRESH FUNCTION ---

# --- Define functions to export handlers ---
# We still need these to be referenced by main.py
def start_handler() -> CommandHandler:
    # Note: Decoration happens in main.py now
    return CommandHandler(c.CMD_START, start)

def help_handler() -> CommandHandler:
    # Note: Decoration happens in main.py now
    return CommandHandler(c.CMD_HELP, help_command)

def refresh_membership_handler() -> CommandHandler:
    # The refresh command itself doesn't need the membership check decorator
    return CommandHandler(c.CMD_REFRESH_MEMBERSHIP, refresh_membership_command)
# --- End handler export functions ---