"""python tests/test_content.py — every syllabus topic with a guide has valid front-matter and exercise keys; banks are well-formed."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import content, exercises  # noqa: E402


def test_guides_and_banks():
    topics = content.topics()
    for m in content.syllabus():
        for u in m["units"]:
            for t in u["topics"]:
                g = content.guide(t)
                if g:
                    assert "{{verb" not in g["html"], t
                    assert all(k in topics for k in g["exercises"]), (t, g["exercises"])
    for name, items in content.banks().items():
        for it in items:
            assert it["type"] in ("cloze", "choice", "transform") and it["answer"] and it["text"], (name, it)
            if it["type"] == "choice":
                assert it["answer"][0] in it["options"], (name, it)
    assert any(it["type"] == "transform" for it in exercises.session(["pronoms-febles"], 30, content.banks()))
    assert content.unit_keys(4) == ["passats", "passat-perifrastic", "preterit-indefinit", "imperfet", "pronoms-febles"]


if __name__ == "__main__":
    test_guides_and_banks(); print("ok")
