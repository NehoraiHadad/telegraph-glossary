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
