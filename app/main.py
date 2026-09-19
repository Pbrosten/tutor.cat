import json
import re
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app import badges, content, definitions, exercises, progress, tips, verbs

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content"

app = FastAPI(title="Catalan Helper")
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
templates.env.globals["user_of"] = lambda request: request.cookies.get("user")
templates.env.globals["unseen_badges"] = lambda request: badges.unseen(request.cookies["user"]) if "user" in request.cookies else 0


@app.middleware("http")
async def badge_toasts(request: Request, call_next):
    """Any page after a badge is earned shows a toast once (the results page also lists them inline)."""
    user = request.cookies.get("user")
    request.state.toasts = badges.pop_toasts(user) if user and request.method == "GET" and "." not in request.url.path else []
    return await call_next(request)


def number_blanks(prompt):
    """'___ Anna i ___ Joan' -> '___₁ Anna i ___₂ Joan' when there is more than one blank."""
    if prompt.count("___") < 2:
        return prompt
    n = iter("₁₂₃₄₅₆₇₈₉")
    return re.sub("___", lambda m: "___" + next(n), prompt)


templates.env.filters["number_blanks"] = number_blanks
templates.env.filters["verbtips"] = lambda text: tips.annotate_text(text)


def user_of(request):
    return request.cookies.get("user")


@app.get("/")
def index(request: Request):
    return templates.TemplateResponse(request, "index.html")


@app.get("/verbs")
def verbs_page(request: Request, q: str = ""):
    return templates.TemplateResponse(request, "verbs.html", _results(q))


@app.get("/verbs/cerca")
def verbs_search(request: Request, q: str = ""):
    return templates.TemplateResponse(request, "verbs_results.html", _results(q))


def _results(q):
    return {"q": q, "hits": verbs.search(q), "ids": verbs.identify(q)}


@app.get("/verbs/tip/{lemmas}")
def verb_tip(request: Request, lemmas: str):
    """Tooltip body: definitions (ca + en) for one or more comma-separated lemmas."""
    items = [(l, definitions.get(l)) for l in lemmas.split(",")[:3] if verbs.conjugation(l)]
    if not items:
        raise HTTPException(404)
    return templates.TemplateResponse(request, "tip.html", {"items": items})


@app.get("/verbs/{lemma}")
def verb_page(request: Request, lemma: str, tot: bool = False, def_lang: str = "ca"):
    c = verbs.conjugation(lemma, all_tenses=tot)
    if not c:
        raise HTTPException(404)
    return templates.TemplateResponse(request, "verb.html", {"c": c, "all": tot, "persons": verbs.PERSONS,
                                                             "defs": definitions.get(lemma), "def_lang": "en" if def_lang == "en" else "ca"})


@app.get("/guies")
def guides_index(request: Request):
    mods = content.syllabus()
    titles = {t: (content.guide_meta(t) or {}).get("title") for m in mods for u in m["units"] for t in u["topics"]}
    status = progress.guide_status(user_of(request)) if user_of(request) else {}
    return templates.TemplateResponse(request, "guies.html", {"modules": mods, "titles": titles, "status": status})


@app.get("/guies/{slug}")
def guide_page(request: Request, slug: str, lang: str = "ca"):
    g = content.guide(slug, lang)
    if not g:
        raise HTTPException(404, "Guia pendent d'escriure")
    user, status, passed, rounds = user_of(request), {}, None, 0
    if user:
        progress.touch_guide(user, slug)
        status = progress.guide_status(user).get(slug, {})
        passed = progress.guide_passed(user, slug)
        rounds = len(progress.guide_rounds(user, slug))
    order = content.guide_order()
    i = order.index(slug) if slug in order else -1
    nxt = order[i + 1] if i >= 0 and i + 1 < len(order) else None
    prv = order[i - 1] if i > 0 else None
    return templates.TemplateResponse(request, "guia.html", {"g": g, "topics": content.topics(), "status": status, "passed": passed, "rounds": rounds, "pass_rounds": progress.rounds_required(slug),
                                                             "lang": g["lang"], "has_en": content.guide_meta(slug, "en") is not None,
                                                             "next": {"slug": nxt, "title": content.guide_meta(nxt)["title"]} if nxt else None,
                                                             "prev": {"slug": prv, "title": content.guide_meta(prv)["title"]} if prv else None,
                                                             "pass_n": progress.PASS_MIN_ITEMS, "pass_score": round(progress.PASS_RATIO * progress.PASS_MIN_ITEMS)})


@app.post("/guies/{slug}/llegida")
def guide_toggle_read(request: Request, slug: str):
    if user_of(request):
        progress.toggle_guide_read(user_of(request), slug)  # refuses until a qualifying round exists
        badges.award(user_of(request))
    return RedirectResponse(f"/guies/{slug}", status_code=303)


@app.get("/exercicis")
def exercises_page(request: Request):
    user = user_of(request)
    return templates.TemplateResponse(request, "exercicis.html", {
        "topics": content.topics(), "modules": content.syllabus(),
        "weak": progress.weak_keys(user) if user else [], "sets": progress.sets(user) if user else []})


