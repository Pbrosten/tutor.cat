"""Per-user progress: guides read, exercise results, saved sets. SQLite in data/progress.sqlite.
ponytail: profiles are a name in a cookie, no passwords — this runs on one machine.
"""
import os
import sqlite3
from datetime import datetime
from pathlib import Path

# bind-mounted ./data keeps this across restarts; PROGRESS_DB lets tests/dev runs use a throwaway copy
DB = Path(os.environ.get("PROGRESS_DB") or Path(__file__).resolve().parent.parent / "data" / "progress.sqlite")
SCHEMA = """
CREATE TABLE IF NOT EXISTS users(name TEXT PRIMARY KEY, created TEXT);
CREATE TABLE IF NOT EXISTS guides(user TEXT, slug TEXT, read INTEGER DEFAULT 0, last_seen TEXT, PRIMARY KEY(user, slug));
CREATE TABLE IF NOT EXISTS results(id INTEGER PRIMARY KEY, user TEXT, ts TEXT, key TEXT, type TEXT, prompt TEXT, given TEXT, ok INTEGER);
CREATE TABLE IF NOT EXISTS sets(id INTEGER PRIMARY KEY, user TEXT, name TEXT, keys TEXT);
CREATE TABLE IF NOT EXISTS sessions(id INTEGER PRIMARY KEY, user TEXT, ts TEXT, guide TEXT, n INTEGER, correct INTEGER, kind TEXT);
CREATE TABLE IF NOT EXISTS badges(user TEXT, id TEXT, earned_at TEXT, seen INTEGER DEFAULT 0, toasted INTEGER DEFAULT 0, PRIMARY KEY(user, id));
"""
WEAK_MIN_ATTEMPTS = 5
WEAK_MAX_ACCURACY = 0.7
PASS_MIN_ITEMS = 10      # a guide is "passed" after PASS_ROUNDS rounds of >= 10 items...
PASS_RATIO = 0.7         # ...each with 7/10 or better
PASS_ROUNDS = 2          # default; a guide's front-matter `rounds:` raises it (2–5) for the key topics


def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    if "kind" not in {r[1] for r in con.execute("PRAGMA table_info(sessions)")}:   # DBs created before the badges feature
        con.execute("ALTER TABLE sessions ADD COLUMN kind TEXT")
    cols = {r[1] for r in con.execute("PRAGMA table_info(badges)")}
    if "seen" not in cols:
        con.execute("ALTER TABLE badges ADD COLUMN seen INTEGER DEFAULT 0")
    if "toasted" not in cols:
        con.execute("ALTER TABLE badges ADD COLUMN toasted INTEGER DEFAULT 0")
    return con


def now():
    return datetime.now().isoformat(timespec="seconds")


# --- users
def users():
    with db() as con:
        return [r["name"] for r in con.execute("SELECT name FROM users ORDER BY name")]


def ensure_user(name):
    name = " ".join(name.split())[:40]
    if not name:
        return None
    with db() as con:
        con.execute("INSERT OR IGNORE INTO users VALUES (?, ?)", (name, now()))
    return name


# --- guides
def touch_guide(user, slug):
    with db() as con:
        con.execute("INSERT INTO guides(user, slug, last_seen) VALUES (?,?,?) ON CONFLICT(user, slug) DO UPDATE SET last_seen = excluded.last_seen",
                    (user, slug, now()))


def toggle_guide_read(user, slug):
    if not guide_passed(user, slug):
        return False
    with db() as con:
        con.execute("INSERT INTO guides(user, slug, read, last_seen) VALUES (?,?,1,?) ON CONFLICT(user, slug) DO UPDATE SET read = 1 - read",
                    (user, slug, now()))
    return True


def record_session(user, guide, n, correct, kind="tema"):
    """Every graded series; `guide` is set only for guide rounds, `kind` is guia/tema/unitat/personal/set."""
    with db() as con:
        con.execute("INSERT INTO sessions(user, ts, guide, n, correct, kind) VALUES (?,?,?,?,?,?)", (user, now(), guide, n, correct, kind))


