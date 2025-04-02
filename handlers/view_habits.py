import logging
import math
from telegram import Update, InlineKeyboardMarkup
from telegram.helpers import escape_markdown
from telegram.constants import ParseMode
from telegram.ext import CommandHandler, CallbackContext, CallbackQueryHandler
from telegram.error import BadRequest
from typing import Dict, Any
from utils import localization as lang, helpers, keyboards, constants as c
from database import db_manager

logger = logging.getLogger(__name__)

async def _generate_today_message(user_id: int) -> Dict[str, Any]:
    """Generates text/keyboard for /today (HTML)."""
    try:
        today = helpers.get_today_date()
        habits = await db_manager.get_user_habits(user_id)
        statuses = await db_manager.get_todays_habit_statuses(user_id, today)

        if not habits: return {"text": lang.MSG_NO_HABITS_TODAY, "reply_markup": None, "parse_mode": None}

        today_str = helpers.format_date_user_friendly(today)
        msg_text = lang.MSG_TODAY_HEADER.format(today_date=today_str) + "\n\n"
        habits_for_kbd = []
        for hid, name, _, _ in habits:
            status = statuses.get(hid, 'pending')
            status_txt = lang.STATUS_DONE if status == 'done' else lang.STATUS_PENDING
            safe_name = helpers.escape_html(name)
            msg_text += f"- {safe_name}: {status_txt}\n"
            habits_for_kbd.append((hid, name, status))

        reply_markup = keyboards.today_habits_keyboard(habits_for_kbd)
        return {"text": msg_text, "reply_markup": reply_markup, "parse_mode": ParseMode.HTML}
    except ConnectionError: return {"text": lang.ERR_DATABASE_CONNECTION, "reply_markup": None, "parse_mode": None}
    except Exception as e:
         logger.error(f"Error gen today msg for user {user_id}: {e}", exc_info=True)
         return {"text": lang.MSG_ERROR_GENERAL, "reply_markup": None, "parse_mode": None}

async def show_today(update: Update, context: CallbackContext) -> None:
    """Displays today's habits & status via inline keyboard."""
    if not update.effective_message or not update.effective_user: return
    msg_content = await _generate_today_message(update.effective_user.id)
    await update.effective_message.reply_text(
        text=msg_content['text'], reply_markup=msg_content['reply_markup'], parse_mode=msg_content.get('parse_mode')
    )

