# time_utils.py
from dateutil import parser
import time, pytz, datetime as dt

def parse_when(text, tzname='UTC'):
    try:
        zone = pytz.timezone(tzname)
        dt_local = parser.parse(text, fuzzy=True)
        dt_local = zone.localize(dt_local) if dt_local.tzinfo is None else dt_local.astimezone(zone)
        due_ts = int(dt_local.astimezone(pytz.UTC).timestamp())
        remind_ts = due_ts - 15 * 60
        if remind_ts <= int(time.time()):
            remind_ts = None
        return due_ts, remind_ts, text
    except Exception:
        return None, None, text

def day_bounds(tzname='UTC', when=None):
    zone = pytz.timezone(tzname)
    now_local = dt.datetime.now(zone) if when is None else zone.localize(when)
    start = zone.localize(dt.datetime(now_local.year, now_local.month, now_local.day, 0, 0, 0))
    end = start + dt.timedelta(days=1) - dt.timedelta(seconds=1)
    return int(start.astimezone(pytz.UTC).timestamp()), int(end.astimezone(pytz.UTC).timestamp())
