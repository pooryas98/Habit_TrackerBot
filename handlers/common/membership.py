import logging,time,functools,asyncio
from config import settings
from typing import Optional,Dict,Any,Callable,Coroutine
from telegram import Update,InlineKeyboardButton,InlineKeyboardMarkup
from telegram.constants import ChatMemberStatus
from telegram.ext import Application,CommandHandler,CallbackContext,ConversationHandler
from telegram.error import BadRequest,Forbidden
from utils import localization as lang,constants as c

log=logging.getLogger(__name__)
CACHE_PFX="chm_"
VALID_STS={ChatMemberStatus.MEMBER,ChatMemberStatus.ADMINISTRATOR,ChatMemberStatus.OWNER}
CONV_ENTRIES={"add_ask_name","edit_start_cmd","sel_habit_del_cmd","ask_habit","start","list_cmd"} # Incl conv entries & list_cmd

async def check_memb(upd: Update, ctx: CallbackContext) -> bool:
	if not settings.required_channel_ids_list: return True
	u=upd.effective_user;
	if not u: log.warning("check_memb called no user."); return False
	uid=u.id; t=time.time(); data=ctx.user_data if ctx.user_data else {}
	for cid in settings.required_channel_ids_list:
		ck=f"{CACHE_PFX}{cid}"; cached:Optional[Dict[str,Any]]=data.get(ck); member:Optional[bool]=None
		if cached and isinstance(cached,dict):
			if (t-cached.get("t",0)<settings.channel_membership_cache_ttl):
				member=cached.get("s"); err=cached.get("e")
				log.debug(f"Cache HIT u:{uid} ch:'{cid}': M={member}, E={err}")
			else: log.debug(f"Cache EXP u:{uid} ch:'{cid}'.")
		else: log.debug(f"Cache MISS u:{uid} ch:'{cid}'.")
		if member is None:
			err=None
			try:
				log.debug(f"API get_chat_member(ch='{cid}', u={uid})")
				m_info=await ctx.bot.get_chat_member(chat_id=cid,user_id=uid)
				member=m_info.status in VALID_STS
				log.info(f"API check u:{uid} ch:'{cid}': St='{m_info.status}' -> M={member}")
			except (BadRequest,Forbidden) as e: log.error(f"API Err check u:{uid} ch:'{cid}': {type(e).__name__}-{e}"); member=False; err=type(e).__name__
			except Exception as e: log.error(f"Exc check u:{uid} ch:'{cid}': {e}",exc_info=True); member=False; err="Exception"
			cache_entry={"s":member,"t":t}; data[ck]=cache_entry | ({"e":err} if err else {})
		if not member: log.warning(f"Memb check FAIL u:{uid} ch:'{cid}'."); return False
	log.debug(f"Memb check PASS u:{uid}."); return True

def require_membership(h_func:Callable[[Update,CallbackContext],Coroutine]):
	@functools.wraps(h_func)
	async def wrapper(upd: Update, ctx: CallbackContext, *args, **kwargs):
		u=upd.effective_user; fname=h_func.__name__
		if not u: log.warning(f"@require_membership: No user '{fname}'. Skip."); return None
		log.debug(f"@require_m check u:{u.id} h:'{fname}'")
		if await check_memb(upd,ctx): log.debug(f"@require_m PASS u:{u.id} h:'{fname}'."); return await h_func(upd,ctx,*args,**kwargs)
		else:
			log.info(f"@require_m FAIL u:{u.id} h:'{fname}'. Block.")
			kbd=[]
			for i,cid in enumerate(settings.required_channel_ids_list):
				link=f"https://t.me/{cid[1:]}" if isinstance(cid,str) and cid.startswith('@') else None
				if not link and isinstance(cid,int): log.warning(f"Need @username for ch ID {cid}."); continue
				if link: kbd.append([InlineKeyboardButton(f"{lang.BUTTON_JOIN_CHANNEL} #{i+1}",url=link)])
			markup=InlineKeyboardMarkup(kbd) if kbd else None
			try:
				target=upd.callback_query or upd.effective_message
				if upd.callback_query: await upd.callback_query.answer(text=lang.MSG_MUST_JOIN_CHANNEL_ALERT,show_alert=True)
				if target: await target.reply_text(lang.MSG_MUST_JOIN_CHANNEL,reply_markup=markup)
			except Exception as e: log.error(f"Failed send 'must join' u:{u.id}: {e}",exc_info=True)
			if fname in CONV_ENTRIES: log.debug(f"Decorator conv entry '{fname}'. Ret END."); return ConversationHandler.END
			log.debug(f"Decorator block non-conv '{fname}'. Ret None."); return None
	return wrapper

async def refresh_cmd(upd: Update, ctx: CallbackContext) -> None:
	u=upd.effective_user; m=upd.effective_message
	if not u or not m: return
	uid=u.id; data=ctx.user_data if ctx.user_data is not None else {}
	if not settings.required_channel_ids_list: await m.reply_text(lang.MSG_MEMBERSHIP_REFRESH_DISABLED); return
	log.info(f"U {uid} init /refresh. Clear cache.")
	keys_del=[k for k in data if isinstance(k,str) and k.startswith(CACHE_PFX)]
	for k in keys_del: del data[k]
	log.debug(f"Del {len(keys_del)} cache keys u:{uid}.")
	await m.reply_text(lang.MSG_MEMBERSHIP_REFRESHING)
	try:
		await asyncio.sleep(0.2) # Shorter delay
		is_member=await check_memb(upd,ctx)
		if is_member: await m.reply_text(lang.MSG_MEMBERSHIP_REFRESHED_OK); log.info(f"Memb refresh OK u:{uid}.")
		else:
			kbd=[]
			for i,cid in enumerate(settings.required_channel_ids_list):
				link=f"https://t.me/{cid[1:]}" if isinstance(cid,str) and cid.startswith('@') else None
				if link: kbd.append([InlineKeyboardButton(f"{lang.BUTTON_JOIN_CHANNEL} #{i+1}",url=link)])
			markup=InlineKeyboardMarkup(kbd) if kbd else None
			await m.reply_text(lang.MSG_MEMBERSHIP_REFRESHED_FAIL,reply_markup=markup); log.warning(f"Memb refresh FAIL u:{uid}.")
	except Exception as e: log.error(f"Err during re-check u:{uid} /refresh: {e}",exc_info=True); await m.reply_text(lang.ERR_MEMBERSHIP_REFRESH_API)

def register_membership_handlers(app: Application):
	app.add_handler(CommandHandler(c.CMD_REFRESH_MEMBERSHIP,refresh_cmd))
	log.info("Registered /refresh_membership handler.")