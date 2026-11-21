"""Settings: environment variables override ~/.config/telegraph-glossary/config.json."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

ENV = {
    "telegraph_token": "TELEGRAPH_ACCESS_TOKEN",
    "bot_token": "TELEGRAM_BOT_TOKEN",
    "chat_id": "TELEGRAM_CHAT_ID",
}


def config_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "telegraph-glossary" / "config.json"


def load() -> dict:
    p = config_path()
    data = json.loads(p.read_text()) if p.exists() else {}
    for key, env in ENV.items():
        if os.environ.get(env):
            data[key] = os.environ[env]
    return data


def get(key: str) -> Optional[str]:
    return load().get(key) or None


def save(**values: str) -> Path:
    p = config_path()
    data = json.loads(p.read_text()) if p.exists() else {}
    data.update({k: v for k, v in values.items() if v is not None})
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    try:
        p.chmod(0o600)
    except OSError:
        pass
    return p
