import logging, time, functools
from typing import Optional, Dict, Any, Callable, Coroutine
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ChatMemberStatus
from telegram.ext import CallbackContext, ConversationHandler
from telegram.error import BadRequest, Forbidden
import config
from . import localization as lang

logger = logging.getLogger(__name__)
CACHE_KEY_PREFIX = "ch_mem_"
VALID_STATUSES = {ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER}

async def check_channel_membership(update: Update, ctx: CallbackContext) -> bool:
    """Checks user membership in REQUIRED_CHANNEL_IDS using cache."""
    if not config.REQUIRED_CHANNEL_IDS: return True
    user = update.effective_user
    if not user: return False
    user_id = user.id
    current_time = time.time()
    user_data = ctx.user_data if ctx.user_data is not None else {}

    for channel_id in config.REQUIRED_CHANNEL_IDS:
        cache_key = f"{CACHE_KEY_PREFIX}{channel_id}"
        cached_data: Optional[Dict[str, Any]] = user_data.get(cache_key)
        is_member: Optional[bool] = None

        if cached_data and (current_time - cached_data.get("t", 0) < config.CHANNEL_MEMBERSHIP_CACHE_TTL):
            is_member = cached_data.get("s") # Use cached status 's'
            logger.debug(f"Cache HIT u{user_id} c{channel_id}: {is_member}")
        else: # Cache miss or expired
            logger.debug(f"Cache MISS/EXPIRED u{user_id} c{channel_id}. API call.")
            err_type = None
            try:
                member = await ctx.bot.get_chat_member(chat_id=channel_id, user_id=user_id)
                is_member = member.status in VALID_STATUSES
                logger.info(f"API check u{user_id} c{channel_id}: '{member.status}' -> Member={is_member}")
            except (BadRequest, Forbidden) as e: logger.error(f"{type(e).__name__} u{user_id} c{channel_id}: {e}"); is_member = False; err_type = type(e).__name__
            except Exception as e: logger.error(f"Error check u{user_id} c{channel_id}: {e}", exc_info=True); is_member = False; err_type = "Exception"
            user_data[cache_key] = {"s": is_member, "t": current_time} # Store status 's', time 't'
            if err_type: user_data[cache_key]["e"] = err_type # Store error 'e' if any

        if not is_member: logger.debug(f"Membership check FAIL u{user_id} c{channel_id}"); return False

    logger.debug(f"Membership check PASS u{user_id}")
    return True

def require_membership(handler_func: Callable[[Update, CallbackContext], Coroutine]):
    """Decorator: Checks membership before handler. Sends join msg if needed."""
    @functools.wraps(handler_func)
    async def wrapper(update: Update, ctx: CallbackContext, *args, **kwargs):
        func_name = handler_func.__name__
        logger.debug(f"@require_membership check for {func_name}")
        is_member = await check_channel_membership(update, ctx)

        if not is_member:
            user_id = update.effective_user.id if update.effective_user else "Unknown"
            logger.info(f"User {user_id} FAILED check for {func_name}. Blocking.")
            keyboard = []
            for i, ch_id in enumerate(config.REQUIRED_CHANNEL_IDS):
                 link = f"https://t.me/{ch_id[1:]}" if isinstance(ch_id, str) and ch_id.startswith('@') else None
                 if link: keyboard.append([InlineKeyboardButton(f"{lang.BUTTON_JOIN_CHANNEL} {i+1}", url=link)])
                 else: logger.warning(f"Decorator: No link for channel {ch_id}, skipping button.")

            reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
            try:
                 if update.callback_query: await update.callback_query.answer(text=lang.MSG_MUST_JOIN_CHANNEL_ALERT, show_alert=True)
                 elif update.effective_message: await update.effective_message.reply_text(lang.MSG_MUST_JOIN_CHANNEL, reply_markup=reply_markup)
            except Exception as e: logger.error(f"Decorator: Failed sending 'must join' msg to {user_id}: {e}")

            # Check if it's a known conversation entry point name
            if func_name in ("ask_habit_name", "select_habit_to_delete", "ask_reminder_habit", "start_edit_habit"):
                 logger.debug(f"Decorator: returning ConversationHandler.END for {func_name}")
                 return ConversationHandler.END
            logger.debug(f"Decorator: blocking non-conversation handler {func_name}")
            return None # Block handler execution

        # Membership check passed
        logger.debug(f"@require_membership PASSED for {func_name}. Running.")
        return await handler_func(update, ctx, *args, **kwargs)
    return wrapper