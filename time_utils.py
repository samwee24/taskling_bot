# time_utils.py
import dateparser
from dateutil import parser
import time, pytz, datetime as dt

def parse_when(raw: str, tzname: str):
    raw = normalize_shorthand(raw)

    settings = {
        "RELATIVE_BASE": now_in_tz(tzname),
        "RETURN_AS_TIMEZONE_AWARE": True,
    }

    # 👇 Key fix: if user explicitly said "today", don’t bump forward
    if "today" in raw:
        settings["PREFER_DATES_FROM"] = "past"
    else:
        settings["PREFER_DATES_FROM"] = "future"

    dt = dateparser.parse(raw, settings=settings)
    if not dt:
        return None, None, None
    return int(dt.timestamp()), None, None


def day_bounds(tzname='UTC', when=None):
    zone = pytz.timezone(tzname)
    now_local = dt.datetime.now(zone) if when is None else zone.localize(when)
    start = zone.localize(dt.datetime(now_local.year, now_local.month, now_local.day, 0, 0, 0))
    end = start + dt.timedelta(days=1) - dt.timedelta(seconds=1)
    return int(start.astimezone(pytz.UTC).timestamp()), int(end.astimezone(pytz.UTC).timestamp())

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

