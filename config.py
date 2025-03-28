import os
import logging
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError # Python 3.9+ zoneinfo
import pytz # Fallback or if zoneinfo isn't sufficient

from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

# --- Core Settings ---
BOT_TOKEN: str | None = os.getenv("BOT_TOKEN")
DATABASE_FILE: str = os.getenv("DATABASE_FILE", "habits_data.db")

# --- Timezone ---
_TZ_STR = os.getenv("USER_TIMEZONE", "UTC")
try:
    # Prefer Python 3.9+'s zoneinfo
    USER_TIMEZONE: ZoneInfo | pytz.BaseTzInfo = ZoneInfo(_TZ_STR)
    _TZ_INFO_TYPE = "zoneinfo"
except ZoneInfoNotFoundError:
    try:
        # Fallback to pytz
        USER_TIMEZONE = pytz.timezone(_TZ_STR)
        _TZ_INFO_TYPE = "pytz"
    except pytz.UnknownTimeZoneError:
        logging.critical(f"Invalid USER_TIMEZONE '{_TZ_STR}'. Using UTC as fallback.")
        USER_TIMEZONE = ZoneInfo("UTC") # or pytz.utc
        _TZ_INFO_TYPE = "zoneinfo (fallback)"

# --- Optional Settings ---
DEVELOPER_CHAT_ID: int | None = int(s) if (s := os.getenv("DEVELOPER_CHAT_ID")) and s.isdigit() else None
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
RESET_DB_ON_START: bool = os.getenv("RESET_DB_ON_START") == "1"


# --- Validation ---
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is not set!")

# --- Logging Configuration ---
# Determine numeric log level
log_level_numeric = getattr(logging, LOG_LEVEL, logging.INFO)

logging.basicConfig(
    format="%(asctime)s - %(name)s [%(levelname)s] - %(message)s",
    level=log_level_numeric
)
# Reduce verbosity of libraries
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.INFO) # Keep INFO for job scheduling visibility

# Initial log messages
logger = logging.getLogger(__name__)
logger.info("Configuration loaded.")
logger.info(f"  Database file: {DATABASE_FILE}")
logger.info(f"  Timezone: {_TZ_STR} (using {_TZ_INFO_TYPE})")
logger.info(f"  Log Level: {LOG_LEVEL}")
if DEVELOPER_CHAT_ID:
    logger.info(f"  Developer Chat ID: {DEVELOPER_CHAT_ID}")
if RESET_DB_ON_START:
    logger.warning("  RESET_DB_ON_START is enabled! Database will be deleted.")
