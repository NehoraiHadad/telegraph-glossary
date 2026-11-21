from telegraph_glossary.glossary import Entry, build_index, parse_index, path_from_url
from telegraph_glossary.markdown import markdown_to_nodes, nodes_to_markdown

MD = """## Title

**Bold** and *italic* with [a link](https://example.com) and `code`.
second line

- one
- two

1. first
2. second

> quoted

```
x = 1
```

![caption](https://example.com/a.png)

---"""


def test_markdown_roundtrip():
    assert nodes_to_markdown(markdown_to_nodes(MD)) == MD


def test_line_break_becomes_br():
    nodes = markdown_to_nodes("a\nb")
    assert nodes == [{"tag": "p", "children": ["a", {"tag": "br"}, "b"]}]


def test_index_roundtrip():
    terms = [Entry("פייתון", "פייתון-11-21", ["Python"]), Entry("API", "API-11-21", [])]
    parsed = parse_index(build_index(terms))
    assert [(t.term, t.path, t.aliases) for t in parsed] == [("API", "API-11-21", []), ("פייתון", "פייתון-11-21", ["Python"])]


def test_relative_and_encoded_paths():
    assert path_from_url("/%D7%A4%D7%99-11-21") == "פי-11-21"
    assert path_from_url("https://telegra.ph/API-11-21") == "API-11-21"
    assert path_from_url("https://example.com/x") is None
