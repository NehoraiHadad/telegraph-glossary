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
    # User settings
    "chat_id": "cid",
    "marking_syntax": "syn",
    "custom_prefix": "cpre",
    "custom_suffix": "csuf",
    "imgbb_api_key": "ibb",  # imgbb image hosting API key
    # Telegraph settings (per-user)
    "access_token": "tok",
    "short_name": "sn",
    "author_name": "an",
    "index_page_path": "idx",
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
            Dict with telegraph, telegram_bot and settings sections
        """
        prefix, suffix = cls.get_custom_syntax()
        return {
            "telegraph": cls.get_telegraph_settings(),
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

    # ========== Telegraph Settings (per-user) ==========

    @classmethod
    def get_access_token(cls) -> str:
        """Get the user's Telegraph access token from URL.

        Returns:
            The access token or empty string if not set
        """
        return cls._get_param("access_token")

    @classmethod
    def set_access_token(cls, token: str) -> None:
        """Set the user's Telegraph access token in URL.

        Args:
            token: The Telegraph API access token
        """
        cls._set_param("access_token", token)

    @classmethod
    def get_short_name(cls) -> str:
        """Get the user's Telegraph account short name.

        Returns:
            The short name or empty string if not set
        """
        return cls._get_param("short_name")

    @classmethod
    def set_short_name(cls, name: str) -> None:
        """Set the user's Telegraph account short name.

        Args:
            name: The short name for the account
        """
        cls._set_param("short_name", name)

    @classmethod
    def get_author_name(cls) -> str:
        """Get the user's Telegraph author name.

        Returns:
            The author name or empty string if not set
        """
        return cls._get_param("author_name")

    @classmethod
    def set_author_name(cls, name: str) -> None:
        """Set the user's Telegraph author name.

        Args:
            name: The author name to display on pages
        """
        cls._set_param("author_name", name)

    @classmethod
    def get_index_page_path(cls) -> str:
        """Get the user's Telegraph index page path.

        Returns:
            The index page path or empty string if not set
        """
        return cls._get_param("index_page_path")

    @classmethod
    def set_index_page_path(cls, path: str) -> None:
        """Set the user's Telegraph index page path.

        Args:
            path: The path to the glossary index page
        """
        cls._set_param("index_page_path", path)

    @classmethod
    def is_telegraph_configured(cls) -> bool:
        """Check if Telegraph is configured (token exists in URL).

        Returns:
            True if access token is present in URL
        """
        return bool(cls.get_access_token())

    @classmethod
    def get_telegraph_settings(cls) -> dict:
        """Get all Telegraph settings from URL.

        Returns:
            Dict with access_token, short_name, author_name, index_page_path
        """
        return {
            "access_token": cls.get_access_token(),
            "short_name": cls.get_short_name(),
            "author_name": cls.get_author_name(),
            "index_page_path": cls.get_index_page_path(),
        }

    # ========== Image Hosting Settings ==========

    @classmethod
    def get_imgbb_api_key(cls) -> str:
        """Get the user's imgbb API key from URL.

        Returns:
            The API key or empty string if not set
        """
        # Check session state cache first
        if "imgbb_api_key" in st.session_state:
            return st.session_state.imgbb_api_key

        api_key = cls._get_param("imgbb_api_key")
        st.session_state.imgbb_api_key = api_key
        return api_key

    @classmethod
    def set_imgbb_api_key(cls, api_key: str) -> None:
        """Set the user's imgbb API key in URL.

        Args:
            api_key: The imgbb API key
        """
        cleaned = api_key.strip() if api_key else ""
        cls._set_param("imgbb_api_key", cleaned)
        st.session_state.imgbb_api_key = cleaned
