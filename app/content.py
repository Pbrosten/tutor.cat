"""Syllabus, markdown guides and YAML exercise banks under content/."""
import re
from functools import lru_cache
from pathlib import Path

import markdown
import yaml

from app import exercises, tips, verbs

CONTENT = Path(__file__).resolve().parent.parent / "content"


def syllabus():
    return yaml.safe_load((CONTENT / "syllabus.yaml").read_text())["modules"]


LANGS = ("ca", "en")   # ca = content/guides/<slug>.md (primary), en = content/guides/en/<slug>.md


def _guide_path(slug, lang="ca"):
    return CONTENT / "guides" / ("" if lang == "ca" else lang) / f"{slug}.md"


def guide_meta(slug, lang="ca"):
    """Front-matter only (cheap), or None if the guide isn't written yet."""
    p = _guide_path(slug, lang)
    if not p.exists():
        return None
    return {"slug": slug, "lang": lang, "exercises": [], **yaml.safe_load(p.read_text().split("---", 2)[1])}


@lru_cache(maxsize=64)  # ponytail: guides are static files; restart to pick up edits (same as the banks)
def guide(slug, lang="ca"):
    if lang not in LANGS or not _guide_path(slug, lang).exists():
        lang = "ca"
    meta = guide_meta(slug, lang)
    if not meta:
        return None
    body = _guide_path(slug, lang).read_text().split("---", 2)[2]
    body = re.sub(r"\{\{verb (\S+) (\S+)\}\}", lambda m: _verb_table(m[1], m[2]), body)
    html = tips.annotate_html(markdown.markdown(body, extensions=["tables", "toc"]))  # toc: gives the h2s ids to link to
    return {**meta, "html": html, "toc": re.findall(r'<h2 id="([^"]+)">(.*?)</h2>', html)}


def _verb_table(lemma, key):
    mood, tense = exercises.TENSES[key]
    forms = verbs.conjugation(lemma, all_tenses=True)["tables"][mood][tense]
    rows = "".join(f"<tr><th>{p}</th><td>{f}</td></tr>" for p, f in zip(verbs.PERSONS, forms))
    return f'<table class="verb striped"><caption>{lemma} — {tense or mood}</caption>{rows}</table>'


@lru_cache  # ponytail: banks reload on container restart; drop the cache if editing YAML live gets annoying
def banks():
    return {p.stem: yaml.safe_load(p.read_text()) for p in (CONTENT / "exercises").glob("*.yaml")}


def topics():
    """Everything a session can be built from: drill keys + bank names, with labels."""
    return {**exercises.TOPICS, **{k: (guide_meta(k) or {}).get("title", k) for k in banks()}}


def guide_order():
    """Guide slugs in syllabus order, each once (a topic can appear in several units)."""
    return list(dict.fromkeys(t for m in syllabus() for u in m["units"] for t in u["topics"] if guide_meta(t)))


def unit_keys(n):
    for mod in syllabus():
        for u in mod["units"]:
            if u["n"] == n:
                return [k for t in u["topics"] for k in (guide_meta(t) or {}).get("exercises", [])]
    return []
