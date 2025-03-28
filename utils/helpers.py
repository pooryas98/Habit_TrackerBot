# utils/helpers.py

from datetime import datetime, time, date, timedelta, tzinfo
import re
from typing import Optional
import html # <--- ADDED THIS IMPORT

# Import the configured timezone
from config import USER_TIMEZONE

EXAMPLE_TIME_FORMAT = "HH:MM (e.g., 09:00, 17:30)"

def get_today_date() -> date:
    """
    Gets today's date based on the configured USER_TIMEZONE.

    Ensures that 'today' is consistent across the application, regardless
    of the server's local time.

    Returns:
        date: The current date in the specified timezone.
    """
    return datetime.now(USER_TIMEZONE).date()

def parse_reminder_time(time_str: str) -> Optional[time]:
    """
    Parses a time string in HH:MM or H format into a naive time object.

    Args:
        time_str (str): The time string to parse (e.g., "09:30", "17:00", "8").

    Returns:
        Optional[time]: A naive datetime.time object if parsing is successful,
                        otherwise None.
    """
    time_str = time_str.strip()
    # Try HH:MM format first (most specific)
    match_hhmm = re.fullmatch(r"(\d{1,2}):(\d{2})", time_str)
    if match_hhmm:
        try:
            hour, minute = int(match_hhmm.group(1)), int(match_hhmm.group(2))
            # Validate hour and minute ranges
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                return time(hour, minute)
        except ValueError:
            pass # Should not happen with regex, but good to be safe

    # Try H format (e.g., 8 -> 08:00) as a fallback
    match_h = re.fullmatch(r"(\d{1,2})", time_str)
    if match_h:
        try:
            hour = int(match_h.group(1))
            # Validate hour range
            if 0 <= hour <= 23:
                return time(hour, 0) # Assume :00 for single hour input
        except ValueError:
            pass

    return None # Return None if neither format matches or validation fails

def format_time_user_friendly(t: time) -> str:
    """
    Formats a naive time object into a user-friendly HH:MM string.

    Args:
        t (time): The time object to format.

    Returns:
        str: The time formatted as HH:MM (e.g., "09:05").
    """
    return t.strftime("%H:%M")

def format_date_user_friendly(d: date) -> str:
    """
    Formats a date object into a user-friendly string.

    Args:
        d (date): The date object to format.

    Returns:
        str: The date formatted as YYYY-MM-DD. Other formats like
             "%a, %d %b %Y" (e.g., "Mon, 23 Oct 2023") can also be used.
    """
    # Standard ISO format is often clear and sortable
    return d.strftime("%Y-%m-%d")
    # Alternative more verbose format:
    # return d.strftime("%a, %d %b %Y")

# --- ADDED THIS FUNCTION ---
def escape_html(text: Optional[str]) -> str:
    """
    Basic HTML escaping for user-provided text.
    Escapes &, <, and > characters.

    Args:
        text (Optional[str]): The input string.

    Returns:
        str: The escaped string, or an empty string if input is None.
    """
    if text is None:
        return ""
    # Convert to string just in case something else was passed
    # Use html.escape which is the standard library function
    return html.escape(str(text))
# --- END ADDED FUNCTION ---