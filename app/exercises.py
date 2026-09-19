"""Data-driven verb drills from verbs.sqlite. Every item is a plain dict:
{type, prompt, answer: [accepted...], options: [...] (choice only), hint, guide}
"""
import random
import re
import unicodedata

from app import verbs

# ponytail: hand list instead of dict frequencies (those are polluted by homographs: pelar, matar, metre…)
B1_VERBS = """ser estar haver tenir fer anar venir poder voler saber dir veure donar posar sortir entrar arribar
parlar menjar beure dormir viure treballar estudiar llegir escriure escoltar mirar buscar trobar comprar vendre
pagar obrir tancar agafar deixar portar dur pujar baixar caminar córrer jugar cantar ballar nedar cuinar netejar
rentar vestir despertar aixecar seure asseure començar acabar continuar tornar quedar passar canviar pensar creure
conèixer entendre aprendre ensenyar recordar oblidar preguntar respondre demanar explicar necessitar semblar
agradar caldre servir esperar perdre guanyar aconseguir intentar decidir preferir sentir plorar riure somriure
morir néixer créixer viatjar conduir trucar enviar rebre ajudar preparar provar visitar celebrar convidar
descansar esmorzar dinar sopar beure comptar pagar costar valer caure tocar treure moure pujar seguir triar
acompanyar apagar encendre escollir omplir repetir construir traduir dutxar llevar pentinar
maquillar afaitar casar separar enamorar divertir avorrir preocupar queixar recuperar sorprendre""".split()

TENSES = {
    "present": ("indicatiu", "present"), "imperfet": ("indicatiu", "imperfet"),
    "passat-perifrastic": ("indicatiu", "passat perifràstic"), "preterit-indefinit": ("indicatiu", "pretèrit indefinit"),
    "plusquamperfet": ("indicatiu", "plusquamperfet"), "futur": ("indicatiu", "futur"),
    "condicional": ("indicatiu", "condicional"), "subjuntiu-present": ("subjuntiu", "present"),
    "subjuntiu-imperfet": ("subjuntiu", "imperfet"), "imperatiu": ("imperatiu", ""),
}
TOPICS = {**{k: v[1] or k for k, v in TENSES.items()},
          "passats": "contrast de passats (perifràstic / indefinit / imperfet)", "tots": "tots els temps"}
# time markers that force a tense; used by cloze items
MARKERS = {
    "present": ["ara", "cada dia", "normalment", "els dilluns", "sempre"],
    "imperfet": ["abans", "de petit", "quan era jove", "cada estiu, de petit", "l'any passat, cada dia"],
    "passat-perifrastic": ["ahir", "la setmana passada", "l'any passat", "fa dos dies", "dissabte passat"],
    "preterit-indefinit": ["avui", "aquest matí", "aquesta setmana", "aquest any", "fa una estona"],
    "plusquamperfet": ["quan vas arribar,", "abans d'ahir,", "a les deu,"],
    "futur": ["demà", "l'any que ve", "la setmana que ve", "d'aquí a dos dies", "aviat"],
    "condicional": ["si pogués,", "amb més temps,", "si fos ric,", "en el teu lloc,"],
    "subjuntiu-present": ["vull que", "cal que", "espero que", "és important que", "potser"],
    "subjuntiu-imperfet": ["si", "voldria que", "m'agradaria que", "era important que"],
}
SUBJECTS = [["jo"], ["tu"], ["ell", "ella", "vostè"], ["nosaltres"], ["vosaltres"], ["ells", "elles", "vostès"]]
GUIDES = {k: "verbs-" + k for k in TENSES}
GUIDES.update(dict.fromkeys(["passat-perifrastic", "preterit-indefinit", "imperfet"], "verbs-passats"))
KEY_OF = {v: k for k, v in TENSES.items()}


def _subject(i, key):
    return ("vostè" if i == 2 else "vostès" if i == 5 else SUBJECTS[i][0]) if key == "imperatiu" else SUBJECTS[i][0]


def _norm(s):
    s = unicodedata.normalize("NFC", s.strip().lower())
    s = re.sub(r"\s*/\s*", " / ", s)   # multi-part answers: "tan/com" == "tan / com"
    return re.sub(r"\s+", " ", s).rstrip(".!?")


def check(given, accepted):
    """Case/whitespace/trailing punctuation insensitive; accents DO count (canta ≠ cantà)."""
    return _norm(given) in {_norm(a) for a in accepted}


