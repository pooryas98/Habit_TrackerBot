import logging
import time
import functools
from typing import Optional, Dict, Any, Callable, Coroutine
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatMemberStatus
from telegram.ext import CallbackContext, ApplicationHandlerStop, ConversationHandler
from telegram.error import BadRequest, Forbidden
import config
from . import localization as lang

logger = logging.getLogger(__name__)
CACHE_KEY_PREFIX = "channel_membership_"

async def check_channel_membership(update: Update, context: CallbackContext) -> bool:
    """Checks user membership in REQUIRED_CHANNEL_IDS using cache."""
    if not config.REQUIRED_CHANNEL_IDS: return True
    user = update.effective_user
    if not user: return False

    user_id = user.id
    current_time = time.time()
    user_data = context.user_data if context.user_data is not None else {}
    all_joined = True

    for channel_id in config.REQUIRED_CHANNEL_IDS:
        cache_key = f"{CACHE_KEY_PREFIX}{channel_id}"
        cached_data: Optional[Dict[str, Any]] = user_data.get(cache_key)
        is_member: Optional[bool] = None

        if cached_data: # Check cache first
            checked_at = cached_data.get("checked_at", 0)
            if current_time - checked_at < config.CHANNEL_MEMBERSHIP_CACHE_TTL:
                is_member = cached_data.get("status")
                logger.debug(f"Cache HIT user {user_id}, channel {channel_id}: Status={is_member}")
            else: logger.debug(f"Cache EXPIRED user {user_id}, channel {channel_id}")

        if is_member is None: # Cache miss or expired, call API
            logger.debug(f"Cache MISS/EXPIRED user {user_id}, channel {channel_id}. Calling API.")
            try:
                member = await context.bot.get_chat_member(chat_id=channel_id, user_id=user_id)
                actual_status = member.status
                valid_statuses = [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
                is_member = actual_status in valid_statuses
                logger.info(f"API check user {user_id}, channel {channel_id}: Status='{actual_status}' -> Member={is_member}")
                user_data[cache_key] = {"status": is_member, "checked_at": current_time}
            except (BadRequest, Forbidden) as e:
                logger.error(f"{type(e).__name__} checking membership user {user_id}, channel {channel_id}: {e}.")
                is_member = False
                user_data[cache_key] = {"status": False, "checked_at": current_time, "error": type(e).__name__}
            except Exception as e:
                logger.error(f"Error checking membership user {user_id}, channel {channel_id}: {e}", exc_info=True)
                is_member = False
                user_data[cache_key] = {"status": False, "checked_at": current_time, "error": "Exception"}

        if not is_member:
            all_joined = False
            break # No need to check further

    logger.debug(f"Final membership check result for user {user_id}: {all_joined}")
    return all_joined

def require_membership(handler_func: Callable[[Update, CallbackContext], Coroutine]):
    """Decorator: Checks membership before running handler. Sends join msg if needed."""
    @functools.wraps(handler_func)
    async def wrapper(update: Update, context: CallbackContext, *args, **kwargs):
        logger.debug(f"Decorator @require_membership checking for {handler_func.__name__}")
        is_member = await check_channel_membership(update, context)

        if not is_member:
            user_id = update.effective_user.id if update.effective_user else "Unknown"
            logger.info(f"User {user_id} failed membership check for {handler_func.__name__}. Blocking.")
            keyboard = []
            for i, channel_id in enumerate(config.REQUIRED_CHANNEL_IDS):
                 link = None
                 try:
                      if isinstance(channel_id, str) and channel_id.startswith('@'):
                          link = f"https://t.me/{channel_id[1:]}"
                      # Basic link generation for public numeric IDs (less common)
                      # else: link = f"https://t.me/c/{str(channel_id).replace('-100', '')}" # Basic guess
                      if link: keyboard.append([InlineKeyboardButton(f"{lang.BUTTON_JOIN_CHANNEL} {i+1}", url=link)])
                 except Exception as e: logger.error(f"Decorator: Failed btn creation for {channel_id}: {e}")

            reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
            try:
                 if update.callback_query:
                      await update.callback_query.answer(text=lang.MSG_MUST_JOIN_CHANNEL_ALERT, show_alert=True)
                 elif update.effective_message:
                      await update.effective_message.reply_text(lang.MSG_MUST_JOIN_CHANNEL, reply_markup=reply_markup)
            except Exception as e: logger.error(f"Decorator: Failed sending 'must join' msg to {user_id}: {e}")

            # Check if it's a conversation entry point to return END
            conv_entry_points = ["ask_habit_name", "select_habit_to_delete", "ask_reminder_habit", "start_edit_habit"]
            if handler_func.__name__ in conv_entry_points:
                 logger.debug(f"Decorator: returning ConversationHandler.END for {handler_func.__name__}")
                 return ConversationHandler.END
            logger.debug(f"Decorator: blocking non-conversation handler {handler_func.__name__}")
            return None # Block handler

        else: # Membership check passed
            logger.debug(f"Decorator @require_membership passed for {handler_func.__name__}. Running handler.")
            return await handler_func(update, context, *args, **kwargs)
    return wrapper