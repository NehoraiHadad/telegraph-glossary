"""update_index must not lose a term when several writers edit the index at once."""

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


def test_change_already_in_place_does_not_write():
    g = FakeTelegraph()
    g.interfere_once = False
    g.update_index(lambda terms: [t for t in terms if t.path != "A-1"] + [Entry("A", "A-1")])
    assert g.writes == 0


class LostUpdateTelegraph(FakeTelegraph):
    """Another writer read the index before our write and saves its stale copy right after it."""

    def __init__(self):
        super().__init__()
        self.interfere_once = False
        self.stale_write_pending = True
        self.settle_s = 0

    def _call(self, method, params=None, auth=True):
        out = super()._call(method, params, auth)
        if method == "editPage" and self.stale_write_pending:
            self.stale_write_pending = False
            self.page = build_index([Entry("A", "A-1"), Entry("B", "B-1")])  # drops our "C"
        return out


def test_term_dropped_by_a_stale_concurrent_write_is_restored():
    g = LostUpdateTelegraph()
    g.update_index(lambda terms: [t for t in terms if t.path != "C-1"] + [Entry("C", "C-1")])
    names = sorted(t.term for t in g.refresh())
    assert names == ["A", "B", "C"]