def _forms(lemma, key):
    mood, tense = TENSES[key]
    c = verbs.conjugation(lemma, all_tenses=True)
    return [f for f in c["tables"][mood].get(tense, [])]


def _pick_person(forms):
    """Index of a person that exists (imperative has no 1sg)."""
    return random.choice([i for i, f in enumerate(forms) if f != "—"])


def _split(form):
    return [a.strip() for a in form.split("/")]


def conjugate(lemma, key):
    forms = _forms(lemma, key)
    i = _pick_person(forms)
    return {"type": "conjugate", "prompt": f"{lemma} — {TOPICS[key]}, {_subject(i, key)}",
            "answer": _split(forms[i]), "hint": None, "guide": GUIDES[key], "lemma": lemma, "person": i}


def cloze(lemma, key):
    forms = _forms(lemma, key)
    i = _pick_person(forms)
    subj = random.choice(SUBJECTS[i])
    m = random.choice(MARKERS[key])
    ja = " ja" if key == "plusquamperfet" else ""
    text = f"{m[0].upper() + m[1:]} {subj}{ja} ___ ({lemma})."
    return {"type": "cloze", "prompt": text, "answer": _split(forms[i]), "hint": TOPICS[key], "guide": GUIDES[key],
            "lemma": lemma, "person": i}


def choice(lemma, key, pool):
    forms = _forms(lemma, key)
    i = _pick_person(forms)
    right = _split(forms[i])[0]
    wrong = set()
    wrong.update(_split(f)[0] for j, f in enumerate(forms) if j != i and f != "—")          # same tense, other person
    other = random.choice([k for k in TENSES if k != key])
    wrong.update(_split(f)[0] for f in _forms(lemma, other) if f != "—")                     # other tense, same verb
    wrong.discard(right)
    opts = random.sample(sorted(wrong), min(3, len(wrong))) + [right]
    random.shuffle(opts)
    return {"type": "choice", "prompt": f"{lemma} — {TOPICS[key]}, {_subject(i, key)}",
            "answer": [right], "options": opts, "hint": None, "guide": GUIDES[key], "lemma": lemma, "person": i}


def identify(lemma, key):
    forms = _forms(lemma, key)
    i = _pick_person(forms)
    form = _split(forms[i])[0]
    right = f"{TOPICS[key]}, {_subject(i, key)}"
    # a form like "canteu" is present 2pl AND subjunctive AND imperative: none of those may be a distractor
    also = {f"{TOPICS[k]}, {_subject(verbs.KEYS.index((r['person'], r['number'])), k)}"
            for r in verbs.identify(form) if (k := KEY_OF.get((r["mood"], r["tense"]))) and (r["person"], r["number"]) in verbs.KEYS}
    wrong = {f"{TOPICS[k]}, {_subject(j, k)}" for k in TENSES for j in range(6)} - also - {right}
    opts = random.sample(sorted(wrong), 3) + [right]
    random.shuffle(opts)
    return {"type": "choice", "prompt": f"«{form}» ({lemma}) és…",
            "answer": [right], "options": opts, "hint": None, "guide": GUIDES[key], "lemma": lemma, "person": i, "form": form}


def ident(it):
    """What makes an item 'the same exercise': its prompt plus its options (banks reuse prompts like 'Which one is correct?')."""
    return (it.get("prompt") or it["text"], tuple(it.get("options") or ()))


def bank_item(name, items, seen=()):
    """Random bank item not in `seen`; None if the bank is exhausted."""
    pool = [it for it in items if ident(it) not in seen]
    if not pool:
        return None
    it = random.choice(pool)
    return {"type": it["type"], "prompt": it["text"], "answer": it["answer"], "options": it.get("options"),
            "hint": it.get("hint"), "guide": name}


def make(key, banks=None, seen=()):
    """One item for a drill key or a bank name, with a prompt not in `seen`; None if it can't."""
    if key in (banks or {}):
        it = bank_item(key, banks[key], seen)
        return {**it, "key": key} if it else None
    makers = [conjugate, cloze, lambda l, k: choice(l, k, B1_VERBS), identify] if key in MARKERS \
        else [conjugate, lambda l, k: choice(l, k, B1_VERBS), identify]
    for _ in range(30):  # drills are random; retry until the prompt is new
        try:
            it = random.choice(makers)(random.choice(B1_VERBS), key)
        except IndexError:  # defective verb (caldre has no imperative): draw another one
            continue
        if ident(it) not in seen:
            return {**it, "key": key}
    return None


