"""Verb definitions: Catalan from the Viccionari, English from the English Wiktionary. Fetched on demand, cached in
data/definitions.sqlite. Offline -> empty lists (and we retry next time). Softcatalà's conjugador does the same from a dump;
ponytail: two small HTTP calls beat a 1 GB XML import for a single-user tool."""
import html
import json
import re
import sqlite3
import urllib.parse
import urllib.request
from pathlib import Path

DB = Path(__file__).resolve().parent.parent / "data" / "definitions.sqlite"
UA = {"User-Agent": "CatalanHelper/1.0 (local learning tool)"}
CA_API = "https://ca.wiktionary.org/w/api.php?action=parse&prop=wikitext&format=json&formatversion=2&page="
EN_API = "https://en.wiktionary.org/api/rest_v1/page/definition/"


def _fetch(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=6).read().decode()


def _clean(wiki):
    """Strip enough wiki markup from a definition line to read it as plain text."""
    s = re.sub(r"<ref[^>]*>.*?</ref>|<ref[^>]*/>", "", wiki)
    s = re.sub(r"\{\{marca\|ca\|([^}]*)\}\}", lambda m: "(" + m.group(1).replace("|", ", ") + ")", s)   # {{marca|ca|esports}} -> (esports)
    s = re.sub(r"\{\{[^{}]*\}\}", "", s)
    s = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", s)
    s = re.sub(r"'''?", "", s)
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\s+", " ", s).strip(" .") + "."


def parse_ca(wikitext):
    """Definition lines ('# …') of the verb section inside the Catalan block of a Viccionari page."""
    m = re.search(r"==\s*\{\{-ca-\}\}\s*==(.*?)(?=\n==\s*\{\{-\w+-\}\}\s*==|\Z)", wikitext, re.S)
    if not m:
        return []
    verb = re.search(r"===\s*Verb\s*===(.*?)(?=\n===[^=]|\Z)", m.group(1), re.S)
    return [_clean(l[2:]) for l in (verb.group(1) if verb else "").splitlines() if l.startswith("# ")][:6]


def parse_en(payload):
    out = []
    for block in json.loads(payload).get("ca", []):
        if block.get("partOfSpeech") == "Verb":
            out += [html.unescape(re.sub(r"<[^>]+>", "", d["definition"])).strip() for d in block["definitions"]]
    return [d for d in out if d][:6]


def _db():
    con = sqlite3.connect(DB)
    con.execute("CREATE TABLE IF NOT EXISTS defs(lemma TEXT PRIMARY KEY, ca TEXT, en TEXT)")
    return con


def get(lemma):
    """{'ca': [...], 'en': [...]} — cached once both lookups succeeded."""
    with _db() as con:
        row = con.execute("SELECT ca, en FROM defs WHERE lemma = ?", (lemma,)).fetchone()
    if row:
        return {"ca": json.loads(row[0]), "en": json.loads(row[1])}
    ca = en = None
    try:
        ca = parse_ca(json.loads(_fetch(CA_API + urllib.parse.quote(lemma))).get("parse", {}).get("wikitext", ""))
    except Exception:
        pass
    try:
        en = parse_en(_fetch(EN_API + urllib.parse.quote(lemma)))
    except Exception:  # 404 = no entry; treat as empty but cacheable only if the other side worked too
        en = []
    if ca is not None:
        with _db() as con:
            con.execute("INSERT OR REPLACE INTO defs VALUES (?,?,?)", (lemma, json.dumps(ca), json.dumps(en)))
    return {"ca": ca or [], "en": en or []}
