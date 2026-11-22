"""Client for the channel auto-link bot (bot/).

The bot's address is discovered from the web app's config.json, so the CLI and
the MCP server work with whatever bot the site uses, with no extra settings.
Override with TELEGRAPH_GLOSSARY_BOT_API.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any, Optional

import httpx

APP_URL = "https://nehoraihadad.github.io/telegraph-glossary/"


@lru_cache(maxsize=1)
def bot_api() -> str:
    env = os.environ.get("TELEGRAPH_GLOSSARY_BOT_API")
    if env is not None:
        return env.rstrip("/")
    try:
        return (httpx.get(f"{APP_URL}config.json", timeout=5).json().get("bot_api") or "").rstrip("/")
    except (httpx.HTTPError, ValueError):
        return ""


def _req(method: str, path: str, **kw: Any) -> Any:
    api = bot_api()
    if not api:
        raise RuntimeError("The channel auto-link bot is not enabled for this site yet.")
    r = httpx.request(method, f"{api}{path}", timeout=15, **kw)
    data = r.json()
    if r.status_code >= 400:
        raise RuntimeError(data.get("error") or f"HTTP {r.status_code}")
    return data


def available() -> bool:
    return bool(bot_api())


def info() -> dict:
    return _req("GET", "/api/info")


def status(index_path: str) -> list[dict]:
    return _req("GET", "/api/status", params={"index": index_path})["channels"]


def connect(index_path: str) -> dict:
    return _req("POST", "/api/connect", json={"index_path": index_path})


def relink(index_path: str) -> None:
    """Ask the bot to re-apply the glossary to the remembered posts of every connected channel now."""
    _req("POST", "/api/changed", json={"index_path": index_path})


def notify_changed(index_path: Optional[str]) -> None:
    """Best effort: lets the bot update existing channel posts right away."""
    if not index_path or not bot_api():
        return
    try:
        httpx.post(f"{bot_api()}/api/changed", json={"index_path": index_path}, timeout=5)
    except httpx.HTTPError:
        pass
