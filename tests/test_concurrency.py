"""update_index must not drop a term someone else added between our read and our write."""

from telegraph_glossary.glossary import Entry, Glossary, build_index


class FakeTelegraph(Glossary):
    def __init__(self):
        super().__init__("tok")
        self.index_path = "Idx"
        self.account = {"author_name": "a"}
        self.page = build_index([Entry("A", "A-1")])
        self.writes = 0
        self.interfere_once = True

    def _call(self, method, params=None, auth=True):
        if method == "getPage":
            return {"title": "G", "content": self.page}
        if method == "editPage" and params["path"] == "Idx":
            self.writes += 1
            self.page = params["content"]
            return {}
        raise AssertionError(method)

    def refresh(self):
        super().refresh()
        if self.interfere_once:  # another writer adds "B" right after our read
            self.interfere_once = False
            self.page = build_index([Entry("A", "A-1"), Entry("B", "B-1")])
        return self.terms


def test_concurrent_add_is_kept():
    g = FakeTelegraph()
    g.update_index(lambda terms: terms + [Entry("C", "C-1")])
    names = sorted(t.term for t in g.refresh())
    assert names == ["A", "B", "C"]
    assert g.writes == 1