async def _generate_history_content(user_id: int, offset: int = 0, limit: int = c.HISTORY_PAGE_LIMIT) -> Dict[str, Any]:
    """Generates text/keyboard for /history (HTML, paginated)."""
    try:
        log_entries = await db_manager.get_habit_log(user_id, limit=limit, offset=offset)
        total_count = await db_manager.get_habit_log_count(user_id)

        if total_count == 0: return {"text": lang.MSG_NO_HISTORY, "reply_markup": None, "parse_mode": None}

        current_page = (offset // limit) + 1
        total_pages = math.ceil(total_count / limit)
        msg_text = lang.MSG_HISTORY_HEADER.format(page_num=current_page, total_pages=total_pages) + "\n\n"

        if not log_entries and offset > 0: msg_text += lang.MSG_NO_HISTORY
        else:
            for log_date, habit_name, status in log_entries:
                icon = "✅" if status == 'done' else "❌"
                date_str = helpers.format_date_user_friendly(log_date)
                safe_name = helpers.escape_html(habit_name)
                msg_text += f"{date_str}: {icon} {safe_name}\n"

        if total_pages > 1: msg_text += f"\n{lang.MSG_HISTORY_FOOTER}"
        reply_markup = keyboards.history_pagination_keyboard(offset, total_count, limit)
        return {"text": msg_text, "reply_markup": reply_markup, "parse_mode": ParseMode.HTML}
    except ConnectionError: return {"text": lang.ERR_DATABASE_CONNECTION, "reply_markup": None, "parse_mode": None}
    except Exception as e:
        logger.error(f"Error gen history content for user {user_id}: {e}", exc_info=True)
        return {"text": lang.MSG_ERROR_GENERAL, "reply_markup": None, "parse_mode": None}

async def show_history(update: Update, context: CallbackContext) -> None:
    """Displays recent habit history (paginated)."""
    if not update.effective_message or not update.effective_user: return
    msg_content = await _generate_history_content(update.effective_user.id, offset=0)
    await update.effective_message.reply_text(
        text=msg_content['text'], reply_markup=msg_content['reply_markup'], parse_mode=msg_content.get('parse_mode')
    )

async def show_history_paginated(update: Update, context: CallbackContext) -> None:
    """Handles history pagination button presses."""
    query = update.callback_query
    if not query or not query.message or not query.from_user: return
    await query.answer()

    try:
        if not query.data or not query.data.startswith(c.CALLBACK_HISTORY_PAGE): raise ValueError("Bad prefix")
        offset = int(query.data.split('_', 1)[1])
    except (ValueError, TypeError, IndexError):
        logger.error(f"Failed parsing offset from history cb: {query.data}", exc_info=True)
        await query.answer(text=lang.ERR_GENERIC_CALLBACK, show_alert=True); return

    msg_content = await _generate_history_content(query.from_user.id, offset=offset)
    try:
        await query.edit_message_text(
            text=msg_content['text'], reply_markup=msg_content['reply_markup'], parse_mode=msg_content.get('parse_mode')
        )
    except BadRequest as e:
        if "Message is not modified" not in str(e): logger.error(f"Failed edit history msg: {e}", exc_info=True)
        else: logger.debug(f"History page not modified for offset {offset}.")
    except Exception as e: logger.error(f"Error editing history msg: {e}", exc_info=True)

async def show_stats(update: Update, context: CallbackContext) -> None:
    """Displays habit stats (streaks, rate) last 30 days (MarkdownV2)."""
    if not update.effective_message or not update.effective_user: return
    user_id = update.effective_user.id

    try:
        days = 30
        habit_stats = await db_manager.get_completion_stats(user_id, days_back=days)
        if not habit_stats:
            await update.effective_message.reply_text(lang.MSG_NO_STATS_DATA, parse_mode=ParseMode.MARKDOWN_V2)
            return

        msg_text = lang.MSG_STATS_HEADER.format(days=days) + "\n\n"
        for hid, stats in habit_stats.items():
            # Escape user input and numbers for MarkdownV2
            safe_name = escape_markdown(stats['name'], version=2)
            rate = escape_markdown(str(stats['completion_rate']), version=2)
            done = escape_markdown(str(stats['done_count']), version=2)
            total = escape_markdown(str(stats['total_days']), version=2)
            current = escape_markdown(str(stats['current_streak']), version=2)
            max_s = escape_markdown(str(stats['max_streak']), version=2)

            msg_text += f"📊 *{safe_name}*:\n"
            # Use pre-escaped templates from localization with escaped numbers
            msg_text += lang.MSG_STATS_COMPLETION.format(rate=rate, done=done, total=total) + "\n"
            msg_text += lang.MSG_STATS_STREAK.format(current=current, max_streak=max_s) + "\n\n"

        await update.effective_message.reply_text(msg_text, parse_mode=ParseMode.MARKDOWN_V2)

    except ConnectionError: await update.effective_message.reply_text(lang.ERR_DATABASE_CONNECTION, parse_mode=None)
    except BadRequest as e:
         logger.error(f"BadRequest sending /stats (MarkdownV2 issue?): {e}", exc_info=True)
         await update.effective_message.reply_text(
              f"Error displaying stats: {helpers.escape_html(str(e))}", parse_mode=ParseMode.HTML
         )
    except Exception as e:
        logger.error(f"Error generating /stats for user {user_id}: {e}", exc_info=True)
        await update.effective_message.reply_text(lang.MSG_ERROR_GENERAL, parse_mode=None)

# --- Handlers ---
def today_handler(): return CommandHandler(c.CMD_TODAY, show_today)
def history_handler(): return CommandHandler(c.CMD_HISTORY, show_history)
def history_pagination_handler(): return CallbackQueryHandler(show_history_paginated, pattern=f"^{c.CALLBACK_HISTORY_PAGE}")
def stats_handler(): return CommandHandler(c.CMD_STATS, show_stats)