# utils/checks.py

import logging
import time
import functools
from typing import Optional, Dict, Any, Callable, Coroutine

from telegram import Update
from telegram.constants import ChatMemberStatus
# Import specific ConversationHandler return value if needed by decorator
from telegram.ext import CallbackContext, ApplicationHandlerStop, ConversationHandler
from telegram.error import BadRequest, Forbidden
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

import config
from . import localization as lang

logger = logging.getLogger(__name__)

CACHE_KEY_PREFIX = "channel_membership_"

async def check_channel_membership(update: Update, context: CallbackContext) -> bool:
    """
    Checks if the user is a member of all REQUIRED_CHANNEL_IDS defined in config.
    Uses caching in context.user_data.
    """
    if not config.REQUIRED_CHANNEL_IDS:
        logger.debug("Channel membership requirement disabled.")
        return True

    user = update.effective_user
    if not user:
        logger.warning("check_channel_membership called without effective_user.")
        return False

    user_id = user.id
    current_time = time.time()
    user_data = context.user_data if context.user_data is not None else {}

    all_channels_joined = True
    for channel_id in config.REQUIRED_CHANNEL_IDS:
        cache_key = f"{CACHE_KEY_PREFIX}{channel_id}"
        cached_data: Optional[Dict[str, Any]] = user_data.get(cache_key)

        is_member: Optional[bool] = None
        cache_status = "MISS"

        # 1. Check cache
        if cached_data:
            status = cached_data.get("status")
            checked_at = cached_data.get("checked_at", 0)
            ttl = config.CHANNEL_MEMBERSHIP_CACHE_TTL
            if current_time - checked_at < ttl:
                logger.debug(f"Cache HIT for user {user_id}, channel {channel_id}: Status={status} (TTL: {ttl}s)")
                is_member = status
                cache_status = "HIT"
            else:
                logger.debug(f"Cache EXPIRED for user {user_id}, channel {channel_id} (Checked at: {checked_at}, Now: {current_time}, TTL: {ttl}s)")
                cache_status = "EXPIRED"

        # 2. Cache miss or expired, call API
        if is_member is None:
            logger.debug(f"Cache {cache_status} for user {user_id}, channel {channel_id}. Calling get_chat_member API.")
            try:
                # --- Log API Call ---
                logger.debug(f"Calling context.bot.get_chat_member(chat_id={channel_id!r}, user_id={user_id})")
                member = await context.bot.get_chat_member(chat_id=channel_id, user_id=user_id)
                # --- Log API Response ---
                actual_status = member.status
                logger.info(f"API check result for user {user_id}, channel {channel_id}: Actual Status='{actual_status}'") # <-- Key log

                # Define valid statuses
                valid_statuses = [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
                logger.debug(f"Checking if '{actual_status}' is in valid statuses: {valid_statuses}")
                is_member = actual_status in valid_statuses
                # --- Log Check Result ---
                logger.info(f"Membership check evaluated to: {is_member} for user {user_id} in channel {channel_id}")

                # Update cache
                user_data[cache_key] = {"status": is_member, "checked_at": current_time}
                logger.debug(f"Cache updated for user {user_id}, channel {channel_id}: {user_data[cache_key]}")

            except BadRequest as e:
                logger.error(f"BadRequest checking membership for user {user_id} in channel {channel_id}: {e}. Bot might lack admin rights or channel ID is wrong.")
                is_member = False
                user_data[cache_key] = {"status": False, "checked_at": current_time, "error": "BadRequest"}

            except Forbidden as e:
                logger.error(f"Forbidden checking membership for user {user_id} in channel {channel_id}: {e}. Bot likely kicked or lacks permissions.")
                is_member = False
                user_data[cache_key] = {"status": False, "checked_at": current_time, "error": "Forbidden"}

            except Exception as e:
                logger.error(f"Unexpected error checking membership for user {user_id} in channel {channel_id}: {e}", exc_info=True)
                is_member = False
                user_data[cache_key] = {"status": False, "checked_at": current_time, "error": "Exception"}

        # 3. If check fails for any channel, stop and return False
        if not is_member:
            all_channels_joined = False
            # No need to log failure here, it's logged where is_member is set to False
            break

    logger.debug(f"Final check_channel_membership result for user {user_id}: {all_channels_joined}")
    return all_channels_joined


# --- Decorator (Unchanged logic, just ensure logging is present) ---
def require_membership(handler_func: Callable[[Update, CallbackContext], Coroutine]):
    @functools.wraps(handler_func)
    async def wrapper(update: Update, context: CallbackContext, *args, **kwargs):
        logger.debug(f"Decorator @require_membership checking for handler {handler_func.__name__}")
        # Call the updated check function
        is_member = await check_channel_membership(update, context)

        if not is_member:
            user = update.effective_user
            user_id = user.id if user else "Unknown"
            logger.info(f"User {user_id} failed membership check in decorator for {handler_func.__name__}. Blocking handler.")

            # Send message logic (unchanged)
            keyboard = []
            for i, channel_id in enumerate(config.REQUIRED_CHANNEL_IDS):
                 try:
                      if isinstance(channel_id, str) and channel_id.startswith('@'):
                          link = f"https://t.me/{channel_id[1:]}"
                      else:
                           link = None
                           logger.warning(f"Decorator: Non-username channel ID {channel_id} found. Invite link might be needed.")
                      button_text = f"{lang.BUTTON_JOIN_CHANNEL} {i+1}"
                      if link:
                          keyboard.append([InlineKeyboardButton(button_text, url=link)])
                 except Exception as e:
                      logger.error(f"Decorator: Could not create join button for channel {channel_id}: {e}")
            reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
            message_text = lang.MSG_MUST_JOIN_CHANNEL
            try:
                 query = update.callback_query
                 message = update.effective_message
                 if query and query.message:
                      await query.answer(text=lang.MSG_MUST_JOIN_CHANNEL_ALERT, show_alert=True)
                 elif message:
                      await message.reply_text(message_text, reply_markup=reply_markup)
            except Exception as e:
                 logger.error(f"Decorator: Failed to send 'must join' message to user {user_id}: {e}")

            # Stop processing
            # Check if the original function is a conversation entry point based on its name (adjust names if needed)
            conv_entry_points = ["ask_habit_name", "select_habit_to_delete", "ask_reminder_habit", "start_edit_habit"]
            if handler_func.__name__ in conv_entry_points:
                 logger.debug(f"Decorator detected conversation entry point {handler_func.__name__}, returning ConversationHandler.END")
                 return ConversationHandler.END
            logger.debug(f"Decorator blocking non-conversation handler {handler_func.__name__}")
            return None # Stop this specific handler execution

        else:
            # Membership check passed
            logger.debug(f"Decorator @require_membership passed for {handler_func.__name__}. Running handler.")
            return await handler_func(update, context, *args, **kwargs)

    return wrapper