"""python tests/test_badges.py — throwaway DB."""
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import badges, content, progress  # noqa: E402

progress.DB = Path(tempfile.mkdtemp()) / "p.sqlite"


def test_badges():
    u = progress.ensure_user("b")
    assert badges.award(u) == [] and len(badges.catalogue()) > 30
    # guides: read one (bypassing the gate by inserting the rounds), then all of Elemental 1
    for slug in content.syllabus()[0]["units"][0]["topics"]:
        progress.record_session(u, slug, 10, 10, "guia"); progress.record_session(u, slug, 10, 8, "guia"); progress.toggle_guide_read(u, slug)
    got = {b["id"] for b in badges.award(u)}
    assert {"primera-passa", "serie-perfecta", "a-la-primera"} <= got and "elemental-1" not in got
    # answers: 50 on 'present' with irregular verbs, all right -> escalfament, mestre-present, irregulars
    verbs = badges.IRREGULARS[:10] * 5
    for i, v in enumerate(verbs):
        progress.record(u, "present", "conjugate", f"{v} — present, jo", "x", True)
    got = {b["id"] for b in badges.award(u)}
    assert {"escalfament", "mestre-present", "irregulars"} <= got
    # comeback: 5 wrong then 20 right on relatius
    for ok in [False] * 5 + [True] * 20:
        progress.record(u, "relatius", "cloze", "p", "x", ok)
    assert "remuntada" in {b["id"] for b in badges.award(u)}
    # streak: fake three consecutive days
    with progress.db() as con:
        for d in range(3):
            con.execute("INSERT INTO results(user, ts, key, type, prompt, given, ok) VALUES (?,?,?,?,?,?,?)",
                        (u, (date(2026, 1, 1) + timedelta(days=d)).isoformat() + "T10:00:00", "futur", "conjugate", "x", "x", 1))
    got = {b["id"] for b in badges.award(u)}
    assert "ratxa-3" in got and "ratxa-7" not in got
    assert badges.award(u) == []  # idempotent
    assert badges.unseen(u) >= 8
    badges.mark_seen(u)
    assert badges.unseen(u) == 0
    assert len(badges.pop_toasts(u)) >= 8 and badges.pop_toasts(u) == []
    shelf = badges.shelf(u)
    assert sum(1 for b in shelf if b["earned_at"]) >= 8 and any(b["id"] == "ratxa-30" and not b["earned_at"] for b in shelf)


if __name__ == "__main__":
    test_badges(); print("ok")
