"""Settings panel UI component."""

import streamlit as st
from typing import Dict, Any

from services.user_settings_manager import UserSettingsManager
from services.text_parser import SYNTAX_PATTERNS, validate_custom_syntax, create_custom_syntax
from utils.helpers import show_toast


def render_settings() -> None:
    st.header("Settings")
    st.subheader("Marking Syntax")
    _render_syntax_settings()
    st.divider()
    st.subheader("Image Hosting")
    _render_image_hosting_settings()
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
    # Get syntax from UserSettingsManager instead of config
    current_syntax = UserSettingsManager.get_marking_syntax()
    current_prefix, current_suffix = UserSettingsManager.get_custom_syntax()

    syntax_options = list(SYNTAX_PATTERNS.keys()) + ["custom"]

    def format_syntax(x):
        if x == "custom":
            return "Custom (define your own)"
        return f"{SYNTAX_PATTERNS[x]['display']} - Example: {SYNTAX_PATTERNS[x]['example']}"

    current_index = syntax_options.index(current_syntax) if current_syntax in syntax_options else 0
    selected_syntax = st.radio(
        "Marking Syntax",
        options=syntax_options,
        index=current_index,
        format_func=format_syntax,
        label_visibility="collapsed"
    )

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
    UserSettingsManager.set_marking_syntax(syntax)
    # Update session state for backward compatibility
    if "config" in st.session_state and "settings" in st.session_state.config:
        st.session_state.config["settings"]["marking_syntax"] = syntax
    show_toast("Syntax saved! Bookmark this page to keep your settings.")
    st.rerun()


def _save_custom_syntax(prefix: str, suffix: str) -> None:
    UserSettingsManager.set_custom_syntax(prefix, suffix)
    UserSettingsManager.set_marking_syntax("custom")
    # Update session state for backward compatibility
    if "config" in st.session_state and "settings" in st.session_state.config:
        st.session_state.config["settings"]["marking_syntax"] = "custom"
        st.session_state.config["settings"]["custom_prefix"] = prefix
        st.session_state.config["settings"]["custom_suffix"] = suffix
    show_toast(f"Custom syntax saved: {prefix}term{suffix}")
    st.rerun()


def _render_image_hosting_settings() -> None:
    """Render image hosting settings (imgbb API key)."""

    st.markdown("""
    **Upload images directly** instead of using external links.

    Images are hosted on [imgbb.com](https://imgbb.com) - free and permanent.
    """)

    # Get current API key from session state
    current_key = st.session_state.get("imgbb_api_key", "")

    with st.expander("Setup Instructions", expanded=not current_key):
        st.markdown("""
        1. Go to [api.imgbb.com](https://api.imgbb.com/)
        2. Sign up (free) or log in
        3. Copy your API key
        4. Paste it below
        """)

    # API key input (masked)
    new_key = st.text_input(
        "imgbb API Key",
        value=current_key,
        type="password",
        placeholder="Enter your imgbb API key",
        help="Your API key is stored in the URL (like other settings)"
    )

    col1, col2 = st.columns(2)

    with col1:
        if new_key and new_key != current_key:
            if st.button("Save API Key", type="primary", use_container_width=True):
                _save_imgbb_api_key(new_key)

    with col2:
        if current_key:
            if st.button("Test Upload", use_container_width=True):
                _test_imgbb_connection(current_key)

    # Status indicator
    if current_key:
        st.success("Image upload enabled")
    else:
        st.info("Add API key to enable direct image uploads")


def _save_imgbb_api_key(api_key: str) -> None:
    """Save imgbb API key to session state and URL."""
    st.session_state["imgbb_api_key"] = api_key
    UserSettingsManager.set_imgbb_api_key(api_key)
    show_toast("API key saved! Bookmark this page to keep your settings.")
    st.rerun()


