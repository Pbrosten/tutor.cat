"""Milestone badges, computed from what progress.py already records and cached in a `badges` table
so we know when each one was earned. award(user) is idempotent and retroactive."""
import re
from datetime import date, timedelta

from app import content, exercises, progress

IRREGULARS = "ser anar tenir fer dir veure poder voler saber venir estar haver caure riure viure beure escriure conèixer dur".split()
PASS = lambda s: s["n"] >= progress.PASS_MIN_ITEMS and s["correct"] >= progress.PASS_RATIO * s["n"]  # noqa: E731


def _lemma(prompt):
    m = re.match(r"^(\S+) — ", prompt) or re.search(r"\((\S+)\)", prompt)
    return m.group(1) if m else None


def _max_streak(days):
    days, best, run = sorted(set(days)), 0, 0
    for i, d in enumerate(days):
        run = run + 1 if i and d - days[i - 1] == timedelta(days=1) else 1
        best = max(best, run)
    return best


def _facts(user):
    """Everything the checks need, in one pass over the DB."""
    with progress.db() as con:
        results = [dict(r) for r in con.execute("SELECT ts, key, prompt, ok FROM results WHERE user = ? ORDER BY ts, id", (user,))]
        sessions = [dict(r) for r in con.execute("SELECT ts, guide, kind, n, correct FROM sessions WHERE user = ? ORDER BY ts, id", (user,))]
    read = {s for s, v in progress.guide_status(user).items() if v["read"]}
    by_key = {}
    for r in results:
        by_key.setdefault(r["key"], []).append(r["ok"])
    modules = {m["name"]: {t for u in m["units"] for t in u["topics"] if content.guide_meta(t)} for m in content.syllabus()}
    return {"results": results, "sessions": sessions, "read": read, "by_key": by_key, "modules": modules,
            "days": {date.fromisoformat(r["ts"][:10]) for r in results}}


def _mastered(oks):
    return len(oks) >= 50 and sum(oks[-50:]) / 50 >= 0.9


def _comeback(oks):
    """Was weak (<70 % after >=5 answers) and later scored >=17/20 in a window of 20."""
    ok_sum = 0
    for i, ok in enumerate(oks, 1):
        ok_sum += ok
        if i >= progress.WEAK_MIN_ATTEMPTS and ok_sum / i < progress.WEAK_MAX_ACCURACY:
            rest = oks[i:]
            return any(sum(rest[j:j + 20]) >= 17 for j in range(len(rest) - 19))
    return False


def _first_try(sessions):
    first = {}
    for s in sessions:
        if s["guide"] and s["guide"] not in first:
            first[s["guide"]] = s
    return any(PASS(s) for s in first.values())


# id, icon, name, description, check(facts) -> bool
BADGES = [
    ("primera-passa", "🚶", "Primera passa", "Primera guia marcada com a llegida", lambda f: bool(f["read"])),
    ("elemental-1", "1️⃣", "Elemental 1", "Totes les guies del mòdul Elemental 1 llegides", lambda f: f["modules"]["Elemental 1"] <= f["read"]),
    ("elemental-2", "2️⃣", "Elemental 2", "Totes les guies del mòdul Elemental 2 llegides", lambda f: f["modules"]["Elemental 2"] <= f["read"]),
    ("elemental-3", "3️⃣", "Elemental 3", "Totes les guies del mòdul Elemental 3 llegides", lambda f: f["modules"]["Elemental 3"] <= f["read"]),
    ("nivell-elemental", "🎓", "Nivell Elemental", "Les 27 guies llegides", lambda f: set().union(*f["modules"].values()) <= f["read"]),
    ("escalfament", "🔥", "Escalfament", "50 respostes", lambda f: len(f["results"]) >= 50),
    ("constancia", "💪", "Constància", "500 respostes", lambda f: len(f["results"]) >= 500),
    ("marato", "🏃", "Marató", "2.000 respostes", lambda f: len(f["results"]) >= 2000),
    ("serie-perfecta", "💯", "Sèrie perfecta", "Una sèrie de 10 ítems o més amb el 100 %", lambda f: any(s["n"] >= 10 and s["correct"] == s["n"] for s in f["sessions"])),
    ("a-la-primera", "🎯", "A la primera", "Superar la ronda d'una guia al primer intent", lambda f: _first_try(f["sessions"])),
    ("remuntada", "📈", "Remuntada", "Un tema feble (<70 %) puja al 85 % en les 20 respostes següents", lambda f: any(_comeback(v) for v in f["by_key"].values())),
    ("irregulars", "🧩", "Irregulars", "Encerts en 10 verbs irregulars diferents",
     lambda f: len({_lemma(r["prompt"]) for r in f["results"] if r["ok"] and r["key"] in exercises.TENSES and _lemma(r["prompt"]) in IRREGULARS}) >= 10),
    ("ratxa-3", "📅", "Ratxa de 3", "3 dies seguits amb una sèrie corregida", lambda f: _max_streak(f["days"]) >= 3),
    ("ratxa-7", "🗓️", "Ratxa de 7", "7 dies seguits amb una sèrie corregida", lambda f: _max_streak(f["days"]) >= 7),
    ("ratxa-30", "🏆", "Ratxa de 30", "30 dies seguits amb una sèrie corregida", lambda f: _max_streak(f["days"]) >= 30),
    ("tastaolletes", "🍽️", "Tastaolletes", "Almenys una resposta en cadascun dels temes de banc", lambda f: set(content.banks()) <= set(f["by_key"])),
    ("tots-els-temps", "⏳", "Tots els temps", "Un encert en cada temps verbal de B1",
     lambda f: all(any(f["by_key"].get(k, [])) for k in exercises.TENSES)),
    ("a-mida", "🧵", "A mida", "Primera sèrie personalitzada completada", lambda f: any(s["kind"] == "personal" for s in f["sessions"])),
]


