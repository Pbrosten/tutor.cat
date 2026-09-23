# Incorrect tooltips

Log of wrong/misleading word tooltips. Fix in one batch once the list is long enough.
Check a word with: `docker compose run --rm app python -c "from app import verbs; print(verbs.lookup('WORD'), verbs.identify('WORD'))"`

| Word | Shown | Should be | Cause |
|------|-------|-----------|-------|
| matí | `matar:v` (+ `matí:nm`) | noun only (*morning*) | `matí` is the literary *passat simple* 1S of *matar* — a real form, but not B1 and never the intended reading. Likely fix: drop `passat simple` rows from `verbs.lookup` (already outside `B1_TENSES`). |
| escolta | `escolta:a`, `escolta_1:nf`, `escolta_2:nc` — verb missing | `escoltar:v` first, plus the noun (*scout*) | Two bugs. (1) `verbs.lookup` sorts by lemma and `/tip` keeps only the first 3 readings, so `escoltar:v` (4th) is cut. Fix: order verb readings first, or raise the cap. (2) LT homonym suffixes `_1`/`_2` leak from `diccionari.txt` into 241 lemmas (`albor_1`, `alfabet_2`…) — they break the Viccionari lookup (404) and look wrong. Fix in `build_verbs.py`: strip `_\d+$` from the lemma. |
