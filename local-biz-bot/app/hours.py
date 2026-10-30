"""
hours.py - work out "are you open right now?" in code.

LLMs are bad at dates and time zones, so we calculate the answer here
and hand the LLM a ready-made sentence.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

from app.profile import BusinessProfile


def to_minutes(hhmm):
    """'08:30' -> 510"""
    hours, minutes = hhmm.split(":")
    return int(hours) * 60 + int(minutes)


def open_now_status(profile: BusinessProfile):
    """Return a sentence about whether the business is open now, or "" if hours are unknown."""
    if not profile.hours or not profile.timezone:
        return ""
    try:
        now = datetime.now(ZoneInfo(profile.timezone))
    except Exception:  # unknown time zone name
        return ""

    today = now.strftime("%A").lower()
    now_text = f"Right now it is {now:%A %H:%M} at the business"

    for h in profile.hours:
        if h.day.lower() == today:
            if to_minutes(h.open) <= now.hour * 60 + now.minute < to_minutes(h.close):
                return f"{now_text}. The business is OPEN now (closes at {h.close})."
            return f"{now_text}. The business is CLOSED now (today's hours: {h.open}-{h.close})."
    return f"{now_text}. The business is CLOSED today."
