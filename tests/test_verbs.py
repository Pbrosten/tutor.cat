"""python -m pytest tests  (or: python tests/test_verbs.py). Needs data/verbs.sqlite for the second half."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "data"))

from build_verbs import apply_model, decode  # noqa: E402


def test_model_and_tag():
    assert apply_model("cantar", "ar", "àvem") == "cantàvem"
    assert apply_model("tenir", "enir", "é") == "té"
    assert apply_model("cantar", "r", "0") == "canta"
    assert decode("VMIP1S0C") == ("indicatiu", "present", "1", "S", "0")


def test_conjugation():
    from app import verbs
    if not verbs.DB.exists():
        return
    c = verbs.conjugation("cantar")
    assert c["tables"]["indicatiu"]["present"] == ["canto", "cantes", "canta", "cantem", "canteu", "canten"]
    assert c["tables"]["indicatiu"]["passat perifràstic"][0] == "vaig cantar"
    assert c["tables"]["indicatiu"]["pretèrit indefinit"][5] == "han cantat"
    assert c["tables"]["subjuntiu"]["imperfet"] == ["cantés", "cantessis", "cantés", "cantéssim", "cantéssiu", "cantessin"]
    assert "cantí" not in str(c["tables"]) and "cante" not in c["tables"]["indicatiu"]["present"]
    assert verbs.identify("hauríem")[0]["lemma"] == "haver"
    assert verbs.search("vaig")[0]["lemma"] == "anar"


if __name__ == "__main__":
    test_model_and_tag(); test_conjugation(); print("ok")
