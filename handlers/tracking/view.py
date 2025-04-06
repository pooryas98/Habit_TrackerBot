import logging,math
from telegram import Update,InlineKeyboardMarkup
from telegram.ext import Application,CommandHandler,CallbackContext,CallbackQueryHandler
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.helpers import escape_markdown
from typing import Dict,Any,List,Tuple,Optional
from database import get_user_habits,get_todays_habit_statuses,get_habit_log,get_habit_log_count,get_completion_stats
from utils import localization as lang,constants as c,keyboards,helpers
from handlers.common.membership import require_membership

log = logging.getLogger(__name__)

async def _today_msg(uid: int) -> Dict[str, Any]:
	"""Generates content dict for /today."""
	log.debug(f"Gen /today u:{uid}")
	try:
		today=helpers.get_today_date()
		habits=await get_user_habits(uid)
		if not habits: return {"text":lang.MSG_NO_HABITS_TODAY,"reply_markup":None,"parse_mode":ParseMode.HTML}
		statuses=await get_todays_habit_statuses(uid,today)
		today_s=helpers.format_date_user_friendly(today)
		txt=f"{lang.MSG_TODAY_HEADER.format(today_date=today_s)}\n\n"
		kbd_data=[]
		for hid,name,_,_ in habits:
			stat=statuses.get(hid,'pending')
			stat_txt=lang.STATUS_DONE if stat=='done' else lang.STATUS_PENDING
			txt+=f"• {helpers.escape_html(name)}: <b>{stat_txt}</b>\n"
			kbd_data.append((hid,name,stat))
		markup=keyboards.today_habits_keyboard(kbd_data)
		return {"text":txt,"reply_markup":markup,"parse_mode":ParseMode.HTML}
	except ConnectionError: log.error(f"DB err /today u:{uid}"); return {"text":lang.ERR_DATABASE_CONNECTION,"reply_markup":None,"parse_mode":ParseMode.HTML}
	except Exception as e: log.error(f"Err gen /today u:{uid}: {e}",exc_info=True); return {"text":lang.MSG_ERROR_GENERAL,"reply_markup":None,"parse_mode":ParseMode.HTML}

@require_membership
async def today_cmd(upd: Update, ctx: CallbackContext) -> None:
	u=upd.effective_user; m=upd.effective_message
	if not u or not m: return
	log.info(f"U {u.id} req /today.")
	await m.reply_text(**(await _today_msg(u.id)))

