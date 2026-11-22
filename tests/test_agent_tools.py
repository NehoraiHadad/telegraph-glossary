"""Bulk add, rename and export (the agent's "do everything" tools) against an in-memory Telegraph."""

import pytest

from telegraph_glossary import mcp_server
from telegraph_glossary.glossary import Entry, Glossary, build_index


class MemTelegraph(Glossary):
    def __init__(self, terms=()):
        super().__init__("tok")
        self.settle_s = 0
        self.index_path = "Idx"
        self.account = {"author_name": "a"}
        self.pages = {"Idx": {"title": "G", "content": build_index(list(terms))}}
        for t in terms:
            self.pages[t.path] = {"title": t.term, "content": [{"tag": "p", "children": [f"about {t.term}"]}]}
        self.index_writes = 0
        self.changed = 0

    def _call(self, method, params=None, auth=True):
        p = params or {}
        if method == "getPage":
            return self.pages[p["path"]]
        if method == "createPage":
            path = f"{p['title']}-{len(self.pages)}"
            self.pages[path] = {"title": p["title"], "content": p["content"]}
            return {"path": path}
        if method == "editPage":
            self.index_writes += p["path"] == "Idx"
            self.pages[p["path"]] = {"title": p["title"], "content": p["content"]}
            return {}
        if method == "getAccountInfo":
            return {"auth_url": "https://edit.telegra.ph/auth/x"}
        raise AssertionError(method)

    def _changed(self):
        self.changed += 1


def test_save_terms_adds_updates_and_reports_errors_with_one_index_write():
    g = MemTelegraph([Entry("API", "API-1", ["APIs"])])
    r = g.save_terms([
        {"term": "Docker", "definition": "Containers.", "aliases": ["docker image"]},
        {"term": "API", "definition": "**Updated**", "aliases": ["APIs"]},
        {"term": "Thing", "definition": "x", "aliases": ["APIs"]},  # alias belongs to API
        {"term": "APIs", "definition": "x"},  # already an alias
        {"term": "Empty", "definition": " "},
        {"term": "a,b", "definition": "x"},
    ])
    assert [x["status"] for x in r] == ["added", "updated", "error", "error", "error", "error"]
    assert g.index_writes == 1 and g.changed == 1
    names = {t.term: t for t in g.refresh()}
    assert set(names) == {"API", "Docker"}
    assert names["Docker"].aliases == ["docker image"]
    assert g.pages["API-1"]["content"][0]["children"][0]["tag"] == "strong"


def test_save_terms_update_keeps_aliases_unless_given():
    g = MemTelegraph([Entry("API", "API-1", ["APIs"])])
    g.save_terms([{"term": "API", "definition": "new"}])
    assert g.refresh()[0].aliases == ["APIs"]
    g.save_terms([{"term": "API", "definition": "new", "aliases": []}])
    assert g.refresh()[0].aliases == []


def test_save_terms_with_nothing_valid_writes_nothing():
    g = MemTelegraph([Entry("API", "API-1")])
    assert g.save_terms([{"term": "", "definition": "x"}])[0]["status"] == "error"
    assert g.index_writes == 0 and g.changed == 0


def test_rename_keeps_terms_added_elsewhere():
    g = MemTelegraph([Entry("API", "API-1")])
    g.refresh()
    g.pages["Idx"]["content"] = build_index([Entry("API", "API-1"), Entry("Docker", "Docker-9")])  # another writer
    g.rename("New name")
    g.refresh()
    assert g.title == "New name" and {t.term for t in g.terms} == {"API", "Docker"}
    with pytest.raises(ValueError):
        g.rename("  ")


def test_export_and_markdown_tool(monkeypatch):
    g = MemTelegraph([Entry("API", "API-1", ["APIs"]), Entry("Docker", "Docker-2")])
    items = g.export()
    assert [(i["term"], i["definition"].strip()) for i in items] == [("API", "about API"), ("Docker", "about Docker")]
    monkeypatch.setattr(mcp_server, "_g", lambda: g)
    md = mcp_server.export_glossary()
    assert md["term_count"] == 2 and md["markdown"].startswith("# G\n") and "*Also: APIs*" in md["markdown"]
    assert mcp_server.export_glossary("json") == items
    assert mcp_server.edit_on_telegraph()["url"].startswith("https://edit.telegra.ph/auth/")
