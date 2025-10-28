# bot.py (Taskling theme)
import os, time, re
from datetime import datetime, timedelta
import pytz
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, ContextTypes,
    MessageHandler, CallbackQueryHandler, filters
)
from time_utils import parse_when  # add this import at the top of bot.py
import random
import db
import scheduler
from dotenv import load_dotenv
import asyncio
import time
from datetime import datetime
import dateparser

load_dotenv()
# Track chats waiting for confirmation
pending_clear = set()

PACIFIC = pytz.timezone("US/Pacific")

NAMES = [
    "Grizzle","Nyra","Fenn","Korra","Thistle","Brakk","Elowen","Drix","Veyra","Tumble",
    "Kaelen","Mosswick","Orin","Zephyra","Quill","Bramble","Liora","Korrin","Sylas","Tindra",
    "Jaxen","Myrrh","Oaken","Vesper","Thrain","Poppy","Eryndor","Calyx","Nimra","Toren",
    "Wisp","Bront","Lyric","Fenwick","Astra","Korril","Dapple","Soren","Thistlewick","Ember",
    "Veylin","Rune","Marrow","Solen","Kithra","Bram","Elric","Nyx","Willow","Tarn",
    "Cindrel","Pyra","Jorah","Faelan","Mistral","Korrick","Lumen","Brisa","Thorn","Drogan",
    "Isolde","Quorra","Branik","Elira","Tovan","Mirelle","Garrick","Zephyr","Corin","Thalor",
    "Oryn","Kaelith","Tamsin","Fenric","Sylric","Torwyn","Nythera","Quenric","Mossra","Branth",
    "Eloweth","Torrick","Lysandra","Korrath","Sylwenna"
]

ROLES = [
    "Shieldbearer","Scout","Mage","Banner‑carrier","Scribe","Beastmaster","Pathfinder","Alchemist",
    "Tactician","Seer","Blade‑dancer","Runesmith","Torchbearer","Watcher","Herald","Trickster",
    "Lorekeeper","Vanguard","Whisperer","Stormcaller","Healer","Shadowblade","Stoneguard","Flamekeeper",
    "Sky‑rider","Druid","Songweaver","Ironfist","Moon‑priest","Sun‑warden","Star‑seer","Battle‑chanter",
    "Rune‑carver","Beast‑rider","Shield‑singer","Storm‑bringer","Ember‑mage","Frost‑warden","Thorn‑knight",
    "Spirit‑caller","Dream‑weaver","Shadow‑hunter","Flame‑dancer","Wind‑scout","Tide‑watcher","Earth‑shaper",
    "Light‑bearer","Night‑stalker","Dawn‑bringer","Mist‑walker","Sky‑seer","Bone‑carver","Iron‑sentinel",
    "Crystal‑seer","Grove‑warden","Storm‑singer","Ember‑smith","Rune‑warden","Spirit‑guide"
]

ENEMIES = [
    ("Goblin Sneak", 2),
    ("Shadow Wraith", 4),
    ("Stone Golem", 6),
    ("Fire Drake", 8),
    ("Chaos Hydra", 12),
    ("Doom Titan", 20)
]


# --- Squad Ranks ---
RANKS = [
    (0, "🎭 Recruit"),
    (5, "👥 Squad"),
    (10, "🛡️ Captain"),
    (20, "⚔️ Legion"),
]

def day_bounds(tzname):
    tz = pytz.timezone(tzname or "UTC")
    now = datetime.now(tz)
    start = datetime(now.year, now.month, now.day, 0, 0, 0, tzinfo=tz)
    end = start + timedelta(days=1) - timedelta(seconds=1)
    return int(start.timestamp()), int(end.timestamp())

from datetime import datetime, timedelta

import time
from datetime import datetime
import dateparser

import re
from datetime import datetime, timedelta
import dateparser
import pytz  # ensure you have pytz installed