@app.get("/exercicis/sessio")
def exercises_session(request: Request, tema: str = "", unitat: int = 0, guia: str = "", personal: int = 0, set: int = 0, n: int = 10):
    topics, user, retry = content.topics(), user_of(request), ()
    if guia:
        g = content.guide_meta(guia)
        keys, title = (g or {}).get("exercises", []), (g or {}).get("title", "")
        n = max(n, progress.PASS_MIN_ITEMS)  # a guide round must be long enough to count
    elif unitat:
        keys, title = content.unit_keys(unitat), f"Unitat {unitat}"
    elif set and user and (s := progress.get_set(user, set)):
        keys, title = s["topics"], s["name"]
    elif personal and user:
        weak = progress.weak_keys(user)
        # weakest topic gets the most items; failed bank items are replayed first
        keys = [k for i, k in enumerate(weak) for _ in range(len(weak) - i)]
        retry = progress.failed_prompts(user, limit=max(1, n // 3))
        title = "Sèrie personalitzada"
    else:
        keys, title = [tema], topics.get(tema, "")
    if not keys or any(k not in topics for k in keys):
        raise HTTPException(404, "Sense exercicis: tema desconegut o encara no hi ha prou respostes")
    items = exercises.session(keys, min(n, 50), content.banks(), retry)
    return templates.TemplateResponse(request, "sessio.html", {"title": title, "items": items, "guia": guia, "query": str(request.url.query),
                                                               "pass_score": round(progress.PASS_RATIO * len(items)),
                                                               "pass_rounds": progress.rounds_required(guia) if guia else progress.PASS_ROUNDS})


@app.post("/exercicis/sessio/corregeix")
async def exercises_grade(request: Request):
    form = await request.form()
    items = json.loads(form.get("items", "[]"))
    def given(i):  # multi-blank items post one field per part; join them the way the answer key is written
        parts = [form.get(f"given_{i}_{j}", "") for j in range(items[i]["prompt"].count("___"))]
        return " / ".join(p.strip() for p in parts) if f"given_{i}_0" in form else form.get(f"given_{i}", "")
    results = exercises.grade(items, [given(i) for i in range(len(items))])
    exercises.llm_explain(results)
    correct, user, guia = sum(r["ok"] for r in results), user_of(request), form.get("guia", "")
    passed, rounds, new_badges = None, 0, []
    if user:
        for r in results:
            progress.record(user, r["key"], r["type"], r["prompt"], r["given"], r["ok"])
        query = form.get("query", "")
        kind = next((k for k in ("guia", "unitat", "personal", "set") if query.startswith(k + "=")), "tema")
        progress.record_session(user, guia, len(results), correct, kind)
        if guia:
            passed = progress.guide_passed(user, guia)
            rounds = len(progress.guide_rounds(user, guia))
        new_badges = badges.award(user)
    return templates.TemplateResponse(request, "resultats.html", {
        "title": form.get("title", "Resultats"), "results": results, "correct": correct, "guia": guia, "passed": passed,
        "rounds": rounds, "pass_rounds": progress.rounds_required(guia) if guia else progress.PASS_ROUNDS, "new_badges": new_badges, "qualified": correct >= progress.PASS_RATIO * len(results) and len(results) >= progress.PASS_MIN_ITEMS,
        "guide_title": (content.guide_meta(guia) or {}).get("title") if guia else None, "query": form.get("query", ""),
        "topics": content.topics()})


# --- profile
@app.get("/perfil")
def profile(request: Request):
    user = user_of(request)
    ctx = {"users": progress.users(), "topics": content.topics()}
    if user:
        mods = content.syllabus()
        slugs = list(dict.fromkeys(t for m in mods for u in m["units"] for t in u["topics"] if content.guide_meta(t)))
        status = progress.guide_status(user)
        badges.award(user)  # retroactive: history earned before the feature existed counts too
        ctx.update(badges=badges.shelf(user), groups=badges.GROUPS, stats=progress.stats(user), weak=progress.weak_keys(user), sets=progress.sets(user),
                   recent=progress.recent(user), guides_total=len(slugs),
                   guides_read=sum(1 for s in slugs if status.get(s, {}).get("read")),
                   guides_seen=sum(1 for s in slugs if s in status),
                   titles={s: content.guide_meta(s)["title"] for s in slugs}, status=status,
                   # per module, each guide once, in syllabus order (a topic can span several units)
                   by_module=[(m["name"], list(dict.fromkeys(t for u in m["units"] for t in u["topics"] if content.guide_meta(t)))) for m in mods])
    resp = templates.TemplateResponse(request, "perfil.html", ctx)
    if user:
        badges.mark_seen(user)
    return resp


@app.post("/perfil/entra")
def profile_login(name: str = Form()):
    name = progress.ensure_user(name)
    r = RedirectResponse("/perfil", status_code=303)
    if name:
        r.set_cookie("user", name, max_age=10 * 365 * 24 * 3600, samesite="lax")
    return r


@app.post("/perfil/surt")
def profile_logout():
    r = RedirectResponse("/perfil", status_code=303)
    r.delete_cookie("user")
    return r


@app.post("/perfil/sets")
def profile_add_set(request: Request, name: str = Form(""), keys: list[str] = Form()):
    if user_of(request):
        progress.add_set(user_of(request), name, [k for k in keys if k in content.topics()])
    return RedirectResponse("/perfil", status_code=303)


@app.post("/perfil/sets/{set_id}/esborra")
def profile_delete_set(request: Request, set_id: int):
    if user_of(request):
        progress.delete_set(user_of(request), set_id)
    return RedirectResponse("/perfil", status_code=303)