GROUPS = ["Progrés", "Volum", "Domini", "Constància", "Exploració"]
GROUP_OF = {'primera-passa': 'Progrés', 'elemental-1': 'Progrés', 'elemental-2': 'Progrés', 'elemental-3': 'Progrés', 'nivell-elemental': 'Progrés', 'escalfament': 'Volum', 'constancia': 'Volum', 'marato': 'Volum', 'serie-perfecta': 'Volum', 'a-la-primera': 'Volum', 'remuntada': 'Domini', 'irregulars': 'Domini', 'ratxa-3': 'Constància', 'ratxa-7': 'Constància', 'ratxa-30': 'Constància', 'tastaolletes': 'Exploració', 'tots-els-temps': 'Exploració', 'a-mida': 'Exploració'}


def catalogue():
    """All badge definitions incl. one 'Mestre' per topic: [{id, icon, name, desc, group}]."""
    base = [{"id": i, "icon": ic, "name": n, "desc": d, "group": GROUP_OF[i]} for i, ic, n, d, _ in BADGES]
    masters = [{"id": f"mestre-{k}", "icon": "🥇", "name": f"Mestre: {label}", "desc": "≥90 % en les últimes 50 respostes del tema", "group": "Domini"}
               for k, label in content.topics().items() if k not in ("tots", "passats")]
    return base + masters


def evaluate(user):
    f = _facts(user)
    earned = {i for i, *_, check in BADGES if check(f)}
    earned |= {f"mestre-{k}" for k, oks in f["by_key"].items() if _mastered(oks)}
    return earned


def award(user):
    """Store newly earned badges; return them (as catalogue entries) so the UI can celebrate."""
    with progress.db() as con:
        have = {r[0] for r in con.execute("SELECT id FROM badges WHERE user = ?", (user,))}
        new = evaluate(user) - have
        con.executemany("INSERT INTO badges(user, id, earned_at) VALUES (?,?,?)", [(user, b, progress.now()) for b in new])
    return [b for b in catalogue() if b["id"] in new]


def shelf(user):
    """Catalogue with earned_at filled in for the ones this user has."""
    with progress.db() as con:
        when = dict(con.execute("SELECT id, earned_at FROM badges WHERE user = ?", (user,)))
    return [{**b, "earned_at": when.get(b["id"])} for b in catalogue()]


def unseen(user):
    """Badges earned but not yet looked at on the profile page (drives the nav dot)."""
    with progress.db() as con:
        return con.execute("SELECT COUNT(*) FROM badges WHERE user = ? AND seen = 0", (user,)).fetchone()[0]


def mark_seen(user):
    with progress.db() as con:
        con.execute("UPDATE badges SET seen = 1 WHERE user = ?", (user,))


def pop_toasts(user):
    """Badges not yet announced with a toast; marks them announced. Called once per page render."""
    with progress.db() as con:
        ids = [r[0] for r in con.execute("SELECT id FROM badges WHERE user = ? AND toasted = 0", (user,))]
        if ids:
            con.execute("UPDATE badges SET toasted = 1 WHERE user = ?", (user,))
    return [b for b in catalogue() if b["id"] in ids]
