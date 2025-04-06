import os,logging,pytz
from zoneinfo import ZoneInfo,ZoneInfoNotFoundError
from typing import List,Optional,Union
from dotenv import load_dotenv

load_dotenv()
log=logging.getLogger(__name__)

# Core
BOT_TOKEN:str|None=os.getenv("BOT_TOKEN")
DB_FILE:str=os.getenv("DATABASE_FILE","habits_data.db")

# Timezone
tz_s=os.getenv("USER_TIMEZONE","UTC"); tz_type="?"
try: TZ:Union[ZoneInfo,pytz.BaseTzInfo]=ZoneInfo(tz_s); tz_type="zoneinfo"
except ZoneInfoNotFoundError:
	try: TZ=pytz.timezone(tz_s); tz_type="pytz"
	except pytz.UnknownTimeZoneError: log.critical(f"Invalid TZ '{tz_s}'. Using UTC."); TZ=ZoneInfo("UTC"); tz_type="zoneinfo(bk)"
except Exception as e: log.critical(f"Err load TZ '{tz_s}': {e}. Using UTC."); TZ=ZoneInfo("UTC"); tz_type="zoneinfo(err)"
USER_TIMEZONE=TZ

# Optional
dev_id_s=os.getenv("DEVELOPER_CHAT_ID")
DEVELOPER_CHAT_ID:int|None=int(dev_id_s) if dev_id_s and dev_id_s.isdigit() else None
LOG_LEVEL:str=os.getenv("LOG_LEVEL","INFO").upper()
RESET_DB:bool=os.getenv("RESET_DB_ON_START")=="1"

# Channel Membership
raw_ch=os.getenv("REQUIRED_CHANNEL_IDS","")
REQUIRED_CHANNEL_IDS:List[Union[str,int]]=[]
if raw_ch:
	for item in raw_ch.split(','):
		item=item.strip();
		if not item: continue
		if item.startswith('@'): REQUIRED_CHANNEL_IDS.append(item)
		else:
			try: REQUIRED_CHANNEL_IDS.append(int(item))
			except ValueError: log.warning(f"Ignoring invalid ch ID: '{item}'")
ch_ttl_s=os.getenv("CHANNEL_MEMBERSHIP_CACHE_TTL")
CHANNEL_MEMBERSHIP_CACHE_TTL:int=int(ch_ttl_s) if ch_ttl_s and ch_ttl_s.isdigit() else 300

# Validation
if not BOT_TOKEN: raise ValueError("FATAL: BOT_TOKEN env var not set!")

# Lib Logging Levels
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.INFO)

# Startup Log
log.info(f"Cfg: DB={DB_FILE}, TZ={tz_s}({tz_type}), Log={LOG_LEVEL}")
if DEVELOPER_CHAT_ID: log.info(f" DevID: {DEVELOPER_CHAT_ID}")
if RESET_DB: log.warning(" RESET_DB_ON_START ENABLED!")
log.info(f" ChanLock: {'ON' if REQUIRED_CHANNEL_IDS else 'OFF'} "+(f"(Chs:{REQUIRED_CHANNEL_IDS}, TTL:{CHANNEL_MEMBERSHIP_CACHE_TTL}s)" if REQUIRED_CHANNEL_IDS else ""))