def guide_rounds(user, slug):
    """Qualifying rounds for this guide, best first: [{'n', 'correct', 'ts'}]."""
    with db() as con:
        return [dict(r) for r in con.execute("""SELECT n, correct, ts FROM sessions WHERE user = ? AND guide = ? AND n >= ? AND correct >= ? * n
                                                ORDER BY CAST(correct AS REAL) / n DESC, ts DESC""", (user, slug, PASS_MIN_ITEMS, PASS_RATIO))]


def rounds_required(slug):
    from app import content  # local import: content imports nothing from here, but keep the module graph simple
    return int((content.guide_meta(slug) or {}).get("rounds", PASS_ROUNDS))


def guide_passed(user, slug):
    """{'rounds': k, 'best': {...}} once k >= rounds_required(slug) qualifying rounds exist, else None."""
    rounds = guide_rounds(user, slug)
    return {"rounds": len(rounds), "best": rounds[0]} if len(rounds) >= rounds_required(slug) else None


def guide_status(user):
    """{slug: {'read': bool, 'last_seen': str}}"""
    with db() as con:
        return {r["slug"]: {"read": bool(r["read"]), "last_seen": r["last_seen"]}
                for r in con.execute("SELECT * FROM guides WHERE user = ?", (user,))}


# --- results
def record(user, key, type_, prompt, given, ok):
    with db() as con:
        con.execute("INSERT INTO results(user, ts, key, type, prompt, given, ok) VALUES (?,?,?,?,?,?,?)",
                    (user, now(), key, type_, prompt, given, int(ok)))


def stats(user):
    """per_key, weakest first: [{key, attempts, correct, accuracy, last}], plus totals."""
    with db() as con:
        rows = con.execute("""SELECT key, COUNT(*) attempts, SUM(ok) correct, MAX(ts) last FROM results
                              WHERE user = ? GROUP BY key ORDER BY CAST(SUM(ok) AS REAL) / COUNT(*), attempts DESC""", (user,)).fetchall()
        days = con.execute("SELECT COUNT(DISTINCT substr(ts, 1, 10)) FROM results WHERE user = ?", (user,)).fetchone()[0]
    per_key = [{**dict(r), "accuracy": r["correct"] / r["attempts"]} for r in rows]
    attempts = sum(r["attempts"] for r in per_key)
    correct = sum(r["correct"] for r in per_key)
    return {"per_key": per_key, "attempts": attempts, "correct": correct,
            "accuracy": correct / attempts if attempts else None, "days": days}


def weak_keys(user, limit=4):
    """Keys practised at least WEAK_MIN_ATTEMPTS times with accuracy below WEAK_MAX_ACCURACY, weakest first."""
    return [r["key"] for r in stats(user)["per_key"]
            if r["attempts"] >= WEAK_MIN_ATTEMPTS and r["accuracy"] < WEAK_MAX_ACCURACY][:limit]


def failed_prompts(user, limit=20):
    """(key, prompt) of bank items whose most recent answer was wrong."""
    with db() as con:
        rows = con.execute("SELECT key, prompt, ok FROM results WHERE user = ? ORDER BY ts, id", (user,)).fetchall()
    last = {}
    for r in rows:
        last[(r["key"], r["prompt"])] = r["ok"]
    return [k for k, ok in reversed(list(last.items())) if not ok][:limit]


def recent(user, limit=15):
    with db() as con:
        return [dict(r) for r in con.execute("SELECT * FROM results WHERE user = ? ORDER BY id DESC LIMIT ?", (user, limit))]


# --- saved sets
def add_set(user, name, keys):
    name = " ".join(name.split())[:60] or "Sèrie personalitzada"
    with db() as con:
        con.execute("INSERT INTO sets(user, name, keys) VALUES (?,?,?)", (user, name, ",".join(keys)))


def sets(user):
    with db() as con:
        return [{**dict(r), "topics": r["keys"].split(",")} for r in con.execute("SELECT * FROM sets WHERE user = ? ORDER BY id", (user,))]


def get_set(user, set_id):
    return next((s for s in sets(user) if s["id"] == set_id), None)


def delete_set(user, set_id):
    with db() as con:
        con.execute("DELETE FROM sets WHERE user = ? AND id = ?", (user, set_id))
