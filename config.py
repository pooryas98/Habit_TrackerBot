import os, logging, pytz
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from typing import List, Optional, Union
from dotenv import load_dotenv

load_dotenv()

# --- Core ---
BOT_TOKEN: str | None = os.getenv("BOT_TOKEN")
DATABASE_FILE: str = os.getenv("DATABASE_FILE", "habits_data.db")

# --- Timezone ---
tz_str = os.getenv("USER_TIMEZONE", "UTC")
tz_info_type = "unknown"
try:
    USER_TIMEZONE: Union[ZoneInfo, pytz.BaseTzInfo] = ZoneInfo(tz_str); tz_info_type = "zoneinfo"
except ZoneInfoNotFoundError:
    try: USER_TIMEZONE = pytz.timezone(tz_str); tz_info_type = "pytz"
    except pytz.UnknownTimeZoneError:
        logging.critical(f"Invalid USER_TIMEZONE '{tz_str}'. Using UTC."); USER_TIMEZONE = ZoneInfo("UTC"); tz_info_type = "zoneinfo (fallback)"

# --- Optional ---
dev_id_str = os.getenv("DEVELOPER_CHAT_ID")
DEVELOPER_CHAT_ID: int | None = int(dev_id_str) if dev_id_str and dev_id_str.isdigit() else None
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
RESET_DB_ON_START: bool = os.getenv("RESET_DB_ON_START") == "1"

# --- Channel Membership ---
raw_ch_ids = os.getenv("REQUIRED_CHANNEL_IDS", "")
REQUIRED_CHANNEL_IDS: List[Union[str, int]] = []
if raw_ch_ids:
    for item in raw_ch_ids.split(','):
        item = item.strip()
        if not item: continue
        if item.startswith('@'): REQUIRED_CHANNEL_IDS.append(item)
        else:
            try: REQUIRED_CHANNEL_IDS.append(int(item))
            except ValueError: logging.warning(f"Ignoring invalid channel ID: '{item}'")

ch_ttl_str = os.getenv("CHANNEL_MEMBERSHIP_CACHE_TTL")
CHANNEL_MEMBERSHIP_CACHE_TTL: int = int(ch_ttl_str) if ch_ttl_str and ch_ttl_str.isdigit() else 300

# --- Validation ---
if not BOT_TOKEN: raise ValueError("BOT_TOKEN environment variable is not set!")

# --- Logging ---
logging.basicConfig(format="%(asctime)s - %(name)s [%(levelname)s] - %(message)s", level=getattr(logging, LOG_LEVEL, logging.INFO))
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.INFO)

# --- Startup Logging ---
logger = logging.getLogger(__name__)
logger.info(f"Config: DB={DATABASE_FILE} | TZ={tz_str} ({tz_info_type}) | Log={LOG_LEVEL}"
            f"{' | DevID=' + str(DEVELOPER_CHAT_ID) if DEVELOPER_CHAT_ID else ''}"
            f"{' | RESET_DB!' if RESET_DB_ON_START else ''}")
logger.info(f"Channel Lock: {'Enabled (' + str(REQUIRED_CHANNEL_IDS) + ', TTL=' + str(CHANNEL_MEMBERSHIP_CACHE_TTL) + 's)' if REQUIRED_CHANNEL_IDS else 'Disabled'}")