def parse_when_preview(raw: str, tzname: str):
    """Preview parse result without converting, used by splitter."""
    raw = normalize_shorthand(raw)

    settings = {
        "RELATIVE_BASE": now_in_tz(tzname),
        "RETURN_AS_TIMEZONE_AWARE": True,
    }

    # If the user explicitly said "today", force today’s date
    if "today" in raw:
        settings["PREFER_DATES_FROM"] = "past"   # don’t bump forward
    else:
        settings["PREFER_DATES_FROM"] = "future"

    dt = dateparser.parse(raw, settings=settings)

    return dt

def parse_time_date(time_str, date_str, tzname):
    tz = pytz.timezone(tzname or "UTC")
    now = datetime.now(tz)

    # --- Parse time ---
    hour, minute = None, 0

    # Case 1: HHMM (e.g. 1845)
    if time_str.isdigit() and len(time_str) == 4:
        hour = int(time_str[:2])
        minute = int(time_str[2:])

    # Case 2: HH:MM (24h)
    elif re.fullmatch(r"\d{1,2}:\d{2}", time_str):
        hour, minute = map(int, time_str.split(":"))

    # Case 3: 12h with am/pm (5pm, 6am, 11:30pm)
    elif re.fullmatch(r"\d{1,2}(:\d{2})?\s*(am|pm)", time_str.lower()):
        m = re.match(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)", time_str.lower())
        hour = int(m.group(1))
        minute = int(m.group(2) or 0)
        ampm = m.group(3)
        if ampm == "pm" and hour != 12:
            hour += 12
        if ampm == "am" and hour == 12:
            hour = 0

    else:
        return None  # invalid time

    # --- Parse date ---
    year, month, day = now.year, now.month, now.day
    if date_str:
        if date_str.isdigit() and len(date_str) == 6:
            day = int(date_str[:2])
            month = int(date_str[2:4])
            year = 2000 + int(date_str[4:])
        elif date_str.lower() in ("tomorrow", "tmr"):
            tomorrow = now + timedelta(days=1)
            year, month, day = tomorrow.year, tomorrow.month, tomorrow.day
        elif date_str.lower() == "today":
            pass  # already today
        # (Optional: add weekday parsing here)

    due_dt = tz.localize(datetime(year, month, day, hour, minute))

    # If the time has already passed today and no explicit date was given, push to tomorrow
    if not date_str and due_dt < now:
        due_dt += timedelta(days=1)

    return int(due_dt.timestamp())

    # Fallback: HHMM [DDMMYY]
    parts = raw.split()
    if parts and parts[0].isdigit() and len(parts[0]) == 4:
        hour = int(parts[0][:2]); minute = int(parts[0][2:])
        if len(parts) > 1 and parts[1].isdigit() and len(parts[1]) == 6:
            day = int(parts[1][:2]); month = int(parts[1][2:4]); year = 2000 + int(parts[1][4:])
            due_dt = localized_dt(year, month, day, hour, minute, tzname)
        else:
            base = now_in_tz(tzname)
            due_dt = localized_dt(base.year, base.month, base.day, hour, minute, tzname)
        return int(due_dt.timestamp()), None, None

    return None, None, None

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
    return datetime.now(tz)

def localized_dt(y, m, d, h, mi, tzname):
    tz = pytz.timezone(tzname or "UTC")
    return tz.localize(datetime(y, m, d, h, mi))


def rank_for(points: int) -> str:
    current = RANKS[0][1]
    for threshold, label in RANKS:
        if points >= threshold:
            current = label
        else:
            break
    return current

def speak(text: str) -> str:
    tags = ["🎭", "👾", "👥", "🛡️", "⚔️"]
    return f"{tags[int(time.time()) % len(tags)]} {text}"

