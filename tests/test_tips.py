"""python tests/test_tips.py — needs data/verbs.sqlite."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import tips  # noqa: E402


def test_annotate():
    out = tips.annotate_text("Ahir la Maria va cantar que sí.")
    assert '<span class="vf" data-w="cantar:v">cantar</span>' in out and 'anar:v' in out and 'data-w="ahir:nm,ahir:r">Ahir' in out
    assert "la Maria" in out and 'data-w="ser:v"' not in out              # stoplist + names untouched
    assert 'data-w="casa:nf,casar:v">casa<' in tips.annotate_text("casa") # noun and verb readings, gender on the noun
    assert 'data-w="ràpidament:r">' in tips.annotate_text("ràpidament") and 'data-w="bo:a">bona<' in tips.annotate_text("bona")
    html = tips.annotate_html('<p>Ell <strong>cantava</strong> — <a href="/x">vegeu</a> <code>cantava</code></p>')
    assert '<strong><span class="vf" data-w="cantar:v">cantava</span></strong>' in html
    assert "<code>cantava</code>" in html and 'href="/x"' in html          # code untouched, attributes untouched
    assert tips.annotate_text("<b>x</b>") == "&lt;b&gt;x&lt;/b&gt;"            # plain text is escaped first


if __name__ == "__main__":
    test_annotate(); print("ok")
