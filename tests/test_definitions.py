"""python tests/test_definitions.py — offline parsers only."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import definitions  # noqa: E402

WIKI = """{{vegeu|càntar}}

== {{-ca-}} ==
{{ca-pron|tipus=inf}}
=== Verb ===
{{ca-verb|t-i}}
[[Fitxer:YaireLive.jpg|miniatura|Cantant]]
# Produir [[música]] amb la [[veu]].
# Un [[ocell]], emetre sons harmoniosos o rítmics.<ref>x</ref>
# {{marca|ca|beisbol|esports de raqueta}} Fer saber en veu alta el [[resultat|resultat]].

==== Conjugació ====
{{ca-conj}}

== {{-es-}} ==
=== Verb ===
# cantar (castellà)
"""
EN = json.dumps({"ca": [{"partOfSpeech": "Verb", "definitions": [
    {"definition": '<span class="usage-label-sense"></span> to <a href="/wiki/sing">sing</a>'}, {"definition": "to call out"}]},
    {"partOfSpeech": "Noun", "definitions": [{"definition": "not a verb"}]}], "es": []})


def test_parsers():
    assert definitions.parse_ca(WIKI) == ["Produir música amb la veu.", "Un ocell, emetre sons harmoniosos o rítmics.",
                                          "(beisbol, esports de raqueta) Fer saber en veu alta el resultat."]
    assert definitions.parse_en(EN) == ["to sing", "to call out"]
    assert definitions.parse_ca("== {{-es-}} ==\n=== Verb ===\n# nope") == []


if __name__ == "__main__":
    test_parsers(); print("ok")
