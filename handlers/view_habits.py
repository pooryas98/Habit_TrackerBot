import logging, math
from telegram import Update, InlineKeyboardMarkup
from telegram.helpers import escape_markdown
from telegram.constants import ParseMode
from telegram.ext import CallbackContext, CallbackQueryHandler
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
        if not habits: return {"text": lang.MSG_NO_HABITS_TODAY, "reply_markup": None}

        today_str = helpers.format_date_user_friendly(today)
        msg = lang.MSG_TODAY_HEADER.format(today_date=today_str) + "\n\n"
        kbd_data = []
        for hid, name, _, _ in habits:
            status = statuses.get(hid, 'pending')
            status_txt = lang.STATUS_DONE if status == 'done' else lang.STATUS_PENDING
            msg += f"- {helpers.escape_html(name)}: {status_txt}\n"
            kbd_data.append((hid, name, status))
        return {"text": msg, "reply_markup": keyboards.today_habits_keyboard(kbd_data), "parse_mode": ParseMode.HTML}
    except ConnectionError: return {"text": lang.ERR_DATABASE_CONNECTION, "reply_markup": None}
    except Exception as e: logger.error(f"Err gen today msg u {user_id}: {e}", exc_info=True); return {"text": lang.MSG_ERROR_GENERAL, "reply_markup": None}

async def show_today(update: Update, ctx: CallbackContext) -> None:
    """Displays today's habits & status via inline keyboard."""
    if not update.effective_message or not update.effective_user: return
    content = await _generate_today_message(update.effective_user.id)
    await update.effective_message.reply_text(**content)

async def _generate_history_content(user_id: int, offset: int = 0, limit: int = c.HISTORY_PAGE_LIMIT) -> Dict[str, Any]:
    """Generates text/keyboard for /history (HTML, paginated)."""
    try:
        log_entries = await db_manager.get_habit_log(user_id, limit=limit, offset=offset)
        total_count = await db_manager.get_habit_log_count(user_id)
        if total_count == 0: return {"text": lang.MSG_NO_HISTORY, "reply_markup": None}

        cur_page = (offset // limit) + 1
        total_pages = math.ceil(total_count / limit)
        msg = lang.MSG_HISTORY_HEADER.format(page_num=cur_page, total_pages=total_pages) + "\n\n"

        if not log_entries and offset > 0: msg += lang.MSG_NO_HISTORY # Handle empty page after first
        else: msg += "".join([f"{helpers.format_date_user_friendly(ld)}: {'✅' if st == 'done' else '❌'} {helpers.escape_html(hn)}\n" for ld, hn, st in log_entries])

        if total_pages > 1: msg += f"\n{lang.MSG_HISTORY_FOOTER}"
        return {"text": msg, "reply_markup": keyboards.history_pagination_keyboard(offset, total_count, limit), "parse_mode": ParseMode.HTML}
    except ConnectionError: return {"text": lang.ERR_DATABASE_CONNECTION, "reply_markup": None}
    except Exception as e: logger.error(f"Err gen history u {user_id}: {e}", exc_info=True); return {"text": lang.MSG_ERROR_GENERAL, "reply_markup": None}

async def show_history(update: Update, ctx: CallbackContext) -> None:
    """Displays recent habit history (paginated)."""
    if not update.effective_message or not update.effective_user: return
    content = await _generate_history_content(update.effective_user.id, offset=0)
    await update.effective_message.reply_text(**content)

async def show_history_paginated(update: Update, ctx: CallbackContext) -> None:
    """Handles history pagination button presses."""
    query = update.callback_query
    if not query or not query.message or not query.from_user or not query.data: return
    await query.answer()
    try: offset = int(query.data.split('_', 1)[1])
    except (ValueError, TypeError, IndexError): logger.error(f"Failed parsing offset from history cb: {query.data}"); await query.answer(text=lang.ERR_GENERIC_CALLBACK, show_alert=True); return

    content = await _generate_history_content(query.from_user.id, offset=offset)
    try: await query.edit_message_text(**content)
    except BadRequest as e:
        if "Message is not modified" not in str(e): logger.error(f"Failed edit history msg: {e}", exc_info=True)
        else: logger.debug(f"History page not modified offset {offset}.")
    except Exception as e: logger.error(f"Error editing history msg: {e}", exc_info=True)

async def show_stats(update: Update, ctx: CallbackContext) -> None:
    """Displays habit stats (streaks, rate) last 30 days (MarkdownV2)."""
    msg, user = update.effective_message, update.effective_user
    if not msg or not user: return
    try:
        days = 30
        stats = await db_manager.get_completion_stats(user.id, days_back=days)
        if not stats: await msg.reply_text(lang.MSG_NO_STATS_DATA, parse_mode=ParseMode.MARKDOWN_V2); return

        reply_text = lang.MSG_STATS_HEADER.format(days=days) + "\n\n"
        for _, s in stats.items():
            # Escape user input and numbers for MarkdownV2
            esc = lambda x: escape_markdown(str(x), version=2)
            safe_name, rate, done, total, cur, max_s = esc(s['name']), esc(s['completion_rate']), esc(s['done_count']), esc(s['total_days']), esc(s['current_streak']), esc(s['max_streak'])
            reply_text += f"📊 *{safe_name}*:\n"
            reply_text += lang.MSG_STATS_COMPLETION.format(rate=rate, done=done, total=total) + "\n"
            reply_text += lang.MSG_STATS_STREAK.format(current=cur, max_streak=max_s) + "\n\n"
        await msg.reply_text(reply_text, parse_mode=ParseMode.MARKDOWN_V2)
    except ConnectionError: await msg.reply_text(lang.ERR_DATABASE_CONNECTION, parse_mode=None)
    except BadRequest as e:
         logger.error(f"BadRequest sending /stats (MarkdownV2?): {e}", exc_info=True)
         await msg.reply_text(f"Error displaying stats: {helpers.escape_html(str(e))}", parse_mode=ParseMode.HTML)
    except Exception as e: logger.error(f"Err generating /stats u {user.id}: {e}", exc_info=True); await msg.reply_text(lang.MSG_ERROR_GENERAL, parse_mode=None)