# --- Command Handlers ---

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Onboarding message when a user first starts the bot."""
    chat_id = update.effective_chat.id
    db.init_db()
    db.ensure_growth_row(chat_id)

    intro_text = (
        "🎭 Greetings, Commander Tan! I am Taskling — your masked helper.\n\n"
        "Here’s how our adventure works:\n"
        "• Use /add or /remind to assign *missions* (your real‑world tasks).\n"
        "• When you complete a mission, mark it with /done — and a new Taskling will join your squad!\n"
        "• Each night you’ll receive a 📜 Daily Debrief with your victories, streak, and morale.\n"
        "• Fail to act, and morale drops… but rally your squad and you’ll rise in rank.\n"
        "• Beware: 👹 random enemies may appear. Your squad’s strength and morale decide the outcome.\n\n"
        "Type /help anytime for the full command guide.\n\n"
        "Now, commander — what is our first mission?"
    )

    await update.message.reply_text(intro_text, parse_mode="Markdown")

    # Schedule daily debrief + other jobs for this chat
    schedule_for_chat = scheduler.schedule_daily_debrief(context.application)
    schedule_for_chat(chat_id)
    scheduler.schedule_random_encouragements(context.application, chat_id, count=3)
    scheduler.schedule_daily_briefings(context.application, chat_id)
    scheduler.schedule_enemy_spawns(context.application, chat_id, count=2)


def split_task_and_when(args, tzname):
    """Return (task_text, when_str) using the longest parsable suffix."""
    best = (None, None)
    for i in range(1, len(args) + 1):
        task_text = " ".join(args[:-i]).strip()
        when_str = " ".join(args[-i:]).strip()
        if parse_when_preview(when_str, tzname) is not None:
            best = (task_text, when_str)
    return best

async def add_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add a new mission with a due time/date."""
    chat_id = update.effective_chat.id
    if len(context.args) < 2:
        await update.message.reply_text(speak("Usage: /add <task> <time> [date]"))
        return

    sh, tzname = db.get_prefs(chat_id)

    # 👇 Use the same smart splitter as /remind
    task_text, when_str = split_task_and_when(context.args, tzname)

    if not task_text or not when_str:
        await update.message.reply_text(
            speak("Could not parse time/date. Try formats like '1700', '09:30', '5pm', 'tomorrow 7am', or '28 Oct 14:00'.")
        )
        return

    # Break into time/date parts
    parts = when_str.split()
    if len(parts) == 2:
        time_str, date_str = parts
    else:
        time_str, date_str = parts[0], None

    due_ts = parse_time_date(time_str, date_str, tzname)

    if not due_ts:
        await update.message.reply_text(
            speak("Could not parse time/date. Try formats like '1700', '09:30', '5pm', 'tomorrow 7am', or '28 Oct 14:00'.")
        )
        return

    # Save to DB
    db.add_task(chat_id, task_text, due_ts)
    PACIFIC = pytz.timezone("US/Pacific")
    local_time = datetime.fromtimestamp(due_ts, PACIFIC).strftime("%Y-%m-%d %H:%M")
    await update.message.reply_text(speak(f"Mission added: {task_text} at {local_time}"))


async def remind_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not context.args:
        await update.message.reply_text(speak("Usage: /remind <task> <time/date>"))
        return

    sh, tzname = db.get_prefs(chat_id)

    # split_task_and_when returns (task_text, when_str)
    task_text, when_str = split_task_and_when(context.args, tzname)

    # Parse the when_str into an integer timestamp
    due_ts, _, _ = parse_when(when_str, tzname)

    print("DEBUG /remind → due_ts:", due_ts, type(due_ts), "when_str:", when_str)

    if not due_ts or not task_text:
        await update.message.reply_text(
            speak("Could not parse time/date. Use HHMM, HHMM DDMMYY, or natural language like 'tomorrow 5pm'.")
        )
        return

    # Reminder time = due_ts as well (you can adjust if you want offset reminders)
    tid = db.add_task(chat_id, task_text, due_ts, due_ts)
    local_time = datetime.fromtimestamp(due_ts, PACIFIC).strftime("%Y-%m-%d %H:%M")
    await update.message.reply_text(speak(f"I’ll sound the horn for: {task_text} at {local_time}. Mission ID {tid}."))

