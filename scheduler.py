# scheduler.py (Taskling theme with debug logging)

# --- Standard library ---
import time
import asyncio
from datetime import datetime, timedelta

# --- Third-party libraries ---
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

PACIFIC = pytz.timezone("US/Pacific")

# --- Local modules ---
import db
from bot import speak, rank_for

scheduler = BackgroundScheduler()
notify = lambda chat_id, msg: None  # injected from bot.py

import random

ENCOURAGEMENTS = [
    "💪 Stay strong, Phoebe — the squad believes in you!",
    "⚔️ Every mission you complete is another victory for the Tasklings, Phoebe.",
    "🛡️ Don’t let the day slip away — rally your squad, Phoebe!",
    "👾 Even small steps keep the march alive, Phoebe.",
    "🎭 The Tasklings await your command, Phoebe. Let’s conquer one mission now!"
]

# --- Global scheduler start ---
def start():
    scheduler.start()
    scheduler.add_job(check_reminders, IntervalTrigger(seconds=30))
    scheduler.add_job(check_due, IntervalTrigger(seconds=30))
    scheduler.add_job(apply_daily_decay, IntervalTrigger(hours=24))
    print("⚙️ Scheduler started with jobs: reminders, due, decay")

# --- Random encouragements ---
def schedule_random_encouragements(app, chat_id, count=3):
    loop = asyncio.get_event_loop()

    async def encouragement():
        now = int(time.time())
        start = now - (now % 86400)
        end = start + 86400
        tasks = db.list_tasks_for_day(chat_id, start, end)
        done = sum(1 for _, _, _, status in tasks if status == "done")

        if done == 0:
            msg = f"Phoebe, the squad is restless — let’s rally for our first victory today!"
        elif done >= len(tasks) // 2:
            msg = f"Phoebe, you’re leading well — only {len(tasks)-done} missions remain!"
        else:
            msg = random.choice(ENCOURAGEMENTS)

        await app.bot.send_message(chat_id=chat_id, text=speak(msg))

    now = datetime.now()
    end_of_day = datetime(now.year, now.month, now.day, 23, 59)

    for i in range(count):
        delta_seconds = int((end_of_day - now).total_seconds())
        trigger_time = now + timedelta(seconds=random.randint(600, delta_seconds))

        scheduler.add_job(
            lambda: loop.create_task(encouragement()),
            DateTrigger(run_date=trigger_time),
            id=f"encouragement_{chat_id}_{i}_{trigger_time.hour}_{trigger_time.minute}",
            replace_existing=False
        )
        print(f"[DEBUG] Scheduled random encouragement for chat {chat_id} at {trigger_time}")


# --- Daily briefings (morning/midday/evening) ---
def schedule_daily_briefings(app, chat_id):
    loop = asyncio.get_event_loop()

    async def briefing(kind):
        now = int(time.time())
        start = now - (now % 86400)
        end = start + 86400
        tasks = db.list_tasks_for_day(chat_id, start, end)
        total = len(tasks)
        done = sum(1 for _, _, _, status in tasks if status == "done")
        rank = rank_for(db.get_growth(chat_id)[0])

        if kind == "morning":
            msg = f"🌅 Morning briefing, Phoebe: {total} missions today. Current rank: {rank}."
        elif kind == "midday":
            msg = f"⚔️ Midday check‑in, Phoebe: {done}/{total} missions complete."
        elif kind == "evening":
            msg = f"🛡️ Evening rally, Phoebe: {total - done} missions remain. Stay sharp!"

        await app.bot.send_message(chat_id=chat_id, text=speak(msg))

    # 👇 pull timezone from prefs
    summary_hour, tzname = db.get_prefs(chat_id)
    tz = pytz.timezone(tzname or "UTC")

    scheduler.add_job(lambda: loop.create_task(briefing("morning")),
                      CronTrigger(hour=9, minute=0, timezone=tz),
                      id=f"briefing_morning_{chat_id}", replace_existing=True)

    scheduler.add_job(lambda: loop.create_task(briefing("midday")),
                      CronTrigger(hour=13, minute=0, timezone=tz),
                      id=f"briefing_midday_{chat_id}", replace_existing=True)

    scheduler.add_job(lambda: loop.create_task(briefing("evening")),
                      CronTrigger(hour=18, minute=0, timezone=tz),
                      id=f"briefing_evening_{chat_id}", replace_existing=True)

    scheduler.add_job(reset_daily_encouragements,
                      CronTrigger(hour=0, minute=5, timezone=tz),
                      id=f"reset_encouragements_{chat_id}", replace_existing=True)

    print(f"[DEBUG] Scheduled daily briefings for chat {chat_id} in {tzname}")

