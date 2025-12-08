"""Configuration manager for Telegraph Glossary."""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

import streamlit as st

CONFIG_FILE = "config.json"

DEFAULT_CONFIG: Dict[str, Any] = {
    "telegraph": {
        "access_token": None,
        "short_name": "MyGlossary",
        "author_name": "",
        "index_page_path": None,
    },
    "settings": {
        "marking_syntax": "<?>",
        "available_syntaxes": ["<?>", "[[]]", "{{}}", "<<>>"],
        "output_format": "markdown",
    },
}


def is_cloud_environment() -> bool:
    """Check if running on Streamlit Community Cloud."""
    try:
        return "telegraph" in st.secrets
    except Exception:
        return False


class ConfigManager:
    """Manages application configuration with file persistence or st.secrets."""

    def __init__(self, config_path: Optional[str] = None):
        if config_path:
            self.config_path = Path(config_path)
        else:
            app_dir = Path(__file__).parent.parent
            self.config_path = app_dir / CONFIG_FILE
        self._config: Dict[str, Any] = {}
        self._use_secrets = is_cloud_environment()

    def load(self) -> Dict[str, Any]:
        """Load configuration from st.secrets or file."""
        if self._use_secrets:
            self._load_from_secrets()
        else:
            self._load_from_file()
        self._config = self._merge_with_defaults(self._config)
        return self._config

    def _load_from_secrets(self) -> None:
        """Load configuration from Streamlit secrets."""
        self._config = {
            "telegraph": {
                "access_token": st.secrets.telegraph.get("access_token"),
                "short_name": st.secrets.telegraph.get("short_name", "MyGlossary"),
                "author_name": st.secrets.telegraph.get("author_name", ""),
                "index_page_path": st.secrets.telegraph.get("index_page_path"),
            },
            "settings": {
                "marking_syntax": st.secrets.get("settings", {}).get("marking_syntax", "<?>"),
                "available_syntaxes": ["<?>", "[[]]", "{{}}", "<<>>"],
                "output_format": st.secrets.get("settings", {}).get("output_format", "markdown"),
            },
        }

    def _load_from_file(self) -> None:
        """Load configuration from JSON file."""
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    self._config = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._config = self._deep_copy(DEFAULT_CONFIG)
        else:
            self._config = self._deep_copy(DEFAULT_CONFIG)

    def save(self) -> None:
        """Save configuration to file (only works in local mode)."""
        if self._use_secrets:
            st.warning("Configuration cannot be saved in cloud mode.")
            return
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self._config, f, indent=2, ensure_ascii=False)

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value using dot notation."""
        keys = key.split(".")
        value = self._config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default
        return value if value is not None else default

    def set(self, key: str, value: Any) -> None:
        """Set a configuration value using dot notation."""
        keys = key.split(".")
        config = self._config
        for k in keys[:-1]:
            config = config.setdefault(k, {})
        config[keys[-1]] = value
        self.save()

    def is_configured(self) -> bool:
        """Check if Telegraph is configured with a valid access token."""
        token = self.get("telegraph.access_token")
        return bool(token)

    def is_cloud_mode(self) -> bool:
        """Check if running in cloud mode."""
        return self._use_secrets

    def get_config(self) -> Dict[str, Any]:
        """Get the full configuration dictionary."""
        return self._config

    def _deep_copy(self, d: Dict[str, Any]) -> Dict[str, Any]:
        return json.loads(json.dumps(d))

    def _merge_with_defaults(self, config: Dict[str, Any]) -> Dict[str, Any]:
        result = self._deep_copy(DEFAULT_CONFIG)
        self._deep_merge(result, config)
        return result

    def _deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> None:
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value
