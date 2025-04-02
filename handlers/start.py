import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, CallbackContext
from telegram.constants import ParseMode
from utils import localization as lang, constants as c
from database import db_manager
import config
from utils.checks import CACHE_KEY_PREFIX, check_channel_membership

logger = logging.getLogger(__name__)

async def start(update: Update, context: CallbackContext) -> None:
    """Welcome msg, register user, show help."""
    user = update.effective_user
    message = update.effective_message
    if not user or not message: return

    try:
        await db_manager.add_user_if_not_exists(user.id)
        logger.info(f"User {user.id} ({user.username}) started bot.")
        await message.reply_text(lang.MSG_WELCOME.format(user_name=user.first_name))
        await help_command(update, context) # Show help
    except ConnectionError:
        logger.error("DB conn unavailable for /start")
        await message.reply_text(lang.ERR_DATABASE_CONNECTION)
    except Exception as e:
        logger.error(f"Error during /start for user {user.id}: {e}", exc_info=True)
        # General error might be sent if help_command itself didn't fail explicitly
        # await message.reply_text(lang.MSG_ERROR_GENERAL)


async def help_command(update: Update, context: CallbackContext) -> None:
    """Sends help message with commands."""
    if update.effective_message:
        await update.effective_message.reply_text(lang.MSG_HELP, disable_web_page_preview=True, parse_mode=None)

async def refresh_membership_command(update: Update, context: CallbackContext) -> None:
    """Clears membership cache, re-checks status, informs user."""
    user = update.effective_user
    message = update.effective_message
    if not user or not message: return

    if not config.REQUIRED_CHANNEL_IDS:
        await message.reply_text(" Channel membership check not enabled.")
        return

    user_id = user.id
    user_data = context.user_data if context.user_data is not None else {}

    # Clear cache entries
    logger.debug(f"User {user_id} /refresh_membership: Clearing cache.")
    keys_to_delete = [key for key in user_data if isinstance(key, str) and key.startswith(CACHE_KEY_PREFIX)]
    for key in keys_to_delete: del user_data[key]
    if keys_to_delete: logger.debug(f"Deleted {len(keys_to_delete)} cache keys for user {user_id}")

    await message.reply_text(lang.MSG_MEMBERSHIP_REFRESHING)

    try:
        is_now_member = await check_channel_membership(update, context) # Re-check

        if is_now_member:
            await message.reply_text(lang.MSG_MEMBERSHIP_REFRESHED_OK)
            logger.info(f"Membership refresh OK for user {user_id}.")
        else:
            # Re-send join message/buttons if still not member
            keyboard = []
            for i, channel_id in enumerate(config.REQUIRED_CHANNEL_IDS):
                 link = None
                 try:
                      if isinstance(channel_id, str) and channel_id.startswith('@'):
                          link = f"https://t.me/{channel_id[1:]}"
                      # Add other link generation logic if needed (e.g., get_chat invite_link)
                      if link: keyboard.append([InlineKeyboardButton(f"{lang.BUTTON_JOIN_CHANNEL} {i+1}", url=link)])
                      else: logger.warning(f"Refresh: No link for channel {channel_id}, skipping button.")
                 except Exception as e: logger.error(f"Refresh: Error creating join btn for {channel_id}: {e}")

            reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
            await message.reply_text(lang.MSG_MEMBERSHIP_REFRESHED_FAIL, reply_markup=reply_markup)
            logger.info(f"Membership refresh FAILED for user {user_id}.")

    except Exception as e:
        logger.error(f"Error during membership re-check for user {user_id}: {e}", exc_info=True)
        await message.reply_text(lang.ERR_MEMBERSHIP_REFRESH_API)

# --- Handler Export Functions (Decoration happens in main.py) ---
def start_handler(): return CommandHandler(c.CMD_START, start)
def help_handler(): return CommandHandler(c.CMD_HELP, help_command)
def refresh_membership_handler(): return CommandHandler(c.CMD_REFRESH_MEMBERSHIP, refresh_membership_command)