def session(keys, n=10, banks=None, retry=()):
    """keys: drill keys (TENSES / passats / tots) and/or bank names, round-robin (repeat a key to weight it).
    retry: (key, prompt) pairs of bank items to replay verbatim, used first. No prompt appears twice."""
    expanded = []
    for k in keys:
        expanded += {"passats": ["passat-perifrastic", "preterit-indefinit", "imperfet"], "tots": list(TENSES)}.get(k, [k])
    random.shuffle(expanded)
    items, seen = [], set()
    for key, prompt in retry:
        src = next((it for it in (banks or {}).get(key, []) if it["text"] == prompt), None)
        if src and ident(src) not in seen and len(items) < n:
            items.append({**bank_item(key, [src]), "key": key})
            seen.add(ident(src))
    i = 0
    while len(items) < n and expanded:
        it = make(expanded[i % len(expanded)], banks, seen)
        if it:
            items.append(it)
            seen.add(ident(it))
        else:  # ponytail: key exhausted (bank smaller than n) -> drop it; a short series beats a repeated item
            expanded.pop(i % len(expanded))
            continue
        i += 1
    random.shuffle(items)
    return items


# ---------------------------------------------------------------- grading, full sentences, explanations
REASONS = {
    "present": "un hàbit o una acció que passa ara",
    "imperfet": "un hàbit, una descripció o el rerefons en el passat (abans, de petit, cada dia…)",
    "passat-perifrastic": "una acció acabada en un període ja tancat (ahir, l'any passat…)",
    "preterit-indefinit": "una acció acabada en un període que inclou ara (avui, aquesta setmana…)",
    "plusquamperfet": "una acció ja acabada abans d'una altra acció passada (ja, quan vas arribar…)",
    "futur": "un pla o una predicció (demà, l'any que ve…)",
    "condicional": "una hipòtesi o un desig cortès (si pogués…, amb més temps…)",
    "subjuntiu-present": "una subordinada després de voluntat, necessitat, sentiment o dubte (vull que, cal que, espero que…)",
    "subjuntiu-imperfet": "una condició hipotètica o un desencadenant en passat (si…, voldria que…)",
    "imperatiu": "una ordre o una petició",
}
COMPOUND = {**{a: "preterit-indefinit" for a in verbs.HAVER_PRES}, **{a: "plusquamperfet" for a in verbs.HAVER_IMPF},
            **{a: "passat-perifrastic" for a in verbs.ANAR_AUX}}


def _strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def full_sentence(item, answer=None):
    """The prompt with the blank filled: 'Ahir jo ___ (cantar).' -> 'Ahir jo vaig cantar.'"""
    answer = answer or item["answer"][0]
    text = item["prompt"]
    if "___" not in text:
        return answer
    parts = [a.strip() for a in answer.split(" / ")]
    if text.count("___") != len(parts):
        parts = [answer] * text.count("___")
    for a in parts:
        blank = " ___" if a[:1] in "-'’" and " ___" in text else "___"   # enclitic: "portar ___" + "-hi" -> "portar-hi"
        text = text.replace(blank, a, 1)
    text = re.sub(r" \([a-zç·l'-]+\)\.?$", ".", text) if item.get("lemma") else text     # drop the '(cantar)' cue
    text = re.sub(r"(['’])\s+(?=\w)", r"\1", text)                                        # "L' Anna" -> "L'Anna"
    text = re.sub(r"(— )(\w)", lambda m: m[1] + m[2].upper(), text)                          # "— està" -> "— Està"
    return text[0].upper() + text[1:] if text else text


def _label_to_forms(lemma, label):
    """'imperfet, nosaltres' -> the conjugated form, or None."""
    try:
        tense_label, subj = [x.strip() for x in label.split(",", 1)]
        key = next(k for k, v in TOPICS.items() if v == tense_label and k in TENSES)
        i = next(i for i in range(6) if subj in SUBJECTS[i] or subj == _subject(i, key))
        return _forms(lemma, key)[i]
    except (ValueError, StopIteration):
        return None


