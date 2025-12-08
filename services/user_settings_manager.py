"""User settings manager using URL query parameters for persistence.

This module provides per-user settings storage via URL query parameters.
Users bookmark the URL to save their settings across sessions.
"""

import streamlit as st
from typing import Optional, Tuple
from urllib.parse import quote, unquote


# Default values for user settings
DEFAULT_USER_SETTINGS = {
    "chat_id": "",
    "marking_syntax": "<?>",
    "custom_prefix": "",
    "custom_suffix": "",
}

# Query param keys (short to keep URLs clean)
PARAM_KEYS = {
    "chat_id": "cid",
    "marking_syntax": "syn",
    "custom_prefix": "cpre",
    "custom_suffix": "csuf",
}


class UserSettingsManager:
    """Manages per-user settings via URL query parameters.

    Settings are stored in the URL as query parameters, allowing users
    to bookmark the page and preserve their settings across sessions.
    Each user has isolated settings based on their URL.
    """

    @staticmethod
    def _get_param(key: str, default: str = "") -> str:
        """Get a query parameter value.

        Args:
            key: The setting key (e.g., 'chat_id')
            default: Default value if not found

        Returns:
            The parameter value or default
        """
        param_key = PARAM_KEYS.get(key, key)
        value = st.query_params.get(param_key, default)
        if value:
            try:
                return unquote(str(value))
            except Exception:
                return default
        return default

    @staticmethod
    def _set_param(key: str, value: str) -> None:
        """Set a query parameter value.

        Args:
            key: The setting key (e.g., 'chat_id')
            value: The value to set
        """
        param_key = PARAM_KEYS.get(key, key)
        if value:
            # Safe characters for URL: @ and - are common in chat IDs
            st.query_params[param_key] = quote(value, safe="@-")
        elif param_key in st.query_params:
            del st.query_params[param_key]

    @classmethod
    def get_chat_id(cls) -> str:
        """Get the user's Telegram chat ID.

        Returns:
            The chat ID or empty string if not set
        """
        # Check session state cache first for performance
        if "user_chat_id" in st.session_state:
            return st.session_state.user_chat_id

        chat_id = cls._get_param("chat_id")
        st.session_state.user_chat_id = chat_id
        return chat_id

    @classmethod
    def set_chat_id(cls, chat_id: str) -> None:
        """Set the user's Telegram chat ID.

        Args:
            chat_id: The chat ID (e.g., '@channelname' or '-1001234567890')
        """
        cleaned = chat_id.strip() if chat_id else ""
        cls._set_param("chat_id", cleaned)
        st.session_state.user_chat_id = cleaned

    @classmethod
    def get_marking_syntax(cls) -> str:
        """Get the user's preferred marking syntax.

        Returns:
            The marking syntax (e.g., '<?>', '[[]]', 'custom')
        """
        if "user_marking_syntax" in st.session_state:
            return st.session_state.user_marking_syntax

        syntax = cls._get_param("marking_syntax", "<?>")
        st.session_state.user_marking_syntax = syntax
        return syntax

    @classmethod
    def set_marking_syntax(cls, syntax: str) -> None:
        """Set the user's preferred marking syntax.

        Args:
            syntax: The syntax pattern (e.g., '<?>', '[[]]', 'custom')
        """
        cls._set_param("marking_syntax", syntax)
        st.session_state.user_marking_syntax = syntax

    @classmethod
    def get_custom_syntax(cls) -> Tuple[str, str]:
        """Get custom prefix and suffix for marking.

        Returns:
            Tuple of (prefix, suffix)
        """
        prefix = cls._get_param("custom_prefix", "")
        suffix = cls._get_param("custom_suffix", "")
        return prefix, suffix

    @classmethod
    def set_custom_syntax(cls, prefix: str, suffix: str) -> None:
        """Set custom prefix and suffix for marking.

        Args:
            prefix: The custom prefix (e.g., '~[')
            suffix: The custom suffix (e.g., ']~')
        """
        cls._set_param("custom_prefix", prefix)
        cls._set_param("custom_suffix", suffix)
        st.session_state.user_custom_prefix = prefix
        st.session_state.user_custom_suffix = suffix

    @classmethod
    def get_all_user_settings(cls) -> dict:
        """Get all user settings as a dictionary.

        Returns a dict compatible with the existing config structure
        for backward compatibility.

        Returns:
            Dict with telegram_bot and settings sections
        """
        prefix, suffix = cls.get_custom_syntax()
        return {
            "telegram_bot": {
                "chat_id": cls.get_chat_id(),
            },
            "settings": {
                "marking_syntax": cls.get_marking_syntax(),
                "custom_prefix": prefix,
                "custom_suffix": suffix,
                "available_syntaxes": ["<?>", "[[]]", "{{}}", "<<>>"],
                "output_format": "markdown",
            }
        }

    @classmethod
    def clear_cache(cls) -> None:
        """Clear the session state cache for user settings.

        Call this when you need to force re-reading from URL params.
        """
        keys_to_clear = [
            "user_chat_id",
            "user_marking_syntax",
            "user_custom_prefix",
            "user_custom_suffix"
        ]
        for key in keys_to_clear:
            if key in st.session_state:
                del st.session_state[key]
