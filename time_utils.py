# time_utils.py
import dateparser
from dateutil import parser
import time, pytz, datetime as dt
import datetime as dt
import pytz

def parse_when(raw: str, tzname: str):
    raw = normalize_shorthand(raw)
    tz = pytz.timezone(tzname or "UTC")
    now = now_in_tz(tzname)

    # --- Case 1: HHMM (e.g. 2227 → 22:27) ---
    if re.fullmatch(r"\d{4}", raw):
        hour = int(raw[:2])
        minute = int(raw[2:])
        due_dt = tz.localize(dt.datetime(now.year, now.month, now.day, hour, minute))
        if due_dt < now:
            due_dt += dt.timedelta(days=1)
        return int(due_dt.timestamp()), None, None

    # --- Case 2: HH:MM (24h) ---
    if re.fullmatch(r"\d{1,2}:\d{2}", raw):
        hour, minute = map(int, raw.split(":"))
        due_dt = tz.localize(dt.datetime(now.year, now.month, now.day, hour, minute))
        if due_dt < now:
            due_dt += dt.timedelta(days=1)
        return int(due_dt.timestamp()), None, None

    # --- Case 3: 12h with am/pm (e.g. 10pm, 11:30am) ---
    if re.fullmatch(r"\d{1,2}(:\d{2})?\s*(am|pm)", raw.lower()):
        m = re.match(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)", raw.lower())
        hour = int(m.group(1))
        minute = int(m.group(2) or 0)
        ampm = m.group(3)
        if ampm == "pm" and hour != 12:
            hour += 12
        if ampm == "am" and hour == 12:
            hour = 0
        due_dt = tz.localize(dt.datetime(now.year, now.month, now.day, hour, minute))
        if due_dt < now:
            due_dt += dt.timedelta(days=1)
        return int(due_dt.timestamp()), None, None

    # --- Otherwise, fall back to dateparser ---
    settings = {
        "RELATIVE_BASE": now,
        "RETURN_AS_TIMEZONE_AWARE": True,
    }
    if "today" in raw:
        settings["PREFER_DATES_FROM"] = "past"
    else:
        settings["PREFER_DATES_FROM"] = "future"

    dt_parsed = dateparser.parse(raw, settings=settings)
    if not dt_parsed:
        return None, None, None
    return int(dt_parsed.timestamp()), None, None



import re

def normalize_shorthand(raw: str) -> str:
    raw = raw.lower().strip()
    shortcuts = {
        r"\btmr\b": "tomorrow",
        r"\btdy\b": "today",
        r"\btonite\b": "tonight",
        r"\bmon\b": "monday",
        r"\btue\b": "tuesday",
        r"\bwed\b": "wednesday",
        r"\bthu\b": "thursday",
        r"\bfri\b": "friday",
        r"\bsat\b": "saturday",
        r"\bsun\b": "sunday",
    }
    for pat, repl in shortcuts.items():
        raw = re.sub(pat, repl, raw)
    return raw

def now_in_tz(tzname: str):
    tz = pytz.timezone(tzname or "UTC")
    return dt.datetime.now(tz)

