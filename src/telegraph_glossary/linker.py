"""Term linker: finds glossary terms in plain text and turns them into links.

Behavior-identical to web/core/linker.js; both are tested against
spec/linker-cases.json.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, Literal, Optional, Sequence

# One-to-three Hebrew prefix letters (ו ה ב כ ל מ ש) optionally followed by a maqaf/hyphen.
HEB_PREFIX = r"(?:[והבכלמש]{1,3}[-־]?)?"
# Spans that must never be touched: URLs, @mentions, #hashtags.
PROTECTED = re.compile(r"(?:https?://|www\.)\S+|[@#]\w+")

# Characters whose Unicode *simple* case folding has no single-character casefold()/lower().
_SIMPLE_FOLD_ONLY = {"\u1fd3": "\u0390", "\u1fe3": "\u03b0", "\ufb05": "\ufb06"}


def fold_char(c: str) -> str:
    """Unicode simple case folding of one character (the rule of JS ``/iu``).

    Matching must not use ``re.IGNORECASE``: Python's engine also equates
    dotless i (U+0131) with "i", which JS does not. Folding both text and forms with this
    function (always one character in, one character out, so offsets are kept)
    gives the same matches and the same lookup keys as ``linker.js``.
    """
    if c in _SIMPLE_FOLD_ONLY:
        return _SIMPLE_FOLD_ONLY[c]
    for folded in (c.casefold(), c.lower()):
        if len(folded) == 1:
            return folded
    return c


def fold(s: str) -> str:
    return "".join(map(fold_char, s))


@dataclass
class Term:
    term: str
    url: str
    aliases: list[str] = field(default_factory=list)


@dataclass
class Segment:
    text: str
    term: Optional[str] = None
    url: Optional[str] = None
    linked: bool = False


def escape_html(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _escape_attr(s: str) -> str:
    return escape_html(s).replace('"', "&quot;")


def _as_term(t) -> Term:
    if isinstance(t, Term):
        return t
    return Term(term=t["term"], url=t["url"], aliases=list(t.get("aliases") or []))


def find_terms(
    text: str,
    terms: Iterable,
    mode: Literal["first", "all"] = "first",
    exclude: Sequence[str] = (),
) -> tuple[list[Segment], list[str]]:
    """Split ``text`` into segments; return (segments, found canonical terms)."""
    excluded = {t.lower() for t in exclude}
    # Longest form first; the sort is stable, so among forms that fold equal the first
    # registered one wins (linker.js tries its alternatives in the same order).
    exact: dict[str, Term] = {}
    for t in map(_as_term, terms):
        for form in [t.term, *t.aliases]:
            f = form.strip()
            if f and f not in exact:
                exact[f] = t
    form_to_term: dict[str, Term] = {}
    for f in sorted(exact, key=len, reverse=True):
        form_to_term.setdefault(fold(f), exact[f])
    if not form_to_term:
        return ([Segment(text)] if text else []), []

    forms = list(form_to_term)
    pattern = re.compile(rf"(?<!\w)({HEB_PREFIX})({'|'.join(map(re.escape, forms))})(?!\w)")

    segments: list[Segment] = []
    found: list[str] = []
    seen: set[str] = set()

    def push(s: str) -> None:
        if not s:
            return
        if segments and segments[-1].term is None:
            segments[-1].text += s
        else:
            segments.append(Segment(s))

    def scan(chunk: str) -> None:
        pos = 0
        for m in pattern.finditer(fold(chunk)):
            t = form_to_term[m.group(2)]
            push(chunk[pos : m.start()] + chunk[m.start(1) : m.end(1)])
            form = chunk[m.start(2) : m.end(2)]
            key = t.term.lower()
            is_excluded = key in excluded
            linked = not is_excluded and (mode == "all" or key not in seen)
            if not is_excluded and key not in seen:
                seen.add(key)
                found.append(t.term)
            segments.append(Segment(form, t.term, t.url, linked))
            pos = m.end()
        push(chunk[pos:])

    pos = 0
    for m in PROTECTED.finditer(text):
        scan(text[pos : m.start()])
        push(m.group(0))
        pos = m.end()
    scan(text[pos:])
    return segments, found


def to_telegram_html(segments: Sequence[Segment]) -> str:
    return "".join(
        f'<a href="{_escape_attr(s.url or "")}">{escape_html(s.text)}</a>'
        if s.term is not None and s.linked
        else escape_html(s.text)
        for s in segments
    )


def _md_escape(s: str) -> str:
    return re.sub(r"([\[\]])", r"\\\1", s)


def to_markdown(segments: Sequence[Segment]) -> str:
    return "".join(
        f"[{_md_escape(s.text)}]({s.url})" if s.term is not None and s.linked else s.text for s in segments
    )


@dataclass
class LinkResult:
    html: str
    markdown: str
    found: list[str]
    segments: list[Segment]


def link_text(text: str, terms: Iterable, mode: str = "first", exclude: Sequence[str] = ()) -> LinkResult:
    segments, found = find_terms(text, terms, mode=mode, exclude=exclude)  # type: ignore[arg-type]
    return LinkResult(to_telegram_html(segments), to_markdown(segments), found, segments)
