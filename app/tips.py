"""Wrap dictionary words (verb forms, nouns, adjectives, adverbs) in running text with <span class="vf" data-w="lemma:pos,…">
so the page can show a definition tooltip. ponytail: a stoplist of function words keeps 'la', 'que', 'per' quiet; homographs
('casa' noun/verb) just list every reading — the alternative is a POS tagger."""
import re
from html import escape

from app import verbs

STOP = set("""la les el els l un una uns unes al del pel als dels pels de a en i o u que què qui no sí si es se em et ens us hi ho li lo
per amb com més menys tot tots tota totes cap res mai ja ara aquí allà allí molt poc on quan fins sense sota entre cada ca
ell ella ells elles jo tu nosaltres vosaltres vostè vostès meu teu seu meva teva seva nostre vostre aquest aquell això allò
i tant tan bé mal sí també però sinó doncs perquè encara quasi gairebé prou massa gaire gens tal""".split())
WORD = re.compile(r"(?<![\w'’·-])([A-Za-zÀ-ÿ·]+(?:['’][A-Za-zÀ-ÿ·]+)*)(?![\w'’·-])")
TAG = re.compile(r"(<[^>]+>)")


def _wrap(m):
    w = m.group(1)
    low = w.lower()
    if len(low) < 2 or low in STOP or low.replace("'", "").replace("’", "") in STOP:
        return w
    if w[0].isupper() and m.string[:m.start()].rstrip()[-1:] not in ("", ".", "!", "?", ":"):
        return w   # capitalised mid-sentence = a name ('la Maria', not the noun 'maria')
    hits = verbs.lookup(low)
    if not hits:
        return w
    return f'<span class="vf" data-w="{",".join(f"{l}:{p}" for l, p in hits)}">{w}</span>'


def annotate_html(html):
    """Annotate text nodes of an HTML fragment (tags and attributes untouched)."""
    out, skip = [], 0
    for part in TAG.split(html):
        if part.startswith("<"):
            if re.match(r"<(code|pre|script|style)\b", part):
                skip += 1
            elif re.match(r"</(code|pre|script|style)\b", part):
                skip = max(0, skip - 1)
            out.append(part)
        else:
            out.append(part if skip else WORD.sub(_wrap, part))
    return "".join(out)


def annotate_text(text):
    """Escape plain text, then annotate."""
    return annotate_html(escape(text or ""))
