"""One-shot: Softcatalà catalan-dict-tools -> data/verbs.sqlite (central Catalan only), plus a `words` table
(nouns, adjectives, adverbs: form -> lemma, pos) from the full-form LanguageTool dictionary, for the tooltips.

    docker compose run --rm app python data/build_verbs.py
"""
import io
import re
import sqlite3
import tarfile
import urllib.request
from pathlib import Path

DATA = Path(__file__).resolve().parent
DICT_COMMIT = "e5de3a983284a2501cd53f869a12b48059146b33"  # catalan-dict-tools, 2026-09
DICT_URL = f"https://github.com/Softcatala/catalan-dict-tools/archive/{DICT_COMMIT}.tar.gz"
OLD_DIACRITICS_URL = "https://raw.githubusercontent.com/Softcatala/conjugador/master/extractor/replace_diacritics_iec.txt"
REFLEX_URL = "https://raw.githubusercontent.com/Softcatala/conjugador/master/extractor/reflexius.txt"
# 8th tag char = dialect. 0 general, C central, Y central subj. -i, X central imp. 2p,
# 1/2 central imperfet subj.; V/3/5 valencià, B/4/6/7 balear, Z other.
CENTRAL = set("0CYX12")

MOOD = {"I": "indicatiu", "S": "subjuntiu", "M": "imperatiu", "N": "infinitiu", "G": "gerundi", "P": "participi"}
TENSE = {"P": "present", "I": "imperfet", "F": "futur", "S": "passat simple", "C": "condicional", "0": ""}
# LT tag prefix -> our pos. NC = common noun (3rd char = gender), AQ/AO = adjective, RG = adverb. Proper nouns and function
# words skipped: the former need no definition, the latter are on the tips stoplist anyway.
WORD_POS = {"NC": "n", "AQ": "a", "AO": "a", "RG": "r"}


def apply_model(infinitive, strip, add):
    """Model line 'strip add ...': remove suffix `strip` from the infinitive, append `add` ('0' = nothing)."""
    assert infinitive.endswith(strip), (infinitive, strip)
    base = infinitive[: -len(strip)]
    return base + ("" if add == "0" else add)


def decode(tag):
    """VMIP1S0C -> (mood, tense, person, number, gender)."""
    return MOOD[tag[2]], TENSE[tag[3]], tag[4], tag[5], tag[6]


def fetch(url):
    cache = DATA / url.rsplit("/", 1)[1]
    if not cache.exists():
        print("downloading", url)
        cache.write_bytes(urllib.request.urlopen(url).read())
    return cache.read_bytes()


def load_dict():
    tar = tarfile.open(fileobj=io.BytesIO(fetch(DICT_URL)))
    files = {}
    for m in tar:
        if "/diccionari-arrel/verbs-fdic.txt" in m.name or "/models-verbals/" in m.name and m.name.endswith(".model") or m.name.endswith(("frequencies-dict-lemmas.txt", "resultats/lt/diccionari.txt")):
            files[m.name.split("/")[-1]] = tar.extractfile(m).read().decode("utf-8")
    return files


def main():
    files = load_dict()
    models = {k[:-6]: [l.split() for l in v.splitlines() if l and not l.startswith("#")] for k, v in files.items() if k.endswith(".model")}
    freq = dict(l.split(", ") for l in files["frequencies-dict-lemmas.txt"].splitlines() if ", " in l)
    reflexive = set(fetch(REFLEX_URL).decode().split())
    # pre-2017 spellings (sóc, dóna, fóra…); the dict keeps both, learners only need the IEC one
    old = {l.split("=")[0] for l in fetch(OLD_DIACRITICS_URL).decode().splitlines() if "=" in l and not l.startswith("#")}

    verbs, forms, seen = [], [], set()
    for line in files["verbs-fdic.txt"].splitlines():
        m = re.match(r"^([^#=]+)=categories: V;model:([^;]+);", line)
        if not m:
            continue
        lemma, model = m.groups()
        if lemma in seen:  # dict has a couple of duplicate entries
            continue
        seen.add(lemma)
        verbs.append((lemma, model, int(freq.get(lemma, 0)), lemma in reflexive))
        for strip, add, _, tag, *_ in models[model]:
            form = apply_model(lemma, strip, add)
            if tag[7] in CENTRAL and form not in old:
                forms.append((lemma, *decode(tag), form))

    words = set()
    for line in files["diccionari.txt"].splitlines():
        form, lemma, tag = line.split(" ")[:3]
        pos = WORD_POS.get(tag[:2])
        if pos and form == form.lower():
            words.add((form, lemma, pos + tag[2].lower() if pos == "n" else pos))   # nf / nm / nc, a, r

    out = DATA / "verbs.sqlite"
    out.unlink(missing_ok=True)
    db = sqlite3.connect(out)
    db.executescript("""
        CREATE TABLE verbs(lemma TEXT PRIMARY KEY, model TEXT, freq INTEGER, reflexive INTEGER);
        CREATE TABLE forms(lemma TEXT, mood TEXT, tense TEXT, person TEXT, number TEXT, gender TEXT, form TEXT);
        CREATE INDEX forms_lemma ON forms(lemma);
        CREATE INDEX forms_form ON forms(form);
        CREATE TABLE words(form TEXT, lemma TEXT, pos TEXT);
        CREATE INDEX words_form ON words(form);
        CREATE INDEX words_lemma ON words(lemma, pos);
    """)
    db.executemany("INSERT INTO verbs VALUES (?,?,?,?)", verbs)
    db.executemany("INSERT INTO forms VALUES (?,?,?,?,?,?,?)", forms)
    db.executemany("INSERT INTO words VALUES (?,?,?)", sorted(words))
    db.commit()
    print(f"{len(verbs)} verbs, {len(forms)} forms, {len(words)} words -> {out}")


if __name__ == "__main__":
    main()
