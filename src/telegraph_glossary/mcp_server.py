"""MCP server: lets any AI agent (Claude Code, Codex, Gemini/Antigravity, Cursor...) use the glossary."""

from __future__ import annotations

import functools
import logging
from typing import Optional

from . import config
from .glossary import APP_URL, Glossary
from .linker import link_text as _link
from . import autolink
from .telegram import MAX_LEN, discover_chats, send_html

try:  # mcp >= 2
    from mcp.server.mcpserver import MCPServer as _Server
    from mcp.server.mcpserver.exceptions import ToolError
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP as _Server  # type: ignore[no-redef]
    from mcp.server.fastmcp.exceptions import ToolError  # type: ignore[no-redef]

INSTRUCTIONS = """\
Telegraph Glossary: the user's glossary. Each term is a short explanation page on
Telegraph, and terms in the user's Telegram posts become links to those pages.

How the user publishes (check with glossary_info):
- channel_connected=true: a bot adds the links to every channel post automatically,
  and updates older posts when terms change. Your job is mostly the glossary itself.
- otherwise: use link_text to produce the linked post, or send_to_telegram if a bot
  token is configured, or help them connect a channel with connect_channel.

Good habits:
- When the user shares a post, call link_text, then point out jargon that is NOT in the
  glossary and offer to add it.
- Definitions: 1-3 plain sentences in the post's language. Markdown is allowed.
  Add aliases for other forms readers will write (plural, English/Hebrew name, acronym).
- Many terms at once (importing a list, filling gaps from a post): use add_terms.
- Ask before removing terms or sending messages. Never invent glossary URLs.
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
    channels = []
    if autolink.available():
        try:
            channels = autolink.status(g.index_path)
        except RuntimeError:
            pass
    return {
        "title": g.title,
        "index_url": g.index_url,
        "term_count": len(g.terms),
        "channel_connected": bool(channels),
        "channels": [c["title"] for c in channels],
        "auto_link_available": autolink.available(),
        "own_bot_configured": bool(config.get("bot_token")),
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
def add_terms(terms: list[dict]) -> list[dict]:
    """Add or update many terms in one call (much faster than add_term in a loop).
    Each item: {"term": str, "definition": str (Markdown), "aliases": [str] (optional)}.
    An item whose term already exists updates it (omit "aliases" to keep its current ones). Returns a status per item: added, updated or error."""
    return _g().save_terms(terms)


@tool
def rename_glossary(title: str) -> dict:
    """Rename the glossary (the title of its public index page)."""
    g = _g()
    g.rename(title)
    return {"title": g.title, "index_url": g.index_url}


@tool
def export_glossary(format: str = "markdown") -> dict | list[dict]:
    """Every term with its full definition, for backup or review.
    format: "markdown" (one document) or "json" (a list of {term, aliases, url, definition})."""
    g = _g()
    items = g.export()
    if format == "json":
        return items
    if format != "markdown":
        raise ValueError('format must be "markdown" or "json"')
    parts = [f"# {g.title}", ""]
    for t in items:
        parts += [f"## {t['term']}", *([f"*Also: {', '.join(t['aliases'])}*"] if t["aliases"] else []), "", t["definition"], f"<{t['url']}>", ""]
    return {"markdown": "\n".join(parts), "term_count": len(items)}


@tool
def edit_on_telegraph() -> dict:
    """A one-time link that signs the user's browser in to telegra.ph as the glossary's account,
    so they can edit pages there directly. The link expires within minutes. Give it only to the user."""
    return {"url": _g().auth_url(), "note": "One-time sign-in link for telegra.ph. It expires within minutes; don't share it."}


@tool
def relink_channel() -> dict:
    """Make the auto-link bot re-apply the glossary to the remembered posts of every connected channel
    now, instead of on its next 15-minute run. Adding, updating or removing terms already does this."""
    g = _g()
    channels = autolink.status(g.index_path)
    if not channels:
        raise RuntimeError("No channel is connected to this glossary. Use connect_channel first.")
    autolink.relink(g.index_path)
    return {"started": True, "channels": [c["title"] for c in channels]}


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


@tool
def connect_channel() -> dict:
    """Get a link that connects one of the user's Telegram channels to this glossary.
    After that, the bot adds the links to every post automatically. Give the user the link
    and the steps; you cannot do the Telegram part for them."""
    g = _g()
    r = autolink.connect(g.index_path)
    return {
        "link": r["start_url"],
        "steps": [
            "Open the link and press Start in Telegram.",
            "Press 'Add to channel' in the bot's reply and pick the channel (keep the 'Edit messages' right).",
            "Done. Check with channel_status. Older posts can be forwarded to the bot to get links.",
        ],
        "bot": "@" + r["bot_username"],
    }


@tool
def channel_status() -> dict:
    """Channels where the bot adds glossary links automatically."""
    g = _g()
    if not autolink.available():
        return {"available": False, "channels": []}
    return {"available": True, "bot": "@" + autolink.info()["bot_username"], "channels": autolink.status(g.index_path)}


@mcp.prompt()
def link_post(post: str) -> str:
    """Link glossary terms in a post and suggest missing ones."""
    return (
        "Here is a Telegram post. Call link_text on it and show me which terms got links. "
        "Then list jargon in it that is missing from my glossary, each with a suggested 1-2 sentence "
        "definition in the post's language, and ask which ones to add.\n\n" + post
    )


def main() -> None:
    logging.getLogger("httpx").setLevel(logging.WARNING)  # keep agent logs readable
    mcp.run()


if __name__ == "__main__":
    main()
