"""Settings panel UI component."""

import streamlit as st
from typing import Dict, Any

from services.config_manager import ConfigManager
from services.text_parser import SYNTAX_PATTERNS, validate_custom_syntax, create_custom_syntax
from utils.helpers import show_toast


def render_settings() -> None:
    st.header("Settings")
    st.subheader("Marking Syntax")
    _render_syntax_settings()
    st.divider()
    st.subheader("Telegram Bot")
    _render_telegram_bot_settings()
    st.divider()
    st.subheader("Telegraph Account")
    _render_account_settings()
    st.divider()
    st.subheader("Data Management")
    _render_data_management()


def _render_syntax_settings() -> None:
    config = st.session_state.get("config", {})
    settings = config.get("settings", {})
    current_syntax = settings.get("marking_syntax", "<?>")
    current_prefix = settings.get("custom_prefix", "")
    current_suffix = settings.get("custom_suffix", "")
    syntax_options = list(SYNTAX_PATTERNS.keys()) + ["custom"]
    def format_syntax(x):
        if x == "custom":
            return "Custom (define your own)"
        return f"{SYNTAX_PATTERNS[x]['display']} - Example: {SYNTAX_PATTERNS[x]['example']}"
    current_index = syntax_options.index(current_syntax) if current_syntax in syntax_options else 0
    selected_syntax = st.radio("Marking Syntax", options=syntax_options, index=current_index, format_func=format_syntax, label_visibility="collapsed")
    if selected_syntax == "custom":
        col1, col2 = st.columns(2)
        with col1:
            new_prefix = st.text_input("Prefix", value=current_prefix or "~[", max_chars=10)
        with col2:
            new_suffix = st.text_input("Suffix", value=current_suffix or "]~", max_chars=10)
        if new_prefix and new_suffix:
            is_valid, error_msg = validate_custom_syntax(new_prefix, new_suffix)
            if is_valid:
                custom_info = create_custom_syntax(new_prefix, new_suffix)
                st.code(custom_info["example"], language=None)
                if st.button("Save Custom Syntax", type="primary"):
                    _save_custom_syntax(new_prefix, new_suffix)
            else:
                st.error(error_msg)
    elif selected_syntax != current_syntax:
        if st.button("Save Syntax Setting", type="primary"):
            _save_syntax(selected_syntax)


def _save_syntax(syntax: str) -> None:
    config_manager = ConfigManager()
    config_manager.load()
    config_manager.set("settings.marking_syntax", syntax)
    st.session_state.config["settings"]["marking_syntax"] = syntax
    show_toast("Syntax saved!")
    st.rerun()


def _save_custom_syntax(prefix: str, suffix: str) -> None:
    config_manager = ConfigManager()
    config_manager.load()
    config_manager.set("settings.marking_syntax", "custom")
    config_manager.set("settings.custom_prefix", prefix)
    config_manager.set("settings.custom_suffix", suffix)
    st.session_state.config["settings"]["marking_syntax"] = "custom"
    st.session_state.config["settings"]["custom_prefix"] = prefix
    st.session_state.config["settings"]["custom_suffix"] = suffix
    show_toast(f"Custom syntax saved: {prefix}term{suffix}")
    st.rerun()


def _render_telegram_bot_settings() -> None:
    from services.telegram_bot_service import TelegramBotService

    # Shared bot token - users don't need to create their own bot!
    SHARED_BOT_TOKEN = "8464395532:AAGyqZQDsn3s6vZtdcaCe75c_rHZAAKerpM"
    SHARED_BOT_USERNAME = "TelegraphGlossaryBot"

    st.markdown(f"""
    **Send messages with clickable links directly to Telegram!**

    The bot is already set up - just add it to your channel and enter your Chat ID.
    """)

    # Instructions expander
    with st.expander("How to find your Chat ID", expanded=False):
        st.markdown(f"""
        **Step 1:** Add **@{SHARED_BOT_USERNAME}** to your channel/group as admin

        **Step 2:** Find your Chat ID:

        **Public Channels:**
        - Use `@yourchannel` (with @ symbol)

        **Private Channels/Groups:**
        - Open [web.telegram.org](https://web.telegram.org)
        - Go to your channel/group
        - Look at URL: `web.telegram.org/a/#-1001234567890`
        - Your Chat ID: `-1001234567890` (including the minus)

        **Alternative:** Add @RawDataBot to your channel, send a message, copy the chat ID, then remove the bot.
        """)

    config = st.session_state.get("config", {})
    telegram_config = config.get("telegram_bot", {})
    current_chat_id = telegram_config.get("chat_id", "")

    new_chat_id = st.text_input(
        "Chat ID",
        value=current_chat_id,
        placeholder="@channelname or -1001234567890"
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Test Connection", use_container_width=True):
            if new_chat_id:
                is_valid, msg = TelegramBotService.validate_chat_id(SHARED_BOT_TOKEN, new_chat_id.strip())
                if is_valid:
                    st.success(msg)
                else:
                    st.error(f"Error: {msg}")
            else:
                st.warning("Enter a Chat ID first")

    with col2:
        if new_chat_id != current_chat_id:
            if st.button("Save Chat ID", type="primary", use_container_width=True):
                _save_telegram_bot_settings(SHARED_BOT_TOKEN, new_chat_id.strip())
        elif current_chat_id:
            st.success("Configured")


def _save_telegram_bot_settings(bot_token: str, chat_id: str) -> None:
    config_manager = ConfigManager()
    config_manager.load()
    config_manager.set("telegram_bot.bot_token", bot_token)
    config_manager.set("telegram_bot.chat_id", chat_id)
    if "telegram_bot" not in st.session_state.config:
        st.session_state.config["telegram_bot"] = {}
    st.session_state.config["telegram_bot"]["bot_token"] = bot_token
    st.session_state.config["telegram_bot"]["chat_id"] = chat_id
    show_toast("Telegram settings saved!")
    st.rerun()


def _render_account_settings() -> None:
    config = st.session_state.get("config", {})
    telegraph_config = config.get("telegraph", {})
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Account Name:**")
        st.code(telegraph_config.get("short_name", "Not set"))
    with col2:
        st.markdown("**Author Name:**")
        st.code(telegraph_config.get("author_name", "Not set") or "Not set")
    index_path = telegraph_config.get("index_page_path")
    if index_path:
        st.link_button("Open Index Page", f"https://telegra.ph/{index_path}")


def _render_data_management() -> None:
    glossary = st.session_state.get("glossary", {})
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total Terms", len(glossary))
    with col2:
        if st.button("Sync from Telegraph", use_container_width=True):
            _sync_from_telegraph()
    if glossary:
        import json
        export_data = json.dumps(glossary, indent=2, ensure_ascii=False)
        st.download_button("Download JSON", export_data, file_name="glossary.json", mime="application/json")


def _sync_from_telegraph() -> None:
    telegraph = st.session_state.get("telegraph")
    config = st.session_state.get("config", {})
    if not telegraph:
        st.error("Telegraph service not initialized.")
        return
    index_path = config.get("telegraph", {}).get("index_page_path")
    if not index_path:
        st.error("No index page configured.")
        return
    try:
        with st.spinner("Syncing..."):
            glossary = telegraph.load_glossary_from_index(index_path)
            st.session_state.glossary = glossary
            show_toast(f"Synced {len(glossary)} terms!")
            st.rerun()
    except Exception as e:
        st.error(f"Sync failed: {e}")
