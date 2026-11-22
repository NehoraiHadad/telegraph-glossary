"""Glossary storage on Telegraph (format: docs/FORMAT.md; mirrors web/core/glossary.js)."""

from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Optional
from urllib.parse import quote, unquote

import httpx

from .autolink import APP_URL
from .markdown import markdown_to_nodes, nodes_to_markdown

API = "https://api.telegra.ph"
ALIAS_SEP = " · "
# https://telegra.ph/api: "content (Array of Node, up to 64 KB)". Assumed (not verified with a
# real call) to measure the JSON-serialized `content` parameter in UTF-8 bytes, which is what
# `to_json` produces and `_call` sends. Same constant and measure in web/core/glossary.js.
PAGE_LIMIT_BYTES = 64 * 1024


class TelegraphError(Exception):
    pass


class GlossaryFullError(ValueError):
    pass


def to_json(value: Any) -> str:
    """The exact text sent for a non-string API parameter (compact, like JS JSON.stringify)."""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def content_bytes(nodes: list[Any]) -> int:
    return len(to_json(nodes).encode("utf-8"))


def page_url(path: str) -> str:
    return f"https://telegra.ph/{quote(path, safe='')}"


def path_from_url(url: Optional[str]) -> Optional[str]:
    """Accepts absolute and relative (Telegraph rewrites its own links) forms."""
    m = re.match(r"^(?:https?://(?:telegra\.ph|graph\.org))?/([^?#/]+)$", url or "")
    return unquote(m.group(1)) if m else None


@dataclass
class Entry:
    term: str
    path: str
    aliases: list[str] = field(default_factory=list)

    @property
    def url(self) -> str:
        return page_url(self.path)

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "url": self.url}


def _text_of(nodes: list[Any]) -> str:
    return "".join(n if isinstance(n, str) else _text_of(n.get("children", [])) for n in nodes or [])


def parse_index(nodes: list[Any]) -> list[Entry]:
    terms = []
    for n in nodes or []:
        if isinstance(n, str) or n.get("tag") != "p":
            continue
        children = n.get("children") or []
        if not children or isinstance(children[0], str) or children[0].get("tag") != "a":
            continue
        path = path_from_url((children[0].get("attrs") or {}).get("href"))
        term = _text_of(children[0].get("children", [])).strip()
        if not path or not term:
            continue
        tail = _text_of(children[1:]).strip()
        if tail.startswith(ALIAS_SEP.strip()):
            tail = tail[len(ALIAS_SEP.strip()) :]
        aliases = [a.strip() for a in tail.split(",") if a.strip()]
        terms.append(Entry(term, path, aliases))
    return terms


def build_index(terms: list[Entry]) -> list[Any]:
    items = sorted(terms, key=lambda t: t.term.lower())
    nodes: list[Any] = [
        {"tag": "p", "children": [{"tag": "em", "children": [f"{len(items)} · ", {"tag": "a", "attrs": {"href": APP_URL}, "children": ["Telegraph Glossary"]}]}]}
    ]
    for t in items:
        kids: list[Any] = [{"tag": "a", "attrs": {"href": page_url(t.path)}, "children": [t.term]}]
        if t.aliases:
            kids.append(ALIAS_SEP + ", ".join(t.aliases))
        nodes.append({"tag": "p", "children": kids})
    if not items:
        nodes.append({"tag": "p", "children": ["—"]})
    return nodes


def projected_path(term: str) -> str:
    """Stand-in for the path Telegraph will give a new page, used only to size the index before
    the page exists. Assumes Telegraph's observed form: the title with spaces as "-", then "-MM-DD"
    and a "-N" suffix on collisions (here the longest date and a 3-digit suffix)."""
    return re.sub(r"\s+", "-", term) + "-12-31-999"


