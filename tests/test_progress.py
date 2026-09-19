"""python tests/test_progress.py — uses a throwaway DB."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import content, exercises, progress  # noqa: E402

progress.DB = Path(tempfile.mkdtemp()) / "p.sqlite"


def test_flow():
    u = progress.ensure_user("  Peter   B ")
    assert u == "Peter B" and progress.users() == ["Peter B"]
    progress.touch_guide(u, "verbs-futur"); progress.record_session(u, "verbs-futur", 10, 9); progress.record_session(u, "verbs-futur", 10, 7)
    progress.toggle_guide_read(u, "verbs-futur"); progress.touch_guide(u, "relatius")
    st = progress.guide_status(u)
    assert st["verbs-futur"]["read"] and not st["relatius"]["read"]
    progress.toggle_guide_read(u, "verbs-futur")
    assert not progress.guide_status(u)["verbs-futur"]["read"]

    bank = content.banks()["pronoms-febles"]
    for i in range(6):
        progress.record(u, "pronoms-febles", "cloze", bank[i]["text"], "x", i < 1)      # 1/6 right
    for i in range(6):
        progress.record(u, "present", "conjugate", f"p{i}", "x", True)                   # 6/6 right
    progress.record(u, "futur", "conjugate", "f", "x", False)                            # too few attempts
    s = progress.stats(u)
    assert [r["key"] for r in s["per_key"]] == ["futur", "pronoms-febles", "present"] and s["attempts"] == 13 and s["days"] == 1
    assert progress.weak_keys(u) == ["pronoms-febles"]  # futur has too few attempts
    progress.record(u, "pronoms-febles", "cloze", bank[1]["text"], "y", True)            # fixed one
    failed = progress.failed_prompts(u)
    assert len(failed) == 5 and ("pronoms-febles", bank[1]["text"]) not in failed and ("futur", "f") in failed

    items = exercises.session(["pronoms-febles"], 6, content.banks(), retry=failed)
    assert len(items) == 6 and sum(1 for it in items if it["prompt"] in {p for _, p in failed}) >= 4
    assert all(it["key"] for it in items)

    # guide gate: no read mark until a round of >=10 with >=70 %
    assert progress.toggle_guide_read(u, "relatius") is False and not progress.guide_status(u).get("relatius", {}).get("read")
    progress.record_session(u, "relatius", 10, 6)
    assert progress.guide_passed(u, "relatius") is None
    progress.record_session(u, "relatius", 8, 8)   # too short
    assert progress.guide_passed(u, "relatius") is None
    progress.record_session(u, "relatius", 10, 7)
    assert progress.guide_passed(u, "relatius") is None and len(progress.guide_rounds(u, "relatius")) == 1   # one good round isn't enough
    progress.record_session(u, "relatius", 12, 9)
    p = progress.guide_passed(u, "relatius")
    assert p["rounds"] == 2 and p["best"]["correct"] == 9 and progress.toggle_guide_read(u, "relatius") is True
    assert progress.rounds_required("relatius") == 2 and progress.rounds_required("verbs-passats") == 5
    for _ in range(4):
        progress.record_session(u, "verbs-passats", 10, 8)
    assert progress.guide_passed(u, "verbs-passats") is None
    progress.record_session(u, "verbs-passats", 10, 8)
    assert progress.guide_passed(u, "verbs-passats")["rounds"] == 5
    assert progress.guide_status(u)["relatius"]["read"]

    progress.add_set(u, "", ["present", "relatius"])
    (st,) = progress.sets(u)
    assert st["name"] == "Sèrie personalitzada" and st["topics"] == ["present", "relatius"] and progress.get_set(u, st["id"])
    progress.delete_set(u, st["id"])
    assert progress.sets(u) == []


if __name__ == "__main__":
    test_flow(); print("ok")
