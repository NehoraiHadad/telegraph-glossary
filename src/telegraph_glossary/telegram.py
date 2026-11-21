"""Send linked posts through the user's own Telegram bot."""

from __future__ import annotations

from typing import Any

import httpx

MAX_LEN = 4096


class TelegramError(Exception):
    pass


def bot_call(token: str, method: str, params: dict[str, Any] | None = None) -> Any:
    r = httpx.post(f"https://api.telegram.org/bot{token}/{method}", json=params or {}, timeout=30).json()
    if not r.get("ok"):
        raise TelegramError(r.get("description") or "Telegram error")
    return r["result"]


def send_html(token: str, chat_id: str, html: str, preview: bool = False) -> dict:
    return bot_call(
        token,
        "sendMessage",
        {"chat_id": chat_id, "text": html, "parse_mode": "HTML", "link_preview_options": {"is_disabled": not preview}},
    )


def discover_chats(token: str) -> list[dict[str, str]]:
    """Chats the bot has seen recently (channels it was added to, people who wrote to it)."""
    chats: dict[str, dict[str, str]] = {}
    for u in bot_call(token, "getUpdates", {"allowed_updates": ["message", "channel_post", "my_chat_member"]}):
        chat = (u.get("my_chat_member") or u.get("message") or u.get("channel_post") or {}).get("chat")
        if not chat:
            continue
        name = chat.get("title") or " ".join(filter(None, [chat.get("first_name"), chat.get("last_name")])) or chat.get("username", "")
        chats[str(chat["id"])] = {"id": str(chat["id"]), "name": name, "type": chat.get("type", "")}
    return list(chats.values())
