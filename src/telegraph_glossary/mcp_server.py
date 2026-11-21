"""MCP server: lets any AI agent (Claude Code, Codex, Gemini/Antigravity, Cursor...) use the glossary."""

from __future__ import annotations

import functools
from typing import Optional

from . import config
from .glossary import APP_URL, Glossary
from .linker import link_text as _link
from .telegram import MAX_LEN, discover_chats, send_html

try:  # mcp >= 2
    from mcp.server.mcpserver import MCPServer as _Server
    from mcp.server.mcpserver.exceptions import ToolError
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP as _Server  # type: ignore[no-redef]
    from mcp.server.fastmcp.exceptions import ToolError  # type: ignore[no-redef]

INSTRUCTIONS = """\
Telegraph Glossary: a personal glossary whose terms are Telegraph pages, used to
add explanatory links to Telegram posts.

Typical flow when the user hands you a post:
1. call link_text(text) - it finds glossary terms and returns Telegram HTML with links.
2. look at the post for jargon that is NOT in the glossary; offer to add it with
   add_term (short, clear definition in the post's language; Markdown allowed).
3. when the user approves, call send_to_telegram(text) or give them the HTML.
Never invent glossary URLs - only use URLs returned by these tools.
"""

mcp = _Server("telegraph-glossary", instructions=INSTRUCTIONS)


def tool(fn):
    """Register a tool; surface our error messages to the agent instead of a generic failure."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except ToolError:
            raise
        except Exception as e:  # noqa: BLE001
            raise ToolError(str(e)) from e

    return mcp.tool()(wrapper)

_glossary: Optional[Glossary] = None


def _g() -> Glossary:
    global _glossary
    token = config.get("telegraph_token")
    if not token:
        raise RuntimeError(
            "No glossary key. Set TELEGRAPH_ACCESS_TOKEN (copy it from the web app's Settings), "
            "or run `telegraph-glossary init` to create a new glossary."
        )
    if _glossary is None or _glossary.token != token:
        _glossary = Glossary(token).load()
    else:
        _glossary.refresh()
    return _glossary


def _entries(g: Glossary) -> list[dict]:
    return [t.to_dict() for t in g.terms]


@tool
def glossary_info() -> dict:
    """Glossary title, public index page, number of terms and whether Telegram sending is configured."""
    g = _g()
    return {
        "title": g.title,
        "index_url": g.index_url,
        "term_count": len(g.terms),
        "telegram_configured": bool(config.get("bot_token")),
        "default_chat": config.get("chat_id"),
        "web_app": APP_URL,
    }


@tool
def list_terms(query: str = "") -> list[dict]:
    """List glossary terms (term, aliases, url). Optional case-insensitive filter on term/aliases."""
    q = query.strip().lower()
    return [t for t in _entries(_g()) if not q or q in t["term"].lower() or any(q in a.lower() for a in t["aliases"])]


@tool
def get_term(term: str) -> dict:
    """Get a term's full definition (Markdown), aliases, url and view count. Accepts the term or any alias."""
    g = _g()
    if not g.find(term):
        raise ValueError(f'"{term}" is not in the glossary')
    return g.get_definition(term)


@tool
def add_term(term: str, definition: str, aliases: Optional[list[str]] = None) -> dict:
    """Add a term. `definition` is Markdown (**bold**, *italic*, [link](url), lists, ## headings).
    `aliases` are other spellings/forms that should also be linked (e.g. plural, English name)."""
    return _g().save_term(term, definition, aliases or []).to_dict()


@tool
def update_term(
    term: str,
    definition: Optional[str] = None,
    new_name: Optional[str] = None,
    aliases: Optional[list[str]] = None,
) -> dict:
    """Update an existing term. Omitted fields are kept as they are."""
    g = _g()
    entry = g.find(term)
    if not entry:
        raise ValueError(f'"{term}" is not in the glossary')
    if definition is None:
        definition = g.get_definition(entry.path)["definition"]
    return g.save_term(new_name or entry.term, definition, entry.aliases if aliases is None else aliases, original=entry.term).to_dict()


@tool
def remove_term(term: str) -> dict:
    """Remove a term from the glossary (its page is blanked; Telegraph cannot delete pages)."""
    return {"removed": _g().remove_term(term)}


@tool
def link_text(text: str, mode: str = "first", exclude: Optional[list[str]] = None) -> dict:
    """Find glossary terms in `text` and return it with links.
    mode: "first" links only the first occurrence of each term (recommended), "all" links every occurrence.
    exclude: terms not to link. Returns telegram_html (for Telegram parse_mode=HTML), markdown and found terms."""
    r = _link(text, [t.to_dict() for t in _g().terms], mode=mode, exclude=exclude or [])
    return {"telegram_html": r.html, "markdown": r.markdown, "found": r.found}


@tool
def send_to_telegram(
    text: str,
    chat_id: Optional[str] = None,
    mode: str = "first",
    exclude: Optional[list[str]] = None,
    dry_run: bool = False,
) -> dict:
    """Link glossary terms in `text` and send it via the user's Telegram bot.
    chat_id: "@channel", a numeric id, or omitted to use TELEGRAM_CHAT_ID. Use dry_run to preview.
    Always show the user the text and get approval before sending for real."""
    r = _link(text, [t.to_dict() for t in _g().terms], mode=mode, exclude=exclude or [])
    token, chat = config.get("bot_token"), chat_id or config.get("chat_id")
    if len(text) > MAX_LEN:
        raise ValueError(f"Telegram messages are limited to {MAX_LEN} characters (this one has {len(text)})")
    if dry_run:
        return {"would_send_to": chat, "telegram_html": r.html, "found": r.found}
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set (create a bot with @BotFather and add it as admin to your channel)")
    if not chat:
        chats = discover_chats(token)
        raise RuntimeError(f"No chat_id given and TELEGRAM_CHAT_ID is not set. Chats the bot has seen: {chats}")
    msg = send_html(token, chat, r.html)
    return {"sent": True, "chat": chat, "message_id": msg.get("message_id"), "found": r.found}


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
