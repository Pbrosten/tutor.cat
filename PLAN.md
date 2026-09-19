# Catalan-Helper — B1 tutoring service (plan)

Local-only, `docker compose up`. Three features: study guides, verb library, exercise generator. Central Catalan (Barcelona) only.
Level scope: B1 = CPNL "Nivell Elemental" (E1/E2/E3), content aligned to *Passos 2. Llibre de classe. Nivell Elemental* (2024, ISBN 9788410054752), 21 units (7 per module).

## Stack (deliberately small)

| Piece | Choice | Why |
|---|---|---|
| Server | Python 3.12, FastAPI + Jinja2 templates + HTMX | server-rendered, no JS build step |
| Storage | SQLite (stdlib) — one file, one volume | ~10k verbs × ~60 forms fits trivially; no Elasticsearch |
| Content | Markdown + YAML files in `content/` | editable in any editor, git-diffable |
| Verb data | Softcatalà `catalan-dict-tools` → `conjugador/extract.py` → JSON | already-solved problem, LGPL/GPL data |
| Deploy | `docker compose` with a single `app` service | nothing else needed |

Python deps: `fastapi uvicorn jinja2 markdown pyyaml`. That's the whole list.

```
Catalan-Helper/
├── compose.yaml
├── Dockerfile
├── app/
│   ├── main.py            # routes: /, /guides/{slug}, /verbs, /verbs/{lemma}, /exercises/...
│   ├── verbs.py           # SQLite lookup + tag decoding
│   ├── exercises.py       # generators (see §3)
│   └── templates/         # base.html, guide.html, verb.html, exercise.html
├── content/
│   ├── syllabus.yaml      # unit → topics → guide slugs → exercise types
│   ├── guides/*.md        # one file per grammar topic
│   └── exercises/*.yaml   # hand-authored item banks per topic
├── data/
│   ├── build_verbs.py     # one-shot: dict → verbs.sqlite (run in Dockerfile)
│   └── verbs.sqlite       # generated, git-ignored
└── tests/test_smoke.py    # one runnable check per non-trivial piece
```

## 1. Study guides

- One Markdown file per topic in `content/guides/`, front-matter: `title, unit, level, tags`.
- Rendered with `markdown` lib; a `verb:cantar` shortcode inlines a conjugation table from §2 so guides and verb data never drift.
- Index page built from `syllabus.yaml` (module → unit → topics). Each guide links to its exercises.
- Target length: 300–600 words + 1–2 tables + 5 examples. B1 = "just enough to do the exercises".

## 2. Verb conjugation library

**Source (Softcatalà):**
- `Softcatala/catalan-dict-tools` — master dictionary. `diccionari-arrel/verbs-fdic.txt` lists every verb with its conjugation model; `build-lt.sh` produces the flat `form<TAB>lemma<TAB>POS-tag` file with every inflected form.
- `Softcatala/conjugador` — `extract.py` reads that flat file and emits one JSON per verb into `data/jsons/`. Their web app (FastAPI + Elasticsearch + Docker) is more than we need; **take `extract.py` and the JSONs, skip Elasticsearch.**

**Build (`data/build_verbs.py`, runs once in the Dockerfile):**
1. Clone `catalan-dict-tools` at a pinned tag, run `build-lt.sh` (or download the release artifact).
2. Run `conjugador/extract.py` → JSONs.
3. Flatten into SQLite:
   ```sql
   verbs(lemma PK, model, is_regular, freq_rank)
   forms(lemma, mood, tense, person, form)   -- central Catalan only (Barcelona); dict variants dropped at build
   ```
   POS tags are EAGLES-style (`VMIP1S0` = Verb Main Indicative Present 1st Singular) — decode mood/tense/person from positions 2–5.
4. `freq_rank` from a Catalan frequency list so search results and drills prefer common verbs. If none is convenient, a hand list of ~300 B1 verbs from the book's glossary is enough.

**UI:**
- `/verbs?q=` — autocomplete over lemma *and* any inflected form (SQLite `LIKE` on 10k rows is instant; add FTS5 only if it isn't).
- `/verbs/{lemma}` — table per mood; columns = tenses, rows = persons. Toggle: show only B1 tenses / show all. Highlight irregular forms vs. model.
- Reverse lookup: type `vaig` → "anar, indicatiu present 1sg / auxiliar perifràstic".

**B1 tense set** (what the book systematises): present, passat perifràstic, pretèrit indefinit, imperfet, plusquamperfet, futur, condicional, imperatiu, present de subjuntiu, imperfet de subjuntiu, gerundi, participi.

## 3. Exercise generator

Two sources, one interface (`Exercise(prompt, answer, accept, hint, guide_slug)`):

**a) Data-driven (infinite, from verbs.sqlite):**
- Conjugate: `(cantar, imperfet, 3pl) → cantaven`
- Cloze in sentence templates: `Ahir {ells} ___ (anar) al cinema.` → `van anar`
- Pick-the-form (multiple choice, distractors = same verb other tense/person, or same tense other verb model)
- Tense contrast: perifràstic vs. indefinit vs. imperfet given a time marker (`ahir`, `aquest matí`, `abans`)
- Identify: given `hauríem` → tense + person