# --- Nightly debrief (23:59) ---
def schedule_daily_debrief(app):
    loop = asyncio.get_event_loop()

    async def daily_debrief(chat_id):
        now = int(time.time())
        start = now - (now % 86400)
        end = start + 86400

        tasks = db.list_tasks_for_day(chat_id, start, end)
        total = len(tasks)
        done = sum(1 for _, _, _, status in tasks if status == "done")

        points, streak, morale = db.get_growth(chat_id)
        rank = rank_for(points)

        msg = (
            f"📜 Daily Debrief for Phoebe ({datetime.now().strftime('%Y-%m-%d')})\n"
            f"Completed: {done}/{total} missions\n"
            f"Current Rank: {rank}\n"
            f"Streak: {streak} days | Morale: {morale}/10\n"
        )
        if total > 0 and done == total:
            msg += "🎉 Perfect day, Phoebe! The squad celebrates your leadership."
        elif done > 0:
            msg += "💪 Progress made, Phoebe. Tomorrow we march again."
        else:
            msg += "😴 No missions completed today, Phoebe. The squad rests uneasily…"
            db.daily_decay(chat_id)
            msg += "\n⚠️ With no victories today, your Tasklings grow weary and vulnerable."

        if morale <= 3:
            msg += "\n😔 Phoebe, the squad’s morale is low. Even one mission tomorrow will lift their spirits."
        elif morale >= 9:
            msg += "\n🔥 Phoebe, the Tasklings are jubilant — your leadership is legendary."

        await app.bot.send_message(chat_id=chat_id, text=speak(msg))

    def schedule_for_chat(chat_id):
        summary_hour, tzname = db.get_prefs(chat_id)
        tz = pytz.timezone(tzname or "UTC")

        scheduler.add_job(
            lambda: loop.create_task(daily_debrief(chat_id)),
            CronTrigger(hour=summary_hour, minute=0, timezone=tz),
            id=f"daily_debrief_{chat_id}",
            replace_existing=True
        )
        print(f"[DEBUG] Scheduled daily debrief for chat {chat_id} at {summary_hour}:00 {tzname}")

    return schedule_for_chat

def reset_daily_encouragements():
    print(f"[DEBUG] Resetting daily encouragements at {time.ctime()}")
    conn = db.get_conn()
    chats = [row[0] for row in conn.execute("SELECT chat_id FROM growth").fetchall()]
    conn.close()

    for chat_id in chats:
        # Clear old encouragement jobs for this chat
        for job in scheduler.get_jobs():
            if job.id.startswith(f"encouragement_{chat_id}_"):
                scheduler.remove_job(job.id)

        # Re‑schedule new random encouragements
        # Note: we need the app instance, so we pass it via notify injection
        # or store it globally when /start runs
        if hasattr(scheduler, "app_ref"):
            schedule_random_encouragements(scheduler.app_ref, chat_id, count=3)

# --- Reminder & due checks ---
def check_reminders():
    now = int(time.time())
    window = now + 120
    rows = db.remind_tasks_between(now, window)
    print(f"[DEBUG] check_reminders at {time.ctime(now)} → {len(rows)} tasks in window")
    for tid, chat_id, text, remind_ts in rows:
        print(f"[DEBUG] Sending reminder for task {tid}: {text}")
        notify(chat_id, f"👾 Reminder, Phoebe: Mission '{text}' is approaching. Stay sharp!")
        _clear_reminder(tid)

def _clear_reminder(task_id):
    conn = db.get_conn()
    conn.execute("UPDATE tasks SET remind_ts=NULL WHERE id=?", (task_id,))
    conn.commit()
    conn.close()
    print(f"[DEBUG] Cleared reminder flag for task {task_id}")

def check_due():
    now = int(time.time())
    window = now + 120
    rows = db.due_tasks_between(now, window)
    print(f"[DEBUG] check_due at {time.ctime(now)} → {len(rows)} tasks in window")
    for tid, chat_id, text, due_ts in rows:
        print(f"[DEBUG] Sending due alert for task {tid}: {text}")
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Done", callback_data=f"due_done:{tid}"),
                InlineKeyboardButton("❌ Not done", callback_data=f"due_notdone:{tid}")
            ]
        ])
        notify(chat_id, {
            "text": f"⚔️ Mission due now, Phoebe: {text}",
            "reply_markup": keyboard
        })

        # 🔑 Mark as alerted so it won’t fire again
        conn = db.get_conn()
        conn.execute("UPDATE tasks SET due_alerted=1 WHERE id=?", (tid,))
        conn.commit()
        conn.close()

def apply_daily_decay():
    print(f"[DEBUG] apply_daily_decay triggered at {time.ctime()}")
    conn = db.get_conn()
    chats = [row[0] for row in conn.execute("SELECT chat_id FROM growth").fetchall()]
    conn.close()
    for chat_id in chats:
        print(f"[DEBUG] Applying morale decay for chat {chat_id}")
        db.daily_decay(chat_id)

def schedule_enemy_spawns(app, chat_id, count=2):
    loop = asyncio.get_event_loop()

    async def spawn_enemy():
        import random
        enemy, difficulty = random.choice(ENEMIES)
        squad = db.list_squad(chat_id)
        morale = db.get_growth(chat_id)[2]

        if not squad:
            msg = f"👹 A wild {enemy} appears! But Phoebe has no Tasklings yet — the monster prowls unchallenged..."
        else:
            # Pick 1–3 random Tasklings to highlight
            fighters = random.sample(squad, min(3, len(squad)))
            fighter_lines = ", ".join([f"{name} the {role}" for name, role in fighters])

            power = len(squad) + morale
            if power >= difficulty:
                msg = (
                    f"👹 A wild {enemy} appears!\n"
                    f"{fighter_lines} charge into battle and strike it down heroically!"
                )
                db.add_growth_on_completion(chat_id)  # reward
            else:
                msg = (
                    f"👹 A wild {enemy} appears!\n"
                    f"{fighter_lines} fight bravely but are overwhelmed. "
                    f"The squad retreats, morale falters..."
                )
                # Punishment: morale drop + streak reset
                db.daily_decay(chat_id)
                conn = db.get_conn()
                conn.execute("UPDATE growth SET streak=0 WHERE chat_id=?", (chat_id,))
                conn.commit()
                conn.close()

        await app.bot.send_message(chat_id=chat_id, text=speak(msg))


