"""Configuration manager for Telegraph Glossary - Admin settings only.

This module handles admin configuration:
- Cloud mode: Loaded from st.secrets (read-only)
- Local mode: Loaded from config.json (read/write for setup wizard)

User settings are managed separately by UserSettingsManager.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional

import streamlit as st


CONFIG_FILE = "config.json"

# Default admin configuration
DEFAULT_ADMIN_CONFIG: Dict[str, Any] = {
    "telegraph": {
        "access_token": None,
        "short_name": "MyGlossary",
        "author_name": "",
        "index_page_path": None,
    },
}


def is_cloud_environment() -> bool:
    """Check if running on Streamlit Community Cloud.

    Returns:
        True if telegraph secrets are configured (indicating cloud deployment)
    """
    try:
        return "telegraph" in st.secrets
    except Exception:
        return False


class ConfigManager:
    """Manages admin configuration from st.secrets or config.json.

    Cloud mode: Reads from st.secrets (read-only)
    Local mode: Reads/writes config.json (for setup wizard)

    User settings (Chat ID, syntax) are managed by UserSettingsManager.
    """

    def __init__(self, config_path: Optional[str] = None):
        if config_path:
            self.config_path = Path(config_path)
        else:
            app_dir = Path(__file__).parent.parent
            self.config_path = app_dir / CONFIG_FILE
        self._config: Dict[str, Any] = {}
        self._use_secrets = is_cloud_environment()

    def load(self) -> Dict[str, Any]:
        """Load admin configuration.

        Returns:
            Dict containing admin configuration
        """
        if self._use_secrets:
            self._load_from_secrets()
        else:
            self._load_from_file()

        return self._config

    def _load_from_secrets(self) -> None:
        """Load admin configuration from Streamlit secrets."""
        try:
            self._config = {
                "telegraph": {
                    "access_token": st.secrets.telegraph.get("access_token"),
                    "short_name": st.secrets.telegraph.get("short_name", "MyGlossary"),
                    "author_name": st.secrets.telegraph.get("author_name", ""),
                    "index_page_path": st.secrets.telegraph.get("index_page_path"),
                },
            }
        except Exception:
            self._load_defaults()

    def _load_from_file(self) -> None:
        """Load configuration from JSON file (local development)."""
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    file_config = json.load(f)
                    # Only extract admin settings (telegraph)
                    self._config = {
                        "telegraph": file_config.get("telegraph", self._deep_copy(DEFAULT_ADMIN_CONFIG["telegraph"]))
                    }
            except (json.JSONDecodeError, IOError):
                self._load_defaults()
        else:
            self._load_defaults()

    def _load_defaults(self) -> None:
        """Load default configuration."""
        self._config = self._deep_copy(DEFAULT_ADMIN_CONFIG)

    def save(self) -> None:
        """Save configuration to file (only works in local mode)."""
        if self._use_secrets:
            st.warning("Configuration cannot be saved in cloud mode. Please update Streamlit secrets.")
            return

        # Load existing file to preserve other settings
        existing = {}
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            except (json.JSONDecodeError, IOError):
                pass

        # Merge admin config into existing
        existing["telegraph"] = self._config.get("telegraph", {})

        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value using dot notation.

        Args:
            key: Dot-separated key path (e.g., 'telegraph.access_token')
            default: Default value if key not found

        Returns:
            The configuration value or default
        """
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
        """Set a configuration value using dot notation (local mode only).

        Args:
            key: Dot-separated key path (e.g., 'telegraph.access_token')
            value: The value to set
        """
        if self._use_secrets:
            st.warning("Configuration cannot be saved in cloud mode.")
            return

        keys = key.split(".")
        config = self._config
        for k in keys[:-1]:
            config = config.setdefault(k, {})
        config[keys[-1]] = value
        self.save()

    def is_configured(self) -> bool:
        """Check if Telegraph is configured with a valid access token.

        Returns:
            True if access_token is set
        """
        token = self.get("telegraph.access_token")
        return bool(token)

    def is_cloud_mode(self) -> bool:
        """Check if running in cloud mode.

        Returns:
            True if running on Streamlit Cloud
        """
        return self._use_secrets

    def get_config(self) -> Dict[str, Any]:
        """Get the full admin configuration dictionary.

        Returns:
            Dict containing all admin settings
        """
        return self._config

    def _deep_copy(self, d: Dict[str, Any]) -> Dict[str, Any]:
        """Create a deep copy of a dictionary."""
        return json.loads(json.dumps(d))
