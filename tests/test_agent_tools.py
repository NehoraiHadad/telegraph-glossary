"""Bulk add, rename and export (the agent's "do everything" tools) against an in-memory Telegraph."""

import json

import pytest

from telegraph_glossary import mcp_server
from telegraph_glossary.glossary import Entry, Glossary, TelegraphError, build_index

LIMIT = 64 * 1024  # Telegraph's page content limit, measured as the JSON sent, in UTF-8 bytes


def sent_bytes(nodes):
    return len(json.dumps(nodes, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


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
        self.fail_index_write = False
        self.fail_page = None  # path whose editPage fails (on_fail runs then)
        self.on_fail = None
        self.lost_page = None  # path whose editPage is applied, but the answer is an error

    def _call(self, method, params=None, auth=True):
        p = params or {}
        if method == "getPage":
            return self.pages[p["path"]]
        if method in ("createPage", "editPage") and sent_bytes(p["content"]) > LIMIT:
            raise TelegraphError("CONTENT_TOO_BIG")
        if method == "editPage" and p["path"] == self.fail_page:
            if self.on_fail:
                self.on_fail()
            raise TelegraphError("network down")
        if method == "editPage" and p["path"] == "Idx" and self.fail_index_write:
            raise TelegraphError("index write failed")
        if method == "editPage" and p["path"] == self.lost_page:
            self.pages[p["path"]] = {"title": p["title"], "content": p["content"]}
            raise TelegraphError("network down")
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


def test_remove_term_keeps_the_definition_when_the_index_write_fails():
    g = MemTelegraph([Entry("API", "API-1")])
    g.fail_index_write = True
    with pytest.raises(TelegraphError):
        g.remove_term("API")
    assert g.pages["API-1"]["content"] == [{"tag": "p", "children": ["about API"]}]
    g.fail_index_write = False
    assert g.remove_term("API")
    assert g.refresh() == [] and g.pages["API-1"]["content"] == [{"tag": "p", "children": ["—"]}]


def full_glossary():
    """Terms whose index is just under the limit, so one more term does not fit."""
    terms = []
    while True:
        more = terms + [Entry(f"Term {len(terms):04d}", f"Term-{len(terms):04d}-11-22", ["x" * 40])]
        if sent_bytes(build_index(more)) > LIMIT:
            return MemTelegraph(terms)
        terms = more


def test_adding_to_a_full_glossary_fails_before_any_page_is_written():
    g = full_glossary()
    pages = {k: dict(v) for k, v in g.pages.items()}
    with pytest.raises(ValueError, match="The glossary is full"):
        g.save_term("A new term with a long enough name", "def")
    with pytest.raises(ValueError, match="The glossary is full"):
        g.save_terms([
            {"term": "Term 0000", "definition": "changed"},  # an update that alone would fit
            {"term": "A new term with a long enough name", "definition": "def"},
        ])
    assert g.pages == pages and g.index_writes == 0


def test_same_term_twice_in_one_call_is_listed_once_last_wins():
    g = MemTelegraph([Entry("API", "API-1", ["APIs"])])
    r = g.save_terms([
        {"term": "Docker", "definition": "one", "aliases": ["dk"]},
        {"term": "docker", "definition": "two", "aliases": ["container"]},
        {"term": "API", "definition": "first"},
        {"term": "API", "definition": "second", "aliases": ["interface"]},
        {"term": "dk", "definition": "x"},  # the replaced item's alias is free again
    ])
    assert [x["status"] for x in r] == ["added", "added", "updated", "updated", "added"]
    terms = g.refresh()
    assert sorted((t.term, t.aliases) for t in terms) == [("API", ["interface"]), ("dk", []), ("docker", ["container"])]
    docker = next(t for t in terms if t.term == "docker")
    assert g.pages[docker.path]["content"] == [{"tag": "p", "children": ["two"]}]
    assert g.pages["API-1"]["content"] == [{"tag": "p", "children": ["second"]}]
    assert len(g.pages) == 4  # index, API, one Docker page, dk


def test_remove_term_relists_the_term_when_blanking_fails():
    g = MemTelegraph([Entry("API", "API-1")])
    g.fail_page = "API-1"
    with pytest.raises(TelegraphError):
        g.remove_term("API")
    assert [t.term for t in g.refresh()] == ["API"]  # still listed, so the removal can be retried
    g.fail_page = None
    assert g.remove_term("API") and g.refresh() == []


def test_remove_term_does_not_relist_a_page_blanked_although_the_answer_was_lost():
    g = MemTelegraph([Entry("API", "API-1")])
    g.lost_page = "API-1"
    assert g.remove_term("API")
    assert g.refresh() == [] and g.pages["API-1"]["content"] == [{"tag": "p", "children": ["—"]}]
    assert g.changed == 1


def test_remove_term_failed_relist_keeps_the_cause_and_names_the_unlisted_page():
    g = MemTelegraph([Entry("API", "API-1")])
    g.fail_page = "API-1"
    g.on_fail = lambda: setattr(g, "fail_index_write", True)
    with pytest.raises(TelegraphError) as e:
        g.remove_term("API")
    msg = str(e.value)
    assert '"API"' in msg and "https://telegra.ph/API-1" in msg and "no longer listed" in msg
    assert "network down" in msg and "index write failed" in msg
    assert isinstance(e.value.__cause__, TelegraphError) and str(e.value.__cause__) == "network down"
    assert g.pages["API-1"]["content"] == [{"tag": "p", "children": ["about API"]}]


def test_save_terms_does_not_list_an_item_whose_name_a_failed_update_still_uses():
    g = MemTelegraph([Entry("API", "API-1", ["REST"])])
    g.fail_page = "API-1"  # the update that frees "REST" fails
    r = g.save_terms([
        {"term": "API", "definition": "x", "aliases": []},
        {"term": "REST", "definition": "y"},
    ])
    assert [x["status"] for x in r] == ["error", "error"]
    terms = g.refresh()
    assert [(t.term, t.aliases) for t in terms] == [("API", ["REST"])]
