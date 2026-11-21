"""Minimal Markdown <-> Telegraph node conversion (mirrors web/core/markdown.js)."""

from __future__ import annotations

import re
from typing import Any, Union

Node = Union[str, dict]

INLINE = re.compile(
    r"`([^`]+)`"
    r"|!\[([^\]]*)\]\(([^)\s]+)\)"
    r"|\[([^\]]+)\]\(([^)\s]+)\)"
    r"|\*\*(.+?)\*\*"
    r"|~~(.+?)~~"
    r"|\*([^*\s][^*]*?)\*"
    r"|(?<![^\W_])_([^_\s][^_]*?)_(?![^\W_])"
)
LIST_ITEM = re.compile(r"^([-*+]|\d+[.)])\s+")


def inline_to_nodes(text: str) -> list[Node]:
    out: list[Node] = []
    pos = 0
    for m in INLINE.finditer(text):
        if m.start() > pos:
            out.append(text[pos : m.start()])
        code, img_alt, img_src, link_text, href, bold, strike, em1, em2 = m.groups()
        if code is not None:
            out.append({"tag": "code", "children": [code]})
        elif img_src is not None:
            attrs = {"src": img_src}
            if img_alt:
                attrs["alt"] = img_alt
            out.append({"tag": "img", "attrs": attrs})
        elif href is not None:
            out.append({"tag": "a", "attrs": {"href": href}, "children": inline_to_nodes(link_text)})
        elif bold is not None:
            out.append({"tag": "strong", "children": inline_to_nodes(bold)})
        elif strike is not None:
            out.append({"tag": "s", "children": inline_to_nodes(strike)})
        else:
            out.append({"tag": "em", "children": inline_to_nodes(em1 if em1 is not None else em2)})
        pos = m.end()
    if pos < len(text):
        out.append(text[pos:])
    return out


def _join_lines(lines: list[str]) -> list[Node]:
    children: list[Node] = []
    for i, line in enumerate(lines):
        if i:
            children.append({"tag": "br"})
        children.extend(inline_to_nodes(line))
    return children


def markdown_to_nodes(md: str) -> list[Node]:
    lines = (md or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    nodes: list[Node] = []
    para: list[str] = []

    def flush() -> None:
        if para:
            nodes.append({"tag": "p", "children": _join_lines(para)})
            para.clear()

    i = 0
    while i < len(lines):
        t = lines[i].strip()
        if t.startswith("```"):
            flush()
            code = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code.append(lines[i])
                i += 1
            nodes.append({"tag": "pre", "children": ["\n".join(code)]})
        elif not t:
            flush()
        elif m := re.match(r"^(#{1,6})\s+(.*)$", t):
            flush()
            nodes.append({"tag": "h3" if len(m.group(1)) <= 2 else "h4", "children": inline_to_nodes(m.group(2))})
        elif re.match(r"^(-{3,}|\*{3,})$", t):
            flush()
            nodes.append({"tag": "hr"})
        elif m := re.match(r"^!\[([^\]]*)\]\(([^)\s]+)\)$", t):
            flush()
            fig: list[Node] = [{"tag": "img", "attrs": {"src": m.group(2)}}]
            if m.group(1):
                fig.append({"tag": "figcaption", "children": [m.group(1)]})
            nodes.append({"tag": "figure", "children": fig})
        elif t.startswith(">"):
            flush()
            q = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                q.append(re.sub(r"^>\s?", "", lines[i].strip()))
                i += 1
            i -= 1
            nodes.append({"tag": "blockquote", "children": _join_lines(q)})
        elif LIST_ITEM.match(t):
            flush()
            ordered = t[0].isdigit()
            items: list[Node] = []
            while i < len(lines) and LIST_ITEM.match(lines[i].strip()) and lines[i].strip()[0].isdigit() == ordered:
                items.append({"tag": "li", "children": inline_to_nodes(LIST_ITEM.sub("", lines[i].strip()))})
                i += 1
            i -= 1
            nodes.append({"tag": "ol" if ordered else "ul", "children": items})
        else:
            para.append(t)
        i += 1
    flush()
    return nodes


def _inline_to_md(nodes: list[Any]) -> str:
    out = []
    for n in nodes or []:
        if isinstance(n, str):
            out.append(n)
            continue
        inner = _inline_to_md(n.get("children", []))
        tag, attrs = n.get("tag"), n.get("attrs") or {}
        if tag in ("b", "strong"):
            out.append(f"**{inner}**")
        elif tag in ("i", "em"):
            out.append(f"*{inner}*")
        elif tag == "s":
            out.append(f"~~{inner}~~")
        elif tag == "code":
            out.append(f"`{inner}`")
        elif tag == "a":
            out.append(f"[{inner}]({attrs.get('href', '')})")
        elif tag == "br":
            out.append("\n")
        elif tag == "img":
            out.append(f"![{attrs.get('alt', '')}]({attrs.get('src', '')})")
        else:
            out.append(inner)
    return "".join(out)


def nodes_to_markdown(nodes: list[Any]) -> str:
    blocks: list[str] = []
    for n in nodes or []:
        if isinstance(n, str):
            if n.strip():
                blocks.append(n.strip())
            continue
        tag, kids = n.get("tag"), n.get("children", [])
        if tag == "h3":
            blocks.append(f"## {_inline_to_md(kids)}")
        elif tag == "h4":
            blocks.append(f"### {_inline_to_md(kids)}")
        elif tag == "hr":
            blocks.append("---")
        elif tag == "pre":
            blocks.append("```\n" + _inline_to_md(kids) + "\n```")
        elif tag in ("blockquote", "aside"):
            blocks.append("\n".join(f"> {line}" for line in _inline_to_md(kids).split("\n")))
        elif tag in ("ul", "ol"):
            items = [k for k in kids if not isinstance(k, str)]
            blocks.append(
                "\n".join(
                    f"{f'{i + 1}.' if tag == 'ol' else '-'} {_inline_to_md(li.get('children', []))}"
                    for i, li in enumerate(items)
                )
            )
        elif tag == "figure":
            img = next((k for k in kids if isinstance(k, dict) and k.get("tag") == "img"), None)
            cap = next((k for k in kids if isinstance(k, dict) and k.get("tag") == "figcaption"), None)
            if img:
                alt = _inline_to_md(cap.get("children", [])) if cap else ""
                blocks.append(f"![{alt}]({(img.get('attrs') or {}).get('src', '')})")
        elif tag == "img":
            blocks.append(_inline_to_md([n]))
        else:
            s = _inline_to_md(kids).strip()
            if s:
                blocks.append(s)
    return "\n\n".join(blocks)
