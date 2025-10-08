import logging
import pytz
from zoneinfo import ZoneInfo
from typing import List, Optional, Union
from pydantic_settings import BaseSettings
from pydantic import field_validator, computed_field


class Settings(BaseSettings):
    # Core
    bot_token: str
    database_file: str = "habits_data.db"
    
    # Timezone
    user_timezone: str = "UTC"
    
    # Optional
    developer_chat_id: Optional[int] = None
    log_level: str = "INFO"
    reset_db_on_start: bool = False
    
    @field_validator('reset_db_on_start', mode='before')
    @classmethod
    def validate_reset_db_on_start(cls, v) -> bool:
        if isinstance(v, bool):
            return v
        if v is None or v == "":
            return False
        return str(v).lower() in ('1', 'true', 'yes', 'on')
    
    @field_validator('developer_chat_id', mode='before')
    @classmethod
    def validate_developer_chat_id(cls, v) -> Optional[int]:
        if v is None or v == "":
            return None
        try:
            return int(v)
        except (TypeError, ValueError):
            logging.getLogger(__name__).warning(f"Invalid DEVELOPER_CHAT_ID '{v}', setting to None")
            return None
    
    # Channel Membership
    required_channel_ids: str = ""
    channel_membership_cache_ttl: int = 300
    
    @field_validator('channel_membership_cache_ttl', mode='before')
    @classmethod
    def validate_channel_membership_cache_ttl(cls, v) -> int:
        if v is None or v == "":
            return 300
        try:
            return int(v)
        except (TypeError, ValueError):
            logging.getLogger(__name__).warning(f"Invalid CHANNEL_MEMBERSHIP_CACHE_TTL '{v}', using default 300")
            return 300
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8"
    }
    
    @computed_field
    @property
    def user_timezone_obj(self) -> Union[ZoneInfo, pytz.BaseTzInfo]:
        """Computed field that returns a timezone object based on the user_timezone string."""
        try:
            return ZoneInfo(self.user_timezone)
        except Exception:
            try:
                return pytz.timezone(self.user_timezone)
            except Exception:
                logging.getLogger(__name__).critical(
                    f"Invalid timezone '{self.user_timezone}'. Using UTC."
                )
                return ZoneInfo("UTC")
    
    @computed_field
    @property
    def required_channel_ids_list(self) -> List[Union[str, int]]:
        """Computed field that parses the channel IDs string into a list."""
        result: List[Union[str, int]] = []
        if self.required_channel_ids:
            for item in self.required_channel_ids.split(','):
                item = item.strip()
                if not item:
                    continue
                if item.startswith('@'):
                    result.append(item)
                else:
                    try:
                        result.append(int(item))
                    except ValueError:
                        logging.getLogger(__name__).warning(f"Ignoring invalid channel ID: '{item}'")
        return result
    
    @field_validator('log_level')
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        return v.upper()


# Create the settings instance - this will load from .env file
settings = Settings()

# Validate that BOT_TOKEN is present
if not settings.bot_token:
    raise ValueError("FATAL: BOT_TOKEN env var not set!")

# Apply library logging levels
import logging
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.INFO)

# Log startup information
log = logging.getLogger(__name__)
tz_type = "zoneinfo" if isinstance(settings.user_timezone_obj, ZoneInfo) else "pytz"
log.info(f"Cfg: DB={settings.database_file}, TZ={settings.user_timezone}({tz_type}), Log={settings.log_level.upper()}")
if settings.developer_chat_id:
    log.info(f" DevID: {settings.developer_chat_id}")
if settings.reset_db_on_start:
    log.warning(" RESET_DB_ON_START ENABLED!")
log.info(f" ChanLock: {'ON' if settings.required_channel_ids else 'OFF'} " +
         (f"(Chs:{settings.required_channel_ids_list}, TTL:{settings.channel_membership_cache_ttl}s)" 
          if settings.required_channel_ids_list else ""))