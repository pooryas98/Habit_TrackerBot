from datetime import datetime, time, date, timedelta, tzinfo
import re
from typing import Optional

# Import the configured timezone
from config import USER_TIMEZONE

EXAMPLE_TIME_FORMAT = "HH:MM (e.g., 09:00, 17:30)"

def get_today_date() -> date:
    """Gets today's date in the bot's configured USER_TIMEZONE."""
    # Ensure we get 'today' based on the configured timezone, not server's local time
    return datetime.now(USER_TIMEZONE).date()

def parse_reminder_time(time_str: str) -> Optional[time]:
    """Parses HH:MM or H:MM format. Returns naive time object."""
    time_str = time_str.strip()
    # Try HH:MM format
    match = re.fullmatch(r"(\d{1,2}):(\d{2})", time_str)
    if match:
        try:
            hour, minute = int(match.group(1)), int(match.group(2))
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                return time(hour, minute)
        except ValueError:
            pass # Should not happen with regex, but be safe

    # Try H format (e.g., 8 -> 08:00) - Less reliable, requires user understanding
    match_h = re.fullmatch(r"(\d{1,2})", time_str)
    if match_h:
        try:
            hour = int(match_h.group(1))
            if 0 <= hour <= 23:
                return time(hour, 0) # Default to :00
        except ValueError:
            pass

    return None # Failed to parse

def format_time_user_friendly(t: time) -> str:
    """Formats time into HH:MM."""
    return t.strftime("%H:%M")

def format_date_user_friendly(d: date) -> str:
    """Formats date into YYYY-MM-DD or a more friendly format if desired."""
    # Example: return d.strftime("%a, %d %b %Y") # e.g., "Mon, 23 Oct 2023"
    return d.strftime("%Y-%m-%d") # Standard ISO format often clearest