async def summary_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    sh, tzname = db.get_prefs(chat_id)
    now = int(time.time())

    conn = db.get_conn()
    rows = conn.execute(
        """
        SELECT id, text, due_ts, status
        FROM tasks
        WHERE chat_id=? 
          AND due_ts IS NOT NULL
          AND (status IS NULL OR status!='done')
        ORDER BY due_ts ASC
        """,
        (chat_id,)
    ).fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text(speak("No missions on the horizon. The squad rests."))
        return

    grouped = {}
    for tid, text, due_ts, status in rows:
        due_ts = int(due_ts)
        date_str = datetime.fromtimestamp(due_ts, PACIFIC).strftime("%Y-%m-%d")
        time_str = datetime.fromtimestamp(due_ts, PACIFIC).strftime("%H:%M")
        is_overdue = due_ts < now
        grouped.setdefault(date_str, []).append((time_str, text, is_overdue, due_ts))

    today_str = datetime.now(PACIFIC).strftime("%Y-%m-%d")
    tomorrow_str = (datetime.now(PACIFIC) + timedelta(days=1)).strftime("%Y-%m-%d")

    parts = []
    for i, date_str in enumerate(sorted(grouped.keys())):
        if i > 0:
            parts.append("\n")

        if date_str == today_str:
            parts.append(f"🌟 TODAY ({date_str})")
        elif date_str == tomorrow_str:
            parts.append(f"🌙 TOMORROW ({date_str})")
        else:
            parts.append(f"📅 {date_str}")

        for time_str, text, is_overdue, due_ts in grouped[date_str]:
            delta = due_ts - now
            if is_overdue:
                marker = "⚠️"
            elif delta < 3600:
                marker = "🔥"
            else:
                marker = "•"
            parts.append(f"{marker} {time_str} — {text}")

    msg = "\n".join(parts)
    await update.message.reply_text(speak(msg))

