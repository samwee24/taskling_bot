import sqlite3, time

def get_conn():
    conn = sqlite3.connect("sproutly.db")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = get_conn()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER NOT NULL,
        text TEXT NOT NULL,
        due_ts INTEGER,
        remind_ts INTEGER,
        status TEXT NOT NULL DEFAULT 'pending',
        created_ts INTEGER NOT NULL,
        due_alerted INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS prefs (
        chat_id INTEGER PRIMARY KEY,
        summary_hour INTEGER DEFAULT 8,
        timezone TEXT DEFAULT 'UTC'
    );

    CREATE TABLE IF NOT EXISTS growth (
        chat_id INTEGER PRIMARY KEY,
        points INTEGER DEFAULT 0,
        streak INTEGER DEFAULT 0,
        last_completed_day INTEGER DEFAULT 0,
        morale INTEGER DEFAULT 5
    );

    CREATE TABLE IF NOT EXISTS squad (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        role TEXT NOT NULL,
        joined_ts INTEGER NOT NULL
    );
    """)
    conn.commit()
    conn.close()
    ensure_growth_columns()
    ensure_task_columns()   # 👈 add this helper


def ensure_task_columns():
    conn = get_conn()
    try:
        conn.execute("ALTER TABLE tasks ADD COLUMN due_alerted INTEGER DEFAULT 0")
        conn.commit()
    except sqlite3.OperationalError:
        # Column already exists
        pass
    conn.close()


# --- Task functions ---
def add_task(chat_id, text, due_ts=None, remind_ts=None):
    conn = get_conn()
    conn.execute(
        "INSERT INTO tasks (chat_id, text, due_ts, remind_ts, status, created_ts) VALUES (?,?,?,?,?,?)",
        (chat_id, text, due_ts, remind_ts, 'pending', int(time.time()))
    )
    conn.commit()
    tid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return tid

def mark_done(chat_id, task_id):
    conn = get_conn()
    cur = conn.execute("UPDATE tasks SET status='done' WHERE chat_id=? AND id=?", (chat_id, task_id))
    conn.commit()
    ok = cur.rowcount > 0
    conn.close()
    if ok:
        add_growth_on_completion(chat_id)
    return ok

def list_tasks_for_day(chat_id, day_start_ts, day_end_ts):
    conn = get_conn()
    rows = conn.execute("""
        SELECT id, text, due_ts, status
        FROM tasks
        WHERE chat_id = ?
            AND status = 'pending'
            AND ((due_ts BETWEEN ? AND ?) OR due_ts IS NULL)
        ORDER BY id ASC
    """, (chat_id, day_start_ts, day_end_ts)).fetchall()
    conn.close()
    return rows

# --- Preferences ---
def set_prefs(chat_id, summary_hour=None, timezone=None):
    conn = get_conn()
    conn.execute("""
        INSERT INTO prefs (chat_id, summary_hour, timezone)
        VALUES (?, COALESCE(?, 8), COALESCE(?, 'UTC'))
        ON CONFLICT(chat_id) DO UPDATE SET
            summary_hour = COALESCE(?, prefs.summary_hour),
            timezone = COALESCE(?, prefs.timezone)
    """, (chat_id, summary_hour, timezone, summary_hour, timezone))
    conn.commit()
    conn.close()

def get_prefs(chat_id):
    # Always default to Berkeley time (US/Pacific) and 9am summary
    return (9, "US/Pacific")


# --- Growth mechanics ---
def add_growth_on_completion(chat_id):
    ensure_growth_row(chat_id)
    now_day = int(time.time() // 86400)
    conn = get_conn()
    points, streak, last_day, morale = conn.execute(
        "SELECT points, streak, last_completed_day, morale FROM growth WHERE chat_id=?", (chat_id,)
    ).fetchone()
    points += 1
    if last_day == now_day - 1:
        streak += 1
    elif last_day != now_day:
        streak = 1
    morale = min(10, morale + 1)
    conn.execute("UPDATE growth SET points=?, streak=?, last_completed_day=?, morale=? WHERE chat_id=?",
                 (points, streak, now_day, morale, chat_id))
    conn.commit()
    conn.close()

def daily_decay(chat_id):
    ensure_growth_row(chat_id)
    conn = get_conn()
    points, streak, last_day, morale = conn.execute(
        "SELECT points, streak, last_completed_day, morale FROM growth WHERE chat_id=?", (chat_id,)
    ).fetchone()
    now_day = int(time.time() // 86400)
    if last_day < now_day:
        morale = max(0, morale - 1)
        conn.execute("UPDATE growth SET morale=? WHERE chat_id=?", (morale, chat_id))
        conn.commit()
    conn.close()

def ensure_growth_row(chat_id):
    conn = get_conn()
    conn.execute(
        "INSERT OR IGNORE INTO growth (chat_id, points, streak, morale) VALUES (?, 0, 0, 5)",
        (chat_id,)
    )
    conn.commit()
    conn.close()

def ensure_growth_columns():
    conn = get_conn()
    try:
        conn.execute("ALTER TABLE growth ADD COLUMN morale INTEGER DEFAULT 5")
        conn.commit()
    except sqlite3.OperationalError:
        # Column already exists
        pass
    conn.close()

def get_growth(chat_id):
    conn = get_conn()
    row = conn.execute(
        "SELECT points, streak, morale FROM growth WHERE chat_id=?",
        (chat_id,)
    ).fetchone()
    conn.close()
    if row:
        return row
    return (0, 0, 5)  # default values


# --- Reminder queries ---
def due_tasks_between(start, end):
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, chat_id, text, due_ts FROM tasks "
        "WHERE due_ts BETWEEN ? AND ? AND (due_alerted IS NULL OR due_alerted=0)",
        (start, end)
    ).fetchall()
    conn.close()
    return rows

def remind_tasks_between(start_ts, end_ts):
    conn = get_conn()
    rows = conn.execute("""
        SELECT id, chat_id, text, remind_ts
        FROM tasks
        WHERE status='pending' AND remind_ts IS NOT NULL
          AND remind_ts BETWEEN ? AND ?
    """, (start_ts, end_ts)).fetchall()
    conn.close()
    return rows

def delete_task(chat_id, task_id):
    conn = get_conn()
    cur = conn.execute("DELETE FROM tasks WHERE chat_id=? AND id=?", (chat_id, task_id))
    conn.commit()
    ok = cur.rowcount > 0
    conn.close()
    return ok

def remap_task_ids():
    conn = get_conn()
    tasks = conn.execute("""
        SELECT chat_id, text, due_ts, remind_ts, status, created_ts, due_alerted
        FROM tasks
        ORDER BY id ASC
    """).fetchall()

    conn.executescript("""
        DROP TABLE IF EXISTS tasks;
        CREATE TABLE tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            text TEXT NOT NULL,
            due_ts INTEGER,
            remind_ts INTEGER,
            status TEXT NOT NULL DEFAULT 'pending',
            created_ts INTEGER NOT NULL,
            due_alerted INTEGER DEFAULT 0
        );
    """)

    for task in tasks:
        conn.execute("""
            INSERT INTO tasks (chat_id, text, due_ts, remind_ts, status, created_ts, due_alerted)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, task)

    conn.execute("DELETE FROM sqlite_sequence WHERE name='tasks'")
    conn.commit()
    conn.close()


def clear_all_tasks(chat_id):
    conn = get_conn()
    cur = conn.execute("DELETE FROM tasks WHERE chat_id=?", (chat_id,))
    conn.commit()
    count = cur.rowcount
    conn.close()
    return count

# --- Squad functions ---
def add_squad_member(chat_id, name, role):
    conn = get_conn()
    conn.execute(
        "INSERT INTO squad (chat_id, name, role, joined_ts) VALUES (?,?,?,?)",
        (chat_id, name, role, int(time.time()))
    )
    conn.commit()
    conn.close()

def list_squad(chat_id):
    conn = get_conn()
    rows = conn.execute(
        "SELECT name, role FROM squad WHERE chat_id=? ORDER BY joined_ts ASC",
        (chat_id,)
    ).fetchall()
    conn.close()
    return rows





