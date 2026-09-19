"""python tests/test_exercises.py — needs data/verbs.sqlite."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import exercises, verbs  # noqa: E402


def test_all_b1_verbs_exist():
    missing = [v for v in exercises.B1_VERBS if not verbs.conjugation(v)]
    assert not missing, missing


def test_check():
    assert exercises.check(" Cantàvem. ", ["cantàvem"])
    assert not exercises.check("cantavem", ["cantàvem"])
    assert exercises.check("vaig anar", ["vaig anar", "vàreig anar"])


def test_session_shape():
    for topic in exercises.TOPICS:
        for it in exercises.session([topic], 20):
            assert it["answer"] and "—" not in it["answer"], it
            if it["type"] == "choice":
                assert it["answer"][0] in it["options"] and len(set(it["options"])) == len(it["options"]), it


def test_no_repeats():
    from app import content
    banks = content.banks()
    for key in ["articles-apostrofacio", "present", "passats", "tots"]:
        for _ in range(5):
            ids = [exercises.ident(it) for it in exercises.session([key], 50, banks)]
            assert len(ids) == len(set(ids)), key
    small = exercises.session(["articles-apostrofacio"], 50, banks)          # bank has 18 items
    assert len(small) == len(banks["articles-apostrofacio"])
    mixed = exercises.session(["articles-apostrofacio", "present"], 50, banks)  # bank runs out, drills fill the rest
    assert len(mixed) == 50 and len({exercises.ident(it) for it in mixed}) == 50


def test_full_sentence_and_explain():
    it = {"type": "cloze", "prompt": "Ahir jo ___ (cantar).", "answer": ["vaig cantar"], "key": "passat-perifrastic", "lemma": "cantar", "person": 0, "hint": "x"}
    assert exercises.full_sentence(it) == "Ahir jo vaig cantar."
    assert "imperfet, jo de cantar" in exercises.explain(it, "cantava") and "passat perifràstic" in exercises.explain(it, "cantava")
    assert "no és cap forma de «cantar»" in exercises.explain(it, "xyz")
    assert "forma de «anar»" in exercises.explain(it, "vaig")
    it2 = {"type": "conjugate", "prompt": "cantar — passat simple, ell/ella", "answer": ["cantà"], "key": "present", "lemma": "cantar", "person": 2}
    assert "accent" in exercises.explain(it2, "canta")
    bank = {"type": "cloze", "prompt": "___ Anna i ___ Joan són germans.", "answer": ["L' / en"], "key": "articles-apostrofacio", "hint": "article personal"}
    assert exercises.full_sentence(bank) == "L'Anna i en Joan són germans."
    assert exercises.full_sentence({"prompt": "Pots portar ___ el teu germà.", "answer": ["-hi"]}) == "Pots portar-hi el teu germà."
    assert exercises.full_sentence({"prompt": "Vols més pa? — Sí, posa ___ una mica més.", "answer": ["-me'n"]}) == "Vols més pa? — Sí, posa-me'n una mica més."
    assert exercises.explain(bank, "La / el").startswith("Regla: article personal")
    ident = {"type": "choice", "prompt": "«cantàvem» (cantar) és…", "answer": ["imperfet, nosaltres"], "key": "imperfet", "lemma": "cantar", "person": 3, "form": "cantàvem", "options": []}
    assert exercises.explain(ident, "futur, nosaltres") == "«cantàvem» és imperfet, nosaltres de cantar. «futur, nosaltres» seria «cantarem»."
    res = exercises.grade([it, bank], ["Vaig cantar", ""])
    assert res[0]["ok"] and res[0]["why"] is None and not res[1]["ok"] and res[1]["why"].startswith("Sense resposta")


def test_identify_no_ambiguous_distractors():
    import random
    random.seed(1)
    for _ in range(50):
        it = exercises.identify("cantar", "present")
        assert not ({"subjuntiu present, vosaltres", "imperatiu, vosaltres"} & set(it["options"]) - set(it["answer"])) or "canteu" not in it["prompt"], it


if __name__ == "__main__":
    test_all_b1_verbs_exist(); test_check(); test_session_shape(); test_no_repeats(); test_full_sentence_and_explain(); test_identify_no_ambiguous_distractors(); print("ok")