def explain(item, given):
    """Una o dues frases sobre per què la resposta esperada és millor que `given`. Basat en regles; un LLM pot substituir-ho (llm_explain)."""
    answer, g = item["answer"][0], _norm(given)
    if not g:
        return f"Sense resposta. S'esperava «{answer}»."
    if _strip_accents(g) == _strip_accents(_norm(answer)):
        return f"Només canvia l'accent: la grafia correcta és «{answer}». En català l'accent pot canviar la forma (canta / cantà)."
    if g.replace("'", "").replace(" ", "") == _norm(answer).replace("'", "").replace(" ", ""):
        return f"Mateixes lletres, però l'apòstrof o l'espai són diferents: la forma escrita correcta és «{answer}»."

    lemma, key = item.get("lemma"), item.get("key")
    if lemma and key in TENSES and item["type"] != "choice" or (lemma and "form" not in item and item["type"] == "choice"):
        want = f"{TOPICS[key]}, {_subject(item['person'], key)}"
        words = g.split()
        # què ha escrit l'aprenent?
        if len(words) == 2 and words[0] in COMPOUND:
            k2 = COMPOUND[words[0]]
            who = {h["lemma"] for h in verbs.identify(words[1])} | ({words[1]} if verbs.conjugation(words[1]) else set())
            head = f"«{given}» és {TOPICS[k2]}"
            if who and lemma not in who:
                head += f" de «{sorted(who)[0]}», no de «{lemma}»"
            elif k2 == key:
                head += ", però d'una altra persona"
        else:
            hits = [h for h in verbs.identify(words[-1]) if (h["mood"], h["tense"]) in KEY_OF]
            same = [h for h in hits if h["lemma"] == lemma]
            if same:
                h = same[0]
                head = f"«{given}» és {TOPICS[KEY_OF[(h['mood'], h['tense'])]]}, {h['label']} de {lemma}"
            elif hits:
                head = f"«{given}» és una forma de «{hits[0]['lemma']}», no de «{lemma}»"
            else:
                head = f"«{given}» no és cap forma de «{lemma}»"
        return f"{head}. La frase demana {want} — {REASONS[key]}: «{answer}»."

    if item.get("form"):  # identify: l'aprenent ha triat l'etiqueta equivocada
        other = _label_to_forms(lemma, given)
        tail = f" «{given}» seria «{other}»." if other and other != "—" else ""
        return f"«{item['form']}» és {answer} de {lemma}.{tail}"

    hint = item.get("hint")
    return (f"Regla: {hint}. " if hint else "") + f"La forma correcta és «{answer}»" + (f", no «{given}»." if g else ".")


def grade(items, givens):
    """items + parallel answers -> per-item result dicts."""
    out = []
    for it, given in zip(items, givens):
        ok = check(given, it["answer"])
        out.append({**it, "given": given, "ok": ok, "sentence": full_sentence(it),
                    "why": None if ok else explain(it, given)})
    return out


def llm_explain(results):
    """Optionally replace rule-based explanations with Claude's, for the wrong answers. Silent no-op without credentials."""
    import os
    wrong = [r for r in results if not r["ok"]]
    if not wrong or not os.environ.get("LLM_API_KEY"):
        return
    try:
        import anthropic
        from pydantic import BaseModel

        class Item(BaseModel):
            index: int
            why: str

        class Out(BaseModel):
            items: list[Item]

        listing = "\n".join(f"{i}. Exercici: {r['prompt']}" + (f" (opcions: {', '.join(r['options'])})" if r.get("options") else "")
                            + f"\n   L'aprenent ha escrit: {r['given'] or '(res)'}\n   Correcte: {' / '.join(r['answer'])}"
                            + (f"\n   Pista: {r['hint']}" if r.get("hint") else "") for i, r in enumerate(wrong))
        resp = anthropic.Anthropic(api_key=os.environ["LLM_API_KEY"], timeout=25.0, max_retries=1).messages.parse(
            model="claude-opus-5", max_tokens=4000, output_config={"effort": "low"},
            system="Ets professor/a de català (català central, estàndard de Barcelona, ortografia IEC 2017) i corregeixes un aprenent de B1. "
                   "Per a cada exercici explica en català senzill, en dues frases curtes com a màxim, per què la resposta correcta ho és i "
                   "què falla en el que ha escrit l'aprenent (temps, persona, concordança, ortografia, pronom…). "
                   "Sigues concret; cita les formes entre «». No elogiïs.",
            messages=[{"role": "user", "content": listing}], output_format=Out)
        for it in resp.parsed_output.items:
            if 0 <= it.index < len(wrong) and it.why.strip():
                wrong[it.index]["why"] = it.why.strip()
    except Exception as e:  # ponytail: explanations are a nicety; never break grading
        print("llm_explain:", e)