async def _hist_msg(uid: int, offset: int=0, limit: int=c.HISTORY_PAGE_LIMIT) -> Dict[str, Any]:
	"""Generates content dict for /history page."""
	log.debug(f"Gen /history u:{uid}, off={offset}, lim={limit}")
	try:
		entries=await get_habit_log(uid,limit=limit,offset=offset)
		total=await get_habit_log_count(uid)
		if total==0: return {"text":lang.MSG_NO_HISTORY,"reply_markup":None,"parse_mode":ParseMode.HTML}
		cur_pg=(offset//limit)+1; total_pg=math.ceil(total/limit)
		txt=f"{lang.MSG_HISTORY_HEADER.format(page_num=cur_pg,total_pages=total_pg)}\n\n"
		if not entries: txt+=lang.MSG_NO_HISTORY # Should not happen if total > 0, but safe check
		else:
			for dt,hname,stat in entries:
				icon="✅" if stat=='done' else ("➖" if stat=='skipped' else "❌")
				txt+=f"{helpers.format_date_user_friendly(dt)}: {icon} {helpers.escape_html(hname)}\n"
		markup=keyboards.history_pagination_keyboard(offset,total,limit) if total_pg > 1 else None
		return {"text":txt,"reply_markup":markup,"parse_mode":ParseMode.HTML}
	except ConnectionError: log.error(f"DB err /history u:{uid}"); return {"text":lang.ERR_DATABASE_CONNECTION,"reply_markup":None,"parse_mode":ParseMode.HTML}
	except Exception as e: log.error(f"Err gen /history u:{uid}: {e}",exc_info=True); return {"text":lang.MSG_ERROR_GENERAL,"reply_markup":None,"parse_mode":ParseMode.HTML}

@require_membership
async def history_cmd(upd: Update, ctx: CallbackContext) -> None:
	u=upd.effective_user; m=upd.effective_message
	if not u or not m: return
	log.info(f"U {u.id} req /history.")
	await m.reply_text(**(await _hist_msg(u.id,offset=0)))

async def hist_page(upd: Update, ctx: CallbackContext) -> None:
	q=upd.callback_query; u=upd.effective_user
	if not q or not q.message or not u or not q.data: return
	await q.answer()
	try:
		if not q.data.startswith(c.CALLBACK_HISTORY_PAGE): raise ValueError("Invalid hist cb")
		offset=int(q.data.split('_',1)[1])
		if offset<0: offset=0
		log.debug(f"U {u.id} req hist pg off {offset}")
		content=await _hist_msg(u.id,offset=offset)
		await q.edit_message_text(**content)
	except (IndexError,ValueError) as e: log.error(f"Err parse offset cb '{q.data}': {e}"); await q.answer(lang.ERR_GENERIC_CALLBACK,show_alert=True)
	except BadRequest as e:
		if "Message is not modified" in str(e): log.debug(f"Hist msg not modified off {offset}.")
		else: log.error(f"BadReq edit hist msg: {e}",exc_info=True); await q.answer(lang.MSG_ERROR_GENERAL,show_alert=True)
	except Exception as e: log.error(f"Err handle hist page: {e}",exc_info=True); await q.answer(lang.MSG_ERROR_GENERAL,show_alert=True)

@require_membership
async def stats_cmd(upd: Update, ctx: CallbackContext) -> None:
	u=upd.effective_user; m=upd.effective_message
	if not u or not m: return
	log.info(f"U {u.id} req /stats.")
	days=30
	try:
		stats_data=await get_completion_stats(u.id,days=days)
		if not stats_data: await m.reply_text(lang.MSG_NO_STATS_DATA,parse_mode=ParseMode.MARKDOWN_V2); return
		txt=lang.MSG_STATS_HEADER.format(days=days)+"\n\n"
		sorted_stats=sorted(stats_data.items(),key=lambda item: item[1]['name'])
		esc=lambda x: escape_markdown(str(x),version=2)
		for _,s in sorted_stats:
			name,rate,done,total,cur,mx=esc(s['name']),esc(s['completion_rate']),esc(s['done_count']),esc(s['total_days']),esc(s['current_streak']),esc(s['max_streak'])
			txt+=f"📊 *{name}*:\n{lang.MSG_STATS_COMPLETION.format(rate=rate,done=done,total=total)}\n{lang.MSG_STATS_STREAK.format(current=cur,max_streak=mx)}\n\n"
		await m.reply_text(txt,parse_mode=ParseMode.MARKDOWN_V2)
	except ConnectionError: await m.reply_text(lang.ERR_DATABASE_CONNECTION,parse_mode=None)
	except BadRequest as e:
		log.error(f"BadReq send /stats (MDv2?) u:{u.id}: {e}",exc_info=True)
		err_msg=f"Error displaying stats: Could not format.\n<code>{helpers.escape_html(str(e))}</code>"
		await m.reply_text(err_msg,parse_mode=ParseMode.HTML)
	except Exception as e: log.error(f"Err gen /stats u:{u.id}: {e}",exc_info=True); await m.reply_text(lang.MSG_ERROR_GENERAL,parse_mode=None)

def register_view_handlers(app: Application):
	app.add_handler(CommandHandler(c.CMD_TODAY, today_cmd))
	app.add_handler(CommandHandler(c.CMD_HISTORY, history_cmd))
	app.add_handler(CommandHandler(c.CMD_STATS, stats_cmd))
	app.add_handler(CallbackQueryHandler(hist_page,pattern=f"^{c.CALLBACK_HISTORY_PAGE}"))
	log.info("Registered view handlers.")