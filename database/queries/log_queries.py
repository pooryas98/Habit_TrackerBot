import logging,aiosqlite
from datetime import date,timedelta,datetime
from typing import List,Tuple,Optional,Dict,Any
from ..connection import _e,_fo,_fa
from .habit_queries import get_user_habits

log=logging.getLogger(__name__)

async def mark_habit_done_db(uid: int, hid: int, log_date: date) -> str:
	ds=log_date.isoformat()
	sql="INSERT INTO HabitLog (habit_id,user_id,log_date,status) VALUES (?,?,?,'done') ON CONFLICT(habit_id,user_id,log_date) DO UPDATE SET status='done' WHERE status!='done'"
	try:
		rc=await _e(sql,(hid,uid,ds))
		if rc is not None and rc>0: log.info(f"Marked h:{hid} done u:{uid} on {ds}"); return "success"
		elif rc==0: log.debug(f"H:{hid} already done u:{uid} on {ds}"); return "already_done"
		else: log.error(f"Mark done h:{hid} unexp rc: {rc}"); return "error"
	except aiosqlite.Error: return "error" # Logged by _e

async def get_todays_habit_statuses(uid: int, today: date) -> Dict[int, str]:
	statuses:Dict[int,str]={}; ds=today.isoformat()
	try:
		habits=await get_user_habits(uid);
		if not habits: return {}
		hids=[h[0] for h in habits]; ph=','.join('?'*len(hids))
		sql=f"SELECT habit_id, status FROM HabitLog WHERE user_id=? AND log_date=? AND habit_id IN ({ph})"
		params=(uid,ds)+tuple(hids)
		logged={r[0]:r[1] for r in await _fa(sql,params)}
		for hid,_,_,_ in habits: statuses[hid]=logged.get(hid,'pending')
		return statuses
	except aiosqlite.Error: return {} # Logged by helpers

async def get_habit_log(uid: int, hid: Optional[int]=None, limit: int=30, offset: int=0) -> List[Tuple[date, str, str]]:
	entries:List[Tuple[date,str,str]]=[]
	try:
		sql="SELECT hl.log_date, h.name, hl.status FROM HabitLog hl JOIN Habits h ON hl.habit_id = h.habit_id WHERE hl.user_id = ?"
		params:List[Any]=[uid]
		if hid is not None: sql+=" AND hl.habit_id = ?"; params.append(hid)
		sql+=" ORDER BY hl.log_date DESC, h.name ASC LIMIT ? OFFSET ?"; params.extend([limit,offset])
		for ds,hname,status in await _fa(sql,tuple(params)):
			try: entries.append((date.fromisoformat(ds),hname,status))
			except (ValueError,TypeError): log.warning(f"Skip log invalid date: d='{ds}', h='{hname}'")
		return entries
	except aiosqlite.Error: return [] # Logged by _fa

async def get_habit_log_count(uid: int, hid: Optional[int]=None) -> int:
	try:
		sql="SELECT COUNT(*) FROM HabitLog WHERE user_id = ?"; params:List[Any]=[uid]
		if hid is not None: sql+=" AND habit_id = ?"; params.append(hid)
		res=await _fo(sql,tuple(params)); return res[0] if res else 0
	except aiosqlite.Error: return 0 # Logged by _fo

async def get_completion_stats(uid: int, days: int=30) -> Dict[int, Dict[str, Any]]:
	stats:Dict[int,Dict[str,Any]]={};
	if days<=0: return {}
	end_d=date.today(); start_d=end_d-timedelta(days=days-1)
	start_s,end_s=start_d.isoformat(),end_d.isoformat()
	try:
		habits=await get_user_habits(uid);
		if not habits: return {}
		hids=[h[0] for h in habits]; ph=','.join('?'*len(hids))
		sql=f"SELECT habit_id, log_date FROM HabitLog WHERE user_id=? AND habit_id IN ({ph}) AND log_date BETWEEN ? AND ? AND status='done' ORDER BY log_date DESC"
		params=(uid,)+tuple(hids)+(start_s,end_s)
		raw_logs=await _fa(sql,params)
		logs_by_h:Dict[int,Dict[date,bool]]={hid: {} for hid in hids} # Store only 'done' dates as bool
		for hid,ds in raw_logs:
			try: logs_by_h[hid][date.fromisoformat(ds)]=True
			except (ValueError,TypeError): log.warning(f"Skip stats log invalid date: d='{ds}', h='{hid}'")

		num_days=(end_d-start_d).days+1
		for h_id,h_name,_,_ in habits:
			h_logs=logs_by_h.get(h_id,{}); done_cnt,cur_s,max_s,tmp_s=0,0,0,0
			is_cur_active=True # Assume streak continues to today unless proven otherwise
			for i in range(num_days):
				d=end_d-timedelta(days=i)
				if d in h_logs: done_cnt+=1; tmp_s+=1
				else:
					max_s=max(max_s,tmp_s); tmp_s=0
					if i==0: is_cur_active=False # Streak broken today
			max_s=max(max_s,tmp_s) # Final check for streak ending today
			cur_s=tmp_s if is_cur_active and (end_d in h_logs) else (tmp_s if is_cur_active and not h_logs else 0) # If streak active check today, else 0
			rate=round((done_cnt/num_days)*100,1) if num_days>0 else 0
			stats[h_id]={"name":h_name,"done_count":done_cnt,"total_days":num_days,"completion_rate":rate,"current_streak":cur_s,"max_streak":max_s}
		return stats
	except aiosqlite.Error: return {} # Logged by helpers