async def done_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    now = int(time.time())
    start = now - (now % 86400)
    end = start + 86400
    tasks = db.list_tasks_for_day(chat_id, start, end)

    if not tasks:
        await update.message.reply_text("No pending missions today.")
        return

    keyboard = [
        [InlineKeyboardButton(f"{tid}: {text}", callback_data=f"done:{tid}")]
        for tid, text, _, _ in tasks
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Select a mission to mark as complete:", reply_markup=reply_markup)

async def delete_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    now = int(time.time())
    start = now - (now % 86400)
    end = start + 86400
    tasks = db.list_tasks_for_day(chat_id, start, end)

    if not tasks:
        await update.message.reply_text("No pending missions to delete.")
        return

    keyboard = [
        [InlineKeyboardButton(f"{tid}: {text}", callback_data=f"delete:{tid}")]
        for tid, text, _, _ in tasks
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Select a mission to delete:", reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    action, tid_str = query.data.split(":")
    tid = int(tid_str)

    if action in ("done", "due_done"):
        ok = db.mark_done(chat_id, tid)
        db.remap_task_ids()
        if ok:
            recruit, role = recruit_taskling(chat_id)
            await context.bot.send_message(
                chat_id=chat_id,
                text=speak(f"🎉 Well done, Phoebe! Taskling {recruit} the {role} has joined your squad.")
            )
            msg = f"Mission #{tid} marked complete!"
        else:
            msg = "Could not find that mission."
    elif action == "delete":
        ok = db.delete_task(chat_id, tid)
        db.remap_task_ids()
        msg = f"Mission #{tid} deleted." if ok else "Could not find that mission."
    elif action == "due_notdone":
        # Snooze: push due_ts forward 15 minutes
        conn = db.get_conn()
        conn.execute("UPDATE tasks SET due_ts = due_ts + 900 WHERE id=? AND chat_id=?", (tid, chat_id))
        conn.commit()
        conn.close()
        msg = f"Mission #{tid} snoozed for 15 minutes. Stay vigilant!"
    elif action == "resched":
        context.user_data["resched_tid"] = tid
        msg = (
            f"Mission #{tid} selected for reschedule.\n"
            "Reply with a new time (HHMM, HHMM DDMMYY, or natural language like 'tomorrow 5pm')."
        )
    elif action == "del_overdue":
        ok = db.delete_task(chat_id, tid)
        db.remap_task_ids()
        msg = f"Mission #{tid} deleted." if ok else "Could not find that mission."
    else:
        msg = "Unknown action."

    await query.edit_message_text(msg)

async def squad_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        chat_id = update.effective_chat.id
        points, streak, morale = db.get_growth(chat_id)
        rank = rank_for(points)

        # Fetch squad members
        squad = db.list_squad(chat_id)

        # Build squad roster text
        if squad:
            roster_lines = [f"• {name} the {role}" for name, role in squad]
            roster_text = "\n".join(roster_lines)
        else:
            roster_text = "No Tasklings recruited yet. Complete missions to grow your squad!"

        msg = (
            f"📊 Squad Status for Phoebe\n"
            f"Rank: {rank}\n"
            f"Recruits: {points}\n"
            f"Streak: {streak} days\n"
            f"Morale: {morale}/10\n\n"
            f"🧑‍🤝‍🧑 Current Tasklings:\n{roster_text}"
        )

        await update.message.reply_text(speak(msg))

    except Exception as e:
        await update.message.reply_text(speak(f"Error in /squad: {e}"))

def recruit_taskling(chat_id):
    # Get all existing squad members for this chat
    existing = db.list_squad(chat_id)
    existing_names = {name for name, role in existing}

    # Pick a name not already used
    available_names = [n for n in NAMES if n not in existing_names]
    if not available_names:
        # If all names used, recycle
        available_names = NAMES

    recruit = random.choice(available_names)
    role = random.choice(ROLES)

    # Save to DB
    db.add_squad_member(chat_id, recruit, role)
    return recruit, role

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Detailed command reference with a short 'how it works' preface."""
    help_text = (
        "🎭 *Taskling Command Guide*\n\n"
        "⚔️ *How it works:*\n"
        "- Add missions with /add or /remind.\n"
        "- Complete missions with /done to recruit Tasklings.\n"
        "- Check your squad’s status with /squad.\n"
        "- Each night you’ll receive a Daily Debrief.\n"
        "- Stay active to keep morale high and defeat enemies!\n\n"
        "*Available commands:*\n"
        "/start – Begin your adventure\n"
        "/help – Show this guide\n\n"
        "/add <task> <time> [date] – Add a new mission\n"
        "   Time formats: HHMM, HH:MM, or 12h with am/pm (e.g. 1700, 09:30, 5pm)\n"
        "   Date formats: DDMMYY, 'today', 'tomorrow' (default is today)\n"
        "   e.g. /add Finish report 1700\n"
        "   e.g. /add Homework 07:30 tomorrow\n\n"
        "/remind <task> <time> [date] – Add a mission with a reminder\n"
        "   e.g. /remind Call mom 1900\n"
        "   e.g. /remind Meeting 09:00 tomorrow\n\n"
        "/summary – Show all missions grouped by date (⚠️ overdue)\n"
        "/done – Mark a mission complete (choose from a list)\n"
        "/delete – Remove a mission completely (choose from a list)\n"
        "/reschedule – Select a mission to reschedule, then reply with a new time/date\n"
        "/clear\\_all – Wipe all missions for today’s squad\n"
        "/squad – Show your current Taskling squad status\n"
        "/reset\\_chat – Reset everything for a fresh start\n"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def remap_ids_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db.remap_task_ids()
    await update.message.reply_text(speak("Mission IDs have been renumbered from 1."))

async def clear_all_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    pending_clear.add(chat_id)
    await update.message.reply_text(
        speak("Are you sure you want to wipe all missions? "
              "Type /confirm_clear to proceed or ignore to cancel.")
    )

async def confirm_clear_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in pending_clear:
        await update.message.reply_text(speak("No pending clear request."))
        return

    count = db.clear_all_tasks(chat_id)
    db.remap_task_ids()
    pending_clear.remove(chat_id)

    if count > 0:
        await update.message.reply_text(speak(f"All {count} missions have been cleared. The slate is clean."))
    else:
        await update.message.reply_text(speak("No missions to clear. The squad rests."))

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text.strip()

    # If we're in reschedule mode
    if "resched_tid" in context.user_data:
        tid = context.user_data.pop("resched_tid")
        sh, tzname = db.get_prefs(chat_id)

        # Split the reply into task_text (ignored here) and due_ts
        _, due_ts = split_task_and_when(update.message.text.split(), tzname)

        if not due_ts:
            await update.message.reply_text(
                speak("Could not parse that time/date. Use HHMM, HHMM DDMMYY, or natural language like 'tomorrow 5pm'.")
            )
            return

        conn = db.get_conn()
        conn.execute("UPDATE tasks SET due_ts=? WHERE id=? AND chat_id=?", (due_ts, tid, chat_id))
        conn.commit()
        conn.close()

        local_time = datetime.fromtimestamp(due_ts, PACIFIC).strftime("%Y-%m-%d %H:%M")
        await update.message.reply_text(speak(f"Mission #{tid} rescheduled to {local_time}."))
        return

    # Otherwise, fall back to intro
    await update.message.reply_text(
        "🎭 Welcome! I’m Taskling, your masked helper.\n"
        "Type /start to begin your adventure, or use /help to see commands."
    )

async def reschedule_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    now = int(time.time())

    # Get all active tasks
    conn = db.get_conn()
    rows = conn.execute(
        """
        SELECT id, text, due_ts, status
        FROM tasks
        WHERE chat_id=? 
          AND due_ts IS NOT NULL
          AND (status IS NULL OR status!='done')
        ORDER BY due_ts ASC
        """,
        (chat_id,)
    ).fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text(speak("No missions available to reschedule."))
        return

    # Build inline keyboard
    keyboard = [
        [InlineKeyboardButton(f"{datetime.fromtimestamp(due_ts, PACIFIC).strftime('%Y-%m-%d %H:%M')} — {text}",
                              callback_data=f"resched:{tid}")]
        for tid, text, due_ts, status in rows
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Select a mission to reschedule:", reply_markup=reply_markup)

async def reset_chat_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    # Clear tasks
    db.clear_all_tasks(chat_id)

    # Clear squad
    conn = db.get_conn()
    conn.execute("DELETE FROM squad WHERE chat_id=?", (chat_id,))
    conn.execute("DELETE FROM growth WHERE chat_id=?", (chat_id,))
    conn.commit()
    conn.close()

    # Re‑initialize growth row so the bot doesn’t break
    db.ensure_growth_row(chat_id)

    await update.message.reply_text(
        speak("All memory for this chat has been reset. Fresh start, commander!")
    )



def inject_notify(app):
    import asyncio
    loop = asyncio.get_event_loop()

    async def _notify(chat_id, payload):
        if isinstance(payload, str):
            await app.bot.send_message(chat_id=chat_id, text=speak(payload))
        else:
            await app.bot.send_message(
                chat_id=chat_id,
                text=speak(payload["text"]),
                reply_markup=payload.get("reply_markup")
            )

    def threadsafe_notify(chat_id, payload):
        asyncio.run_coroutine_threadsafe(_notify(chat_id, payload), loop)

    scheduler.notify = threadsafe_notify

# --- Main entrypoint ---
def main():
    db.init_db()
    token = os.environ["TELEGRAM_TOKEN"]
    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("add", add_cmd))
    app.add_handler(CommandHandler("remind", remind_cmd))
    app.add_handler(CommandHandler("summary", summary_cmd))
    app.add_handler(CommandHandler("squad", squad_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("done", done_cmd))
    app.add_handler(CommandHandler("delete", delete_cmd))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(CommandHandler("remap_ids", remap_ids_cmd))
    app.add_handler(CommandHandler("clear_all", clear_all_cmd))
    app.add_handler(CommandHandler("confirm_clear", confirm_clear_cmd))
    app.add_handler(CommandHandler("reschedule", reschedule_cmd))
    app.add_handler(CommandHandler("reset_chat", reset_chat_cmd))

    inject_notify(app)
    scheduler.start()
    scheduler.app_ref = app

    app.run_polling()

if __name__ == "__main__":
    main()
