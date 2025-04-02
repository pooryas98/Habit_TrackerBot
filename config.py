import os
import logging
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import pytz
from typing import List, Optional
import time
from dotenv import load_dotenv

load_dotenv() # Load .env file if exists

# --- Core Settings ---
BOT_TOKEN: str | None = os.getenv("BOT_TOKEN")
DATABASE_FILE: str = os.getenv("DATABASE_FILE", "habits_data.db")

# --- Timezone ---
_TZ_STR = os.getenv("USER_TIMEZONE", "UTC")
_TZ_INFO_TYPE = None
try: # Prioritize zoneinfo (Python 3.9+)
    USER_TIMEZONE: ZoneInfo | pytz.BaseTzInfo = ZoneInfo(_TZ_STR)
    _TZ_INFO_TYPE = "zoneinfo"
except ZoneInfoNotFoundError:
    try: # Fallback to pytz
        USER_TIMEZONE = pytz.timezone(_TZ_STR)
        _TZ_INFO_TYPE = "pytz"
    except pytz.UnknownTimeZoneError:
        logging.critical(f"Invalid USER_TIMEZONE '{_TZ_STR}'. Using UTC.")
        USER_TIMEZONE = ZoneInfo("UTC")
        _TZ_INFO_TYPE = "zoneinfo (fallback)"

# --- Optional Settings ---
DEVELOPER_CHAT_ID: int | None = int(s) if (s := os.getenv("DEVELOPER_CHAT_ID")) and s.isdigit() else None
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
RESET_DB_ON_START: bool = os.getenv("RESET_DB_ON_START") == "1"

# --- Channel Membership ---
_raw_channels = os.getenv("REQUIRED_CHANNEL_IDS", "")
REQUIRED_CHANNEL_IDS: List[str | int] = []
if _raw_channels:
    for item in _raw_channels.split(','):
        item = item.strip()
        if not item: continue
        if item.startswith('@'): REQUIRED_CHANNEL_IDS.append(item)
        else:
            try: REQUIRED_CHANNEL_IDS.append(int(item))
            except ValueError: logging.warning(f"Ignoring non-numeric/non-@ channel ID: '{item}'")

CHANNEL_MEMBERSHIP_CACHE_TTL: int = int(s) if (s := os.getenv("CHANNEL_MEMBERSHIP_CACHE_TTL")) and s.isdigit() else 300

# --- Validation ---
if not BOT_TOKEN: raise ValueError("BOT_TOKEN environment variable is not set!")

# --- Logging ---
log_level_numeric = getattr(logging, LOG_LEVEL, logging.INFO)
logging.basicConfig(format="%(asctime)s - %(name)s [%(levelname)s] - %(message)s", level=log_level_numeric)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.INFO)
# logging.getLogger("telegram._utils.defaultvalue").setLevel(logging.WARNING) # Uncomment to suppress specific lib noise

# --- Startup Logging ---
logger = logging.getLogger(__name__)
logger.info("Config loaded.")
logger.info(f" DB: {DATABASE_FILE} | TZ: {_TZ_STR} ({_TZ_INFO_TYPE}) | LogLevel: {LOG_LEVEL}")
if DEVELOPER_CHAT_ID: logger.info(f" Developer Chat ID: {DEVELOPER_CHAT_ID}")
if RESET_DB_ON_START: logger.warning(" RESET_DB_ON_START enabled!")
if REQUIRED_CHANNEL_IDS: logger.info(f" Required Channels: {REQUIRED_CHANNEL_IDS} | Cache TTL: {CHANNEL_MEMBERSHIP_CACHE_TTL}s")
else: logger.info(" Channel Membership: Disabled")