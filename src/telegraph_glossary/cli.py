"""Command line interface: `telegraph-glossary` (short alias: `tgg`)."""

from __future__ import annotations

import argparse
import json
import sys

from . import config
from .glossary import APP_URL, Glossary
from .linker import link_text
from .telegram import discover_chats, send_html


def _read(arg: str | None) -> str:
    if arg in (None, "-"):
        return sys.stdin.read()
    with open(arg, encoding="utf-8") as f:
        return f.read()


def _glossary() -> Glossary:
    token = config.get("telegraph_token")
    if not token:
        sys.exit("No glossary key. Run `telegraph-glossary init` or `telegraph-glossary login <key>`.")
    return Glossary(token).load()


def _aliases(s: str | None) -> list[str] | None:
    return None if s is None else [a.strip() for a in s.split(",") if a.strip()]


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="telegraph-glossary", description="Glossary on Telegraph + auto-linked Telegram posts")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("init", help="create a new glossary and save its key")
    s.add_argument("--title", default="Glossary")
    s.add_argument("--author", default="")

    s = sub.add_parser("login", help="use an existing glossary key (from the web app's Settings)")
    s.add_argument("key")

    s = sub.add_parser("telegram", help="save Telegram bot token / default chat")
    s.add_argument("--bot-token")
    s.add_argument("--chat")

    sub.add_parser("chats", help="list chats your bot has seen (to find a chat id)")
    sub.add_parser("info", help="show glossary info")

    s = sub.add_parser("list", help="list terms")
    s.add_argument("--json", action="store_true")

    s = sub.add_parser("show", help="show a term's definition")
    s.add_argument("term")

    s = sub.add_parser("add", help="add a term (definition from -d, a file, or stdin)")
    s.add_argument("term")
    s.add_argument("-d", "--definition")
    s.add_argument("-f", "--file")
    s.add_argument("-a", "--aliases", help="comma separated")

    s = sub.add_parser("edit", help="edit a term")
    s.add_argument("term")
    s.add_argument("--name")
    s.add_argument("-d", "--definition")
    s.add_argument("-f", "--file")
    s.add_argument("-a", "--aliases", help="comma separated (replaces existing)")

    s = sub.add_parser("remove", help="remove a term")
    s.add_argument("term")

    for name, help_ in (("link", "print text with glossary links"), ("send", "link text and send it to Telegram")):
        s = sub.add_parser(name, help=help_)
        s.add_argument("file", nargs="?", default="-", help="text file, or - for stdin")
        s.add_argument("--all", action="store_true", help="link every occurrence, not just the first")
        s.add_argument("--exclude", help="comma separated terms not to link")
        if name == "link":
            s.add_argument("--format", choices=["html", "markdown"], default="html")
        else:
            s.add_argument("--chat")
            s.add_argument("--dry-run", action="store_true")

    sub.add_parser("mcp", help="run the MCP server (stdio) for AI agents")

    a = p.parse_args(argv)

    if a.cmd == "mcp":
        from .mcp_server import main as mcp_main

        return mcp_main()

    if a.cmd == "init":
        g = Glossary.create(a.title, a.author)
        path = config.save(telegraph_token=g.token)
        print(f"Created {g.index_url}\nKey saved to {path}\nOpen it in the browser too: {APP_URL}#key={g.token}")
    elif a.cmd == "login":
        g = Glossary(a.key).load()
        print(f"OK: {g.title} ({len(g.terms)} terms). Saved to {config.save(telegraph_token=a.key)}")
    elif a.cmd == "telegram":
        print(f"Saved to {config.save(bot_token=a.bot_token, chat_id=a.chat)}")
    elif a.cmd == "chats":
        token = config.get("bot_token") or sys.exit("Set a bot token first: telegraph-glossary telegram --bot-token ...")
        for c in discover_chats(token):
            print(f"{c['id']}\t{c['type']}\t{c['name']}")
    elif a.cmd == "info":
        g = _glossary()
        print(f"{g.title}\n{g.index_url}\n{len(g.terms)} terms")
    elif a.cmd == "list":
        g = _glossary()
        if a.json:
            print(json.dumps([t.to_dict() for t in g.terms], ensure_ascii=False, indent=2))
        for t in [] if a.json else sorted(g.terms, key=lambda t: t.term.lower()):
            print(f"{t.term}{' (' + ', '.join(t.aliases) + ')' if t.aliases else ''}\t{t.url}")
    elif a.cmd == "show":
        d = _glossary().get_definition(a.term)
        print(f"# {d['term']}\n{d['url']}\n\n{d['definition']}")
    elif a.cmd == "add":
        definition = a.definition if a.definition is not None else _read(a.file)
        e = _glossary().save_term(a.term, definition, _aliases(a.aliases))
        print(f"Added {e.term}: {e.url}")
    elif a.cmd == "edit":
        g = _glossary()
        entry = g.find(a.term) or sys.exit(f'"{a.term}" not found')
        definition = a.definition if a.definition is not None else (_read(a.file) if a.file else g.get_definition(entry.path)["definition"])
        aliases = _aliases(a.aliases)
        e = g.save_term(a.name or entry.term, definition, entry.aliases if aliases is None else aliases, original=entry.term)
        print(f"Updated {e.term}: {e.url}")
    elif a.cmd == "remove":
        print("Removed" if _glossary().remove_term(a.term) else "Not found")
    elif a.cmd in ("link", "send"):
        g = _glossary()
        r = link_text(_read(a.file), [t.to_dict() for t in g.terms], mode="all" if a.all else "first", exclude=_aliases(a.exclude) or [])
        print(f"found: {', '.join(r.found) or '-'}", file=sys.stderr)
        if a.cmd == "link":
            print(r.html if a.format == "html" else r.markdown)
        elif a.dry_run:
            print(r.html)
        else:
            token = config.get("bot_token") or sys.exit("No bot token: telegraph-glossary telegram --bot-token ...")
            chat = a.chat or config.get("chat_id") or sys.exit("No chat: pass --chat or run `telegraph-glossary telegram --chat ...`")
            send_html(token, chat, r.html)
            print(f"Sent to {chat}")


if __name__ == "__main__":
    main()
