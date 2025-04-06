import logging,re,html,config
from datetime import datetime,time,date,timedelta
from typing import Optional,Callable,Any
from telegram import Update
from telegram.ext import CallbackContext,ConversationHandler
from . import localization as lang

log=logging.getLogger(__name__)
EXAMPLE_TIME_FORMAT="HH:MM (e.g., 09:00 or 17:30)"

def get_today_date()->date: return datetime.now(config.USER_TIMEZONE).date()

def parse_reminder_time(ts: str)->time|None:
	"""Parses HH:MM, H:MM, HH, H into time obj. Returns None if invalid."""
	ts=ts.strip()
	m=re.fullmatch(r"(\d{1,2}):(\d{2})",ts)
	if m:
		try: h,m=int(m[1]),int(m[2]); return time(h,m) if 0<=h<=23 and 0<=m<=59 else None
		except ValueError: pass
	m=re.fullmatch(r"(\d{1,2})",ts)
	if m:
		try: h=int(m[1]); return time(h,0) if 0<=h<=23 else None
		except ValueError: pass
	log.debug(f"Failed parse time: '{ts}'"); return None

def format_time_user_friendly(t: time)->str: return t.strftime("%H:%M")
def format_date_user_friendly(d: date)->str: return d.strftime("%Y-%m-%d")
def escape_html(text:str|None)->str: return html.escape(str(text)) if text else ""

async def cancel_conv(upd:Update,ctx:CallbackContext,clear_ctx_func:Callable|None=None,log_msg:str="Conv cancelled.")->int:
	"""Handles conv cancellation: sends msg, clears ctx, logs, returns END."""
	uid_log=upd.effective_user.id if upd.effective_user else "Unknown"
	try:
		target=upd.callback_query or upd.effective_message
		if upd.callback_query: await upd.callback_query.answer(); await upd.callback_query.edit_message_text(lang.MSG_CANCELLED)
		elif upd.effective_message: await upd.effective_message.reply_text(lang.MSG_CANCELLED)
		else: log.warning(f"Cannot send cancel msg u:{uid_log}")
	except Exception as e: log.error(f"Err sending cancel msg u:{uid_log}: {e}")
	if clear_ctx_func:
		try: log.debug(f"Calling ctx clear func '{clear_ctx_func.__name__}' u:{uid_log}."); clear_ctx_func(ctx)
		except Exception as e: log.error(f"Err exec ctx clear func cancel: {e}",exc_info=True)
	log.info(f"{log_msg} (User: {uid_log})")
	return ConversationHandler.END