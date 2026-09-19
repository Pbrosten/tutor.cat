import sqlite3
from functools import lru_cache
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "data" / "verbs.sqlite"
PERSONS = ["jo", "tu", "ell/ella", "nosaltres", "vosaltres", "ells/elles"]
KEYS = [("1", "S"), ("2", "S"), ("3", "S"), ("1", "P"), ("2", "P"), ("3", "P")]

# ponytail: auxiliaries hardcoded; they're in the DB too but this is 3 lines and never changes.
HAVER_PRES = ["he", "has", "ha", "hem", "heu", "han"]
HAVER_IMPF = ["havia", "havies", "havia", "havíem", "havíeu", "havien"]
ANAR_AUX = ["vaig", "vas", "va", "vam", "vau", "van"]

B1_TENSES = {
    ("indicatiu", "present"), ("indicatiu", "imperfet"), ("indicatiu", "passat perifràstic"),
    ("indicatiu", "pretèrit indefinit"), ("indicatiu", "plusquamperfet"), ("indicatiu", "futur"),
    ("indicatiu", "condicional"), ("subjuntiu", "present"), ("subjuntiu", "imperfet"), ("imperatiu", ""),
}
ORDER = ["present", "imperfet", "passat perifràstic", "pretèrit indefinit", "plusquamperfet", "passat simple", "futur", "condicional", ""]


def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con


def search(q, limit=20):
    """Lemmas starting with q, plus the lemma of any exact inflected form (reverse lookup)."""
    q = q.strip().lower()
    if not q:
        return []
    with db() as con:
        return [dict(r) for r in con.execute(
            """SELECT lemma, freq, reflexive FROM verbs
               WHERE lemma LIKE ? OR lemma IN (SELECT lemma FROM forms WHERE form = ?)
               ORDER BY (lemma = ?) DESC, freq DESC LIMIT ?""",
            (q + "%", q, q, limit))]


@lru_cache(maxsize=20000)
def lemmas_of(form):
    """Distinct lemmas a surface form belongs to ('casa' -> ('casar',)); () if it isn't a verb form."""
    with db() as con:
        return tuple(r[0] for r in con.execute("SELECT DISTINCT lemma FROM forms WHERE form = ? ORDER BY lemma", (form,)))


def identify(form):
    """'hauríem' -> [{'lemma': 'haver', 'mood': ..., 'tense': ..., 'person': 'nosaltres'}]"""
    with db() as con:
        rows = con.execute("SELECT DISTINCT lemma, mood, tense, person, number, gender FROM forms WHERE form = ?", (form.strip().lower(),)).fetchall()
    return [{**dict(r), "label": _label(r)} for r in rows]


def _label(r):
    if (r["person"], r["number"]) in KEYS:
        return PERSONS[KEYS.index((r["person"], r["number"]))]
    return {"S": "singular", "P": "plural"}.get(r["number"], "")


def conjugation(lemma, all_tenses=False):
    """{mood: {tense: [form per person]}}; compound tenses built from participle/infinitive."""
    with db() as con:
        verb = con.execute("SELECT * FROM verbs WHERE lemma = ?", (lemma,)).fetchone()
        if not verb:
            return None
        rows = con.execute("SELECT * FROM forms WHERE lemma = ?", (lemma,)).fetchall()

    cells = {}
    for r in rows:
        cells.setdefault((r["mood"], r["tense"]), {}).setdefault((r["person"], r["number"], r["gender"]), []).append(r["form"])

    def row(mood, tense):
        c = cells.get((mood, tense), {})
        return [" / ".join(c.get((p, n, "0"), ["—"])) for p, n in KEYS]

    part = cells.get(("participi", ""), {})
    participle = part.get(("0", "S", "M"), ["—"])[0]
    tables = {"indicatiu": {}, "subjuntiu": {}, "imperatiu": {}}
    for mood, tense in cells:
        if mood in tables:
            tables[mood][tense] = row(mood, tense)
    tables["indicatiu"]["passat perifràstic"] = [f"{a} {lemma}" for a in ANAR_AUX]
    tables["indicatiu"]["pretèrit indefinit"] = [f"{a} {participle}" for a in HAVER_PRES]
    tables["indicatiu"]["plusquamperfet"] = [f"{a} {participle}" for a in HAVER_IMPF]

    for mood in tables:
        tables[mood] = {t: tables[mood][t] for t in ORDER if t in tables[mood] and (all_tenses or (mood, t) in B1_TENSES)}
    nonfinite = {
        "infinitiu": lemma + (" (-se)" if verb["reflexive"] else ""),
        "gerundi": cells.get(("gerundi", ""), {}).get(("0", "0", "0"), ["—"])[0],
        "participi": " / ".join(part.get(k, ["—"])[0] for k in [("0", "S", "M"), ("0", "S", "F"), ("0", "P", "M"), ("0", "P", "F")]),
    }
    return {"verb": dict(verb), "tables": tables, "nonfinite": nonfinite}
