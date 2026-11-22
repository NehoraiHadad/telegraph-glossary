import json
from pathlib import Path

import pytest

from telegraph_glossary.linker import link_text

SPEC = json.loads((Path(__file__).parent.parent / "spec" / "linker-cases.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", SPEC["cases"], ids=[c["name"] for c in SPEC["cases"]])
def test_spec(case):
    opts = case.get("options", {})
    r = link_text(case["text"], SPEC["terms"], mode=opts.get("mode", "first"), exclude=opts.get("exclude", []))
    assert r.html == case["expected_html"]
    assert r.found == case["expected_found"]


def test_dotless_i_does_not_crash_or_match():
    terms = [{"term": "i", "aliases": [], "url": "https://telegra.ph/I-1"}]
    r = link_text("\u0131 test", terms)
    assert r.html == "\u0131 test"
    assert r.found == []


def test_first_registered_wins_among_case_equivalent_forms():
    terms = [
        {"term": "Silk", "aliases": [], "url": "https://telegra.ph/A"},
        {"term": "silk", "aliases": ["\u017Filk"], "url": "https://telegra.ph/B"},
    ]
    r = link_text("\u017FILK", terms)
    assert r.html == '<a href="https://telegra.ph/A">\u017FILK</a>'
    assert r.found == ["Silk"]
