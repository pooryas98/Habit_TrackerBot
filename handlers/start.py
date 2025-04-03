import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext
from utils import localization as lang, constants as c
from database import db_manager
import config
from utils.checks import CACHE_KEY_PREFIX, check_channel_membership

logger = logging.getLogger(__name__)

async def start(update: Update, ctx: CallbackContext) -> None:
    """Welcome msg, register user, show help."""
    user, msg = update.effective_user, update.effective_message
    if not user or not msg: return
    try:
        await db_manager.add_user_if_not_exists(user.id)
        logger.info(f"User {user.id} ({user.username}) started.")
        await msg.reply_text(lang.MSG_WELCOME.format(user_name=user.first_name))
        await help_command(update, ctx) # Show help
    except ConnectionError: await msg.reply_text(lang.ERR_DATABASE_CONNECTION)
    except Exception as e: logger.error(f"Err during /start u {user.id}: {e}", exc_info=True)

async def help_command(update: Update, ctx: CallbackContext) -> None:
    """Sends help message."""
    if update.effective_message:
        await update.effective_message.reply_text(lang.MSG_HELP, disable_web_page_preview=True, parse_mode=None)

async def refresh_membership_command(update: Update, ctx: CallbackContext) -> None:
    """Clears membership cache, re-checks, informs user."""
    user, msg = update.effective_user, update.effective_message
    if not user or not msg: return
    if not config.REQUIRED_CHANNEL_IDS: await msg.reply_text("Channel check disabled."); return

    user_id = user.id
    user_data = ctx.user_data if ctx.user_data is not None else {}
    logger.debug(f"User {user_id} /refresh: Clearing cache.")
    keys_to_del = [k for k in user_data if isinstance(k, str) and k.startswith(CACHE_KEY_PREFIX)]
    for k in keys_to_del: del user_data[k]
    if keys_to_del: logger.debug(f"Deleted {len(keys_to_del)} cache keys for u {user_id}")

    await msg.reply_text(lang.MSG_MEMBERSHIP_REFRESHING)
    try:
        is_now_member = await check_channel_membership(update, ctx) # Re-check
        if is_now_member:
            await msg.reply_text(lang.MSG_MEMBERSHIP_REFRESHED_OK)
            logger.info(f"Membership refresh OK for u {user_id}.")
        else:
            keyboard = []
            for i, ch_id in enumerate(config.REQUIRED_CHANNEL_IDS):
                 link = f"https://t.me/{ch_id[1:]}" if isinstance(ch_id, str) and ch_id.startswith('@') else None
                 if link: keyboard.append([InlineKeyboardButton(f"{lang.BUTTON_JOIN_CHANNEL} {i+1}", url=link)])
                 else: logger.warning(f"Refresh: No link for channel {ch_id}")
            reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
            await msg.reply_text(lang.MSG_MEMBERSHIP_REFRESHED_FAIL, reply_markup=reply_markup)
            logger.info(f"Membership refresh FAILED for u {user_id}.")
    except Exception as e:
        logger.error(f"Err during membership re-check u {user_id}: {e}", exc_info=True)
        await msg.reply_text(lang.ERR_MEMBERSHIP_REFRESH_API)