def _test_imgbb_connection(api_key: str) -> None:
    """Test imgbb API connection."""
    try:
        from services.imgbb_service import ImgbbService

        # Create a tiny test image (1x1 red pixel PNG)
        test_image = bytes([
            0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,  # PNG signature
            0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,  # IHDR chunk
            0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,  # 1x1
            0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53,
            0xDE, 0x00, 0x00, 0x00, 0x0C, 0x49, 0x44, 0x41,  # IDAT chunk
            0x54, 0x08, 0xD7, 0x63, 0xF8, 0xCF, 0xC0, 0x00,
            0x00, 0x00, 0x03, 0x00, 0x01, 0x00, 0x18, 0xDD,
            0x8D, 0xB4, 0x00, 0x00, 0x00, 0x00, 0x49, 0x45,  # IEND chunk
            0x4E, 0x44, 0xAE, 0x42, 0x60, 0x82
        ])

        service = ImgbbService(api_key)
        with st.spinner("Testing..."):
            url = service.upload_image(test_image, "test.png")

        st.success(f"Connection successful!")

    except Exception as e:
        st.error(f"Test failed: {str(e)}")


def _render_telegram_bot_settings() -> None:
    import os
    from services.telegram_bot_service import TelegramBotService

    # Get bot token from secrets/environment (shared bot - users don't need their own)
    SHARED_BOT_TOKEN = st.secrets.get("telegram", {}).get("bot_token") or os.environ.get("TELEGRAM_BOT_TOKEN", "")
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

    # Get chat_id from UserSettingsManager
    current_chat_id = UserSettingsManager.get_chat_id()

    new_chat_id = st.text_input(
        "Chat ID",
        value=current_chat_id,
        placeholder="@channelname or -1001234567890"
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Test Connection", use_container_width=True):
            if not SHARED_BOT_TOKEN:
                st.error("Bot token not configured! Add [telegram] bot_token to Streamlit secrets.")
            elif not new_chat_id:
                st.warning("Enter a Chat ID first")
            else:
                is_valid, msg = TelegramBotService.validate_chat_id(SHARED_BOT_TOKEN, new_chat_id.strip())
                if is_valid:
                    st.success(msg)
                else:
                    st.error(f"Error: {msg}")

    with col2:
        if new_chat_id != current_chat_id:
            if st.button("Save Chat ID", type="primary", use_container_width=True):
                _save_telegram_chat_id(new_chat_id.strip())
        elif current_chat_id:
            st.success("Configured")


def _render_bookmark_helper() -> None:
    """Render bookmark helper with copy URL button."""
    import streamlit.components.v1 as components

    access_token = UserSettingsManager.get_access_token()

    if access_token:
        # User has glossary - critical warning about URL
        st.warning("""
        **Important!** Your URL contains your glossary access token.
        **If you lose the URL, you lose access to your glossary!**
        """)

        st.info("**Save this URL** - it contains all your settings and glossary access.")

        col1, col2 = st.columns([2, 1])
        with col1:
            st.caption("**Ctrl+D** (Windows/Linux) or **Cmd+D** (Mac) to bookmark")
        with col2:
            if st.button("Copy URL", key="copy_settings_url", type="primary", use_container_width=True):
                # JavaScript to copy current URL to clipboard
                components.html(
                    """
                    <script>
                    navigator.clipboard.writeText(window.parent.location.href);
                    </script>
                    """,
                    height=0
                )
                st.toast("URL copied! Save it somewhere safe.")
    else:
        # No glossary yet
        st.info("Create a Telegraph account to start. Your settings will be saved in the URL.")


def _save_telegram_chat_id(chat_id: str) -> None:
    UserSettingsManager.set_chat_id(chat_id)
    # Update session state for backward compatibility
    if "config" in st.session_state:
        if "telegram_bot" not in st.session_state.config:
            st.session_state.config["telegram_bot"] = {}
        st.session_state.config["telegram_bot"]["chat_id"] = chat_id
    show_toast("Chat ID saved! Bookmark this page to keep your settings.")
    st.rerun()


def _render_account_settings() -> None:
    # Show bookmark helper prominently here
    _render_bookmark_helper()

    st.markdown("---")

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