**b) Hand-authored banks (`content/exercises/<topic>.yaml`):**
Needed where data can't generate: pronoms febles, combinacions de pronoms, apostrofació, ser/estar, per/per a, relatius, connectors, preposicions.
```yaml
- type: cloze
  text: "Aquest llibre, ___ vaig comprar ahir."
  answer: ["el"]
  hint: "CD masculí singular"
- type: transform
  text: "Dona el llibre a la Maria."
  answer: ["Dona-l'hi", "Dona-l'hi."]
  guide: pronoms-combinacions
```
Item types: `cloze`, `choice`, `transform`, `order` (reorder words), `match`. Answers are lists; checker normalises case/accents/trailing punctuation.

**Flow:** `/exercises` → pick unit *or* topic → 10 items (mix of a+b, weighted by `syllabus.yaml`) → answer with HTMX inline check → summary with links to the relevant guides. No accounts, no persistence beyond the browser session (localStorage for streak if wanted).

## 4. B1 syllabus (`content/syllabus.yaml` skeleton)

Grouped by CPNL Elemental modules; **map to Passos 2 unit numbers/titles from the book's index** (fill in from the physical copy — the publisher doesn't publish the TOC).

**E1 (units 1–7)** — consolidation + past tenses
- Articles, apostrofació i contraccions; gènere i nombre
- Present d'indicatiu (models regulars, irregulars freqüents: ser, estar, tenir, fer, anar, venir, poder, voler, saber, dir)
- Passat perifràstic vs. pretèrit indefinit vs. imperfet
- Futur; perífrasis: haver de, caldre, poder, voler, acabar de, tornar a
- Pronoms febles CD/CI (el, la, els, les, en, ho, li, els, hi) — posició amb infinitiu/gerundi/imperatiu
- Demostratius, possessius, quantitatius, comparatius
- Hores, dates, preposicions de lloc i temps

**E2 (units 8–14)** — subjunctive + pronouns
- Plusquamperfet, condicional
- Imperatiu afirmatiu i negatiu
- Present de subjuntiu: formes + usos (voler que, cal que, perquè, quan futur)
- Combinacions de pronoms (me'l, te la, l'hi, la hi, els hi, se'n, n'hi)
- Relatius: que, què, qui, on, el qual
- Oracions subordinades (causals, finals, temporals)
- Numerals, ordinals

**E3 (units 15–21)** — text & nuance
- Imperfet de subjuntiu; condicionals (si + imperfet subj. → condicional)
- Estil indirecte
- Ser / estar; per / per a
- Passiva pronominal ("es venen pisos"), impersonals
- Gerundi i participi; perífrasis de probabilitat
- Connectors i marcadors textuals (però, tanmateix, per tant, d'una banda…)
- Lèxic per camps (salut, medi ambient, feina, habitatge — 2024 edition themes)

## 5. Delivery order

1. `compose.yaml` + `Dockerfile` + hello-world FastAPI (½ day)
2. Verb build script + `/verbs` pages — biggest value, all data, no authoring (1–2 days)
3. Data-driven exercises (§3a) — free once verbs exist (1 day)
4. Syllabus YAML + guide index + 3 guides + 1 YAML bank to prove the loop (1 day)
5. Author remaining guides/banks unit by unit, following the book (ongoing)

## Skipped, and when to add

- **Elasticsearch / Postgres** — add when SQLite `LIKE` over 10k lemmas is measurably slow (it won't be).
- **User accounts / progress tracking** — add when there's >1 user or you want spaced repetition; then a `results(user, item_id, ok, ts)` table.
- **LLM-generated exercises** — add when hand banks feel thin; the `Exercise` interface is the plug point. Keep data-driven drills as ground truth for answer checking.
- **SPA / React** — never, unless the HTMX pages stop being enough.

## Licensing note

`catalan-dict-tools` data is GPL/LGPL; `conjugador` code is LGPL 2.1+. Fine for local use; keep the attribution and the licence files if this ever leaves the machine.
