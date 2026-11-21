"""Glossary storage on Telegraph (format: docs/FORMAT.md; mirrors web/core/glossary.js)."""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Optional
from urllib.parse import quote, unquote

import httpx

from .markdown import markdown_to_nodes, nodes_to_markdown

API = "https://api.telegra.ph"
APP_URL = "https://nehoraihadad.github.io/telegraph-glossary/"
ALIAS_SEP = " · "
# Channel auto-link bot (bot/). When set, edits notify it so channel posts update right away
# (otherwise the bot picks changes up on its 15-minute schedule).
BOT_API = os.environ.get("TELEGRAPH_GLOSSARY_BOT_API", "")


class TelegraphError(Exception):
    pass


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

    # -- low level -----------------------------------------------------------
    def _call(self, method: str, params: Optional[dict] = None, auth: bool = True) -> Any:
        data = {}
        for k, v in {**({"access_token": self.token} if auth else {}), **(params or {})}.items():
            if v is not None:
                data[k] = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
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
        if BOT_API:
            try:
                self.http.post(f"{BOT_API.rstrip('/')}/api/changed", json={"index_path": self.index_path}, timeout=5)
            except httpx.HTTPError:
                pass

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
        if existing:
            self._call("editPage", {"path": existing.path, "title": term, **self._meta(), "content": content})
            existing.term, existing.aliases = term, aliases
            entry = existing
        else:
            page = self._call("createPage", {"title": term, **self._meta(), "content": content})
            entry = Entry(term, page["path"], aliases)
            self.terms.append(entry)
        self.save_index()
        return entry

    def remove_term(self, term: str) -> bool:
        self.refresh()
        entry = self.find(term)
        if not entry:
            return False
        # Telegraph pages cannot be deleted: blank the page and drop it from the index.
        self._call("editPage", {"path": entry.path, "title": entry.term, **self._meta(), "content": [{"tag": "p", "children": ["—"]}]})
        self.terms = [t for t in self.terms if t is not entry]
        self.save_index()
        return True