def check_index_fits(terms: list[Entry]) -> None:
    """Raise before any page is written if the index that `terms` builds is over Telegraph's limit.
    Otherwise a new term page is created and then orphaned when the index write is rejected."""
    size = content_bytes(build_index(terms))
    if size > PAGE_LIMIT_BYTES:
        raise GlossaryFullError(
            f"The glossary is full: Telegraph limits a page to 64 KB, and the index would be {size / 1024:.1f} KB. "
            "Remove terms or shorten aliases first."
        )


def clean_aliases(aliases: list[str], term: str) -> list[str]:
    seen = {term.strip().lower()}
    out = []
    for a in aliases or []:
        s = re.sub(r"\s+", " ", re.sub(r"[,·]", " ", a)).strip()
        if s and s.lower() not in seen:
            seen.add(s.lower())
            out.append(s)
    return out


class Glossary:
    def __init__(self, token: str, client: Optional[httpx.Client] = None):
        self.token = token
        self.http = client or httpx.Client(timeout=30)
        self.account: dict[str, Any] = {}
        self.index_path: Optional[str] = None
        self.title = ""
        self.terms: list[Entry] = []
        self.settle_s = 1.5  # see update_index

    # -- low level -----------------------------------------------------------
    def _call(self, method: str, params: Optional[dict] = None, auth: bool = True) -> Any:
        data = {}
        for k, v in {**({"access_token": self.token} if auth else {}), **(params or {})}.items():
            if v is not None:
                data[k] = v if isinstance(v, str) else to_json(v)
        r = self.http.post(f"{API}/{method}", data=data).json()
        if not r.get("ok"):
            raise TelegraphError(r.get("error") or f"Telegraph {method} failed")
        return r["result"]

    # -- lifecycle -----------------------------------------------------------
    @classmethod
    def create(cls, title: str = "Glossary", author_name: str = "") -> "Glossary":
        tmp = cls("")
        short = (title or "Glossary")[:32]
        acc = tmp._call("createAccount", {"short_name": short, "author_name": author_name or short}, auth=False)
        g = cls(acc["access_token"], tmp.http)
        g.title = title or "Glossary"
        page = g._call("createPage", {"title": g.title, "author_name": acc["author_name"], "content": build_index([])})
        g.index_path = page["path"]
        g.account = g._call("editAccountInfo", {"short_name": short, "author_name": acc["author_name"], "author_url": page_url(page["path"])})
        g.save_index()
        return g

    def load(self) -> "Glossary":
        self.account = self._call("getAccountInfo", {"fields": ["short_name", "author_name", "author_url", "page_count"]})
        self.index_path = path_from_url(self.account.get("author_url"))
        if not self.index_path:
            title = self.account.get("short_name") or "Glossary"
            page = self._call("createPage", {"title": title, "author_name": self.account.get("author_name"), "content": build_index([])})
            self.index_path = page["path"]
            self.account = self._call("editAccountInfo", {"author_url": page_url(page["path"])})
        self.refresh()
        return self

    def refresh(self) -> list[Entry]:
        page = self._call("getPage", {"path": self.index_path, "return_content": True}, auth=False)
        self.title = page["title"]
        self.terms = parse_index(page.get("content", []))
        return self.terms

    @property
    def index_url(self) -> str:
        return page_url(self.index_path or "")

    def _meta(self) -> dict[str, str]:
        return {"author_name": self.account.get("author_name") or self.title, "author_url": self.index_url}

    def save_index(self) -> None:
        self._call("editPage", {"path": self.index_path, "title": self.title, **self._meta(), "content": build_index(self.terms)})

    def _changed(self) -> None:
        from . import autolink  # channel posts are updated by the auto-link bot, if the site has one

        autolink.notify_changed(self.index_path)

    # -- terms ---------------------------------------------------------------
    def find(self, term: str) -> Optional[Entry]:
        k = term.strip().lower()
        for t in self.terms:
            if t.term.lower() == k or any(a.lower() == k for a in t.aliases):
                return t
        return None

    def get_definition(self, term_or_path: str) -> dict[str, Any]:
        entry = self.find(term_or_path)
        path = entry.path if entry else term_or_path
        page = self._call("getPage", {"path": path, "return_content": True}, auth=False)
        return {
            "term": page["title"],
            "url": page_url(path),
            "aliases": entry.aliases if entry else [],
            "definition": nodes_to_markdown(page.get("content", [])),
            "views": page.get("views", 0),
        }

    def save_term(self, term: str, definition: str, aliases: Optional[list[str]] = None, original: Optional[str] = None) -> Entry:
        """Add a term, or update one (pass ``original`` = its current name)."""
        term = re.sub(r"\s+", " ", term).strip()
        if not term:
            raise ValueError("empty term")
        if re.search(r"[,·]", term):
            raise ValueError("term cannot contain ',' or '·'")
        aliases = clean_aliases(aliases or [], term)
        self.refresh()  # read-modify-write
        existing = self.find(original) if original else None
        clash = self.find(term) or next((self.find(a) for a in aliases if self.find(a)), None)
        if clash and clash is not existing:
            raise ValueError(f'"{clash.term}" already exists')
        content = markdown_to_nodes(definition)
        if not content:
            raise ValueError("empty definition")
        planned = Entry(term, existing.path if existing else projected_path(term), aliases)
        check_index_fits([t for t in self.terms if t is not existing] + [planned])
        if existing:
            path = existing.path
            self._call("editPage", {"path": path, "title": term, **self._meta(), "content": content})
        else:
            path = self._call("createPage", {"title": term, **self._meta(), "content": content})["path"]
        entry = Entry(term, path, aliases)
        self.update_index(lambda terms: [t for t in terms if t.path != path] + [entry])
        self._changed()
        return entry

    def save_terms(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Add or update many terms with one index write. Each item: term, definition, aliases?.
        An existing term (by name or alias) is updated. Items that fail validation are reported and
        skipped; the rest are saved. A later item for the same term replaces an earlier one (last
        write wins), so each page is written once and listed once.

        Every item is validated and the resulting index is sized before any page is written: if it
        would not fit, GlossaryFullError is raised and nothing changes."""
        self.refresh()
        # name/alias (lowercase) -> its index entry, or the planned entry that replaces it
        taken: dict[str, Entry] = {k: t for t in self.terms for k in [t.term.lower(), *(a.lower() for a in t.aliases)]}
        results: list[dict[str, Any]] = []
        plans: list[dict[str, Any]] = []  # in item order; a replaced plan is removed
        for item in items:
            term = re.sub(r"\s+", " ", str(item.get("term") or "")).strip()
            try:
                if not term:
                    raise ValueError("empty term")
                if re.search(r"[,·]", term):
                    raise ValueError("term cannot contain ',' or '·'")
                content = markdown_to_nodes(str(item.get("definition") or ""))
                if not content:
                    raise ValueError("empty definition")
                existing = taken.get(term.lower())
                if existing and existing.term.lower() != term.lower():
                    raise ValueError(f'"{term}" is already an alias of "{existing.term}"')
                # omitted aliases keep the existing ones; [] clears them
                aliases = clean_aliases(item["aliases"] if item.get("aliases") is not None else (existing.aliases if existing else []), term)
                clash = next((taken[k.lower()] for k in aliases if k.lower() in taken and taken[k.lower()] is not existing), None)
                if clash:
                    raise ValueError(f'"{clash.term}" already uses one of these aliases')
            except ValueError as e:
                results.append({"term": term, "status": "error", "error": str(e)})
                continue
            prev = next((p for p in plans if p["entry"] is existing), None)
            if prev:
                plans.remove(prev)
            original = prev["original"] if prev else existing  # the index entry this updates, if any
            entry = Entry(term, original.path if original else "", aliases)  # a new page's path is set once it exists
            for k in [k for k, v in taken.items() if v is existing]:  # release the replaced entry's names
                del taken[k]
            for k in [term, *aliases]:
                taken[k.lower()] = entry
            plans.append({"entry": entry, "content": content, "original": original, "positions": (prev["positions"] if prev else []) + [len(results)]})
            results.append({})  # filled in once the page is written
        if not plans:
            return results
        replaced = {p["original"].path for p in plans if p["original"]}
        check_index_fits(
            [t for t in self.terms if t.path not in replaced]
            + [p["entry"] if p["original"] else Entry(p["entry"].term, projected_path(p["entry"].term), p["entry"].aliases) for p in plans]
        )
        saved: list[Entry] = []
        for p in plans:
            entry = p["entry"]
            try:
                if p["original"]:
                    self._call("editPage", {"path": entry.path, "title": entry.term, **self._meta(), "content": p["content"]})
                else:
                    entry.path = self._call("createPage", {"title": entry.term, **self._meta(), "content": p["content"]})["path"]
                saved.append(entry)
                result = {"term": entry.term, "status": "updated" if p["original"] else "added", "url": entry.url}
            except TelegraphError as e:
                result = {"term": entry.term, "status": "error", "error": str(e)}
            *earlier, last = p["positions"]
            results[last] = result
            for pos in earlier:
                results[pos] = {**result, "note": "replaced by a later item for the same term"}
        if saved:
            paths = {e.path for e in saved}
            self.update_index(lambda terms: [t for t in terms if t.path not in paths] + saved)
            self._changed()
        return results

    def rename(self, title: str) -> None:
        title = title.strip()
        if not title:
            raise ValueError("empty title")
        self.refresh()  # don't write back a stale term list
        self.title = title
        self.save_index()

    def auth_url(self) -> str:
        """One-time link that signs a browser in to telegra.ph as this glossary's account."""
        return self._call("getAccountInfo", {"fields": ["auth_url"]})["auth_url"]

    def export(self) -> list[dict[str, Any]]:
        """All terms with their definitions (Markdown)."""
        self.refresh()
        out = []
        for t in self.terms:
            page = self._call("getPage", {"path": t.path, "return_content": True}, auth=False)
            out.append({"term": t.term, "aliases": t.aliases, "url": t.url, "definition": nodes_to_markdown(page.get("content", []))})
        return out

    def update_index(self, apply, attempts: int = 4) -> None:
        """Change the index while others may edit it too (web app, another agent).

        Telegraph has no compare-and-swap: two writers that read the same index both write, and
        the later write drops the earlier change. So write, wait for writes already in flight to
        land, re-read, and re-apply the change on top if it was dropped. `apply` must be
        idempotent (replace by path, filter by path), so re-applying never duplicates. A write that
        lands later than settle_s can still drop a change: this narrows the window, it can't close it."""

        def sig(terms: list[Entry]) -> list:
            return sorted([t.path, t.term, t.aliases] for t in terms)

        def missing() -> bool:
            return sig(apply(list(self.terms))) != sig(self.terms)

        self.refresh()
        for _ in range(attempts):
            if not missing():
                return
            self.terms = apply(list(self.terms))
            self.save_index()
            time.sleep(self.settle_s)
            self.refresh()
        if missing():
            raise RuntimeError("The glossary is being edited somewhere else right now. Try again.")

    def remove_term(self, term: str) -> bool:
        self.refresh()
        entry = self.find(term)
        if not entry:
            return False
        # Telegraph pages cannot be deleted: drop it from the index, then blank the page. Index
        # first, so a failed index write (network, concurrent edit) leaves the term intact. If the
        # blanking fails after that, an unlisted page with the old definition is left: harmless,
        # since the index no longer lists or links it.
        self.update_index(lambda terms: [t for t in terms if t.path != entry.path])
        self._call("editPage", {"path": entry.path, "title": entry.term, **self._meta(), "content": [{"tag": "p", "children": ["—"]}]})
        self._changed()
        return True
