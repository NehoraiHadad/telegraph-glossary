"""Text processor UI component."""

import streamlit as st
import streamlit.components.v1 as components

from services.text_parser import TextParser, SYNTAX_PATTERNS, create_custom_syntax
from services.user_settings_manager import UserSettingsManager


def render_text_processor() -> None:
    st.header("Process Text")

    # Get syntax from UserSettingsManager
    current_syntax = UserSettingsManager.get_marking_syntax()
    custom_prefix, custom_suffix = UserSettingsManager.get_custom_syntax()

    if current_syntax == "custom" and custom_prefix and custom_suffix:
        syntax_info = create_custom_syntax(custom_prefix, custom_suffix)
    else:
        syntax_info = SYNTAX_PATTERNS.get(current_syntax, {})

    st.info(f"Current syntax: `{syntax_info.get('display', current_syntax)}`")
    input_text = st.text_area(
        "Input Text",
        placeholder=f"Paste your text with marked terms...\n\nExample: {syntax_info.get('example', '')}",
        height=200
    )
    col1, col2 = st.columns([1, 3])
    with col1:
        output_format = st.selectbox(
            "Output Format",
            options=["telegram", "markdown", "html"],
            format_func=lambda x: {"telegram": "Telegram", "markdown": "Markdown", "html": "HTML"}.get(x, x)
        )
    with col2:
        st.markdown("")
        process_button = st.button("Process Text", type="primary")

    if process_button and input_text:
        _process_and_display(input_text, current_syntax, output_format, custom_prefix, custom_suffix)
    elif "processed_result" in st.session_state:
        _display_result(
            st.session_state.processed_result,
            st.session_state.found_terms,
            st.session_state.missing_terms,
            output_format
        )


def _process_and_display(
    text: str,
    syntax: str,
    output_format: str,
    custom_prefix: str = "",
    custom_suffix: str = ""
) -> None:
    glossary = st.session_state.get("glossary", {})
    try:
        parser = TextParser(syntax, glossary, custom_prefix, custom_suffix)
        processed, found_terms, missing_terms = parser.process_text(text, output_format)
        st.session_state.processed_result = processed
        st.session_state.found_terms = found_terms
        st.session_state.missing_terms = missing_terms
        _display_result(processed, found_terms, missing_terms, output_format)
    except Exception as e:
        st.error(f"Error: {e}")


def _display_result(
    processed: str,
    found_terms: list,
    missing_terms: list,
    output_format: str
) -> None:
    st.divider()
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Terms Found", len(found_terms))
    with col2:
        st.metric("Missing Terms", len(missing_terms))
    with col3:
        st.metric("Format", output_format.title())

    if output_format == "telegram":
        _display_telegram_output(processed, found_terms)
    else:
        st.subheader("Output")
        st.code(processed, language=None)
        if st.button("Copy to Clipboard"):
            _copy_to_clipboard(processed)
            st.toast("Copied!")

    if missing_terms:
        st.warning(f"Missing Terms: {', '.join(missing_terms)}")


def _display_telegram_output(clean_text: str, found_terms: list) -> None:
    import os

    # Get bot token from secrets/environment (shared bot - no user setup needed)
    SHARED_BOT_TOKEN = st.secrets.get("telegram", {}).get("bot_token") or os.environ.get("TELEGRAM_BOT_TOKEN", "")

    glossary = st.session_state.get("glossary", {})

    # Get chat_id from UserSettingsManager
    chat_id = UserSettingsManager.get_chat_id()

    terms_with_urls = {}
    for term in set(found_terms):
        data = glossary.get(term, {})
        url = data.get("telegraph_url", "")
        if url:
            terms_with_urls[term] = url

    if chat_id and found_terms:
        if st.button("Send to Telegram", type="primary"):
            _send_to_telegram(clean_text, terms_with_urls, SHARED_BOT_TOKEN, chat_id)
    elif not chat_id:
        st.info("Configure your Chat ID in Settings to send directly to Telegram")

    st.subheader("Text")
    st.code(clean_text, language=None)
    if st.button("Copy Text"):
        _copy_to_clipboard(clean_text)
        st.toast("Copied!")

    if found_terms:
        st.subheader("Links")
        for term in sorted(set(found_terms)):
            data = glossary.get(term, {})
            url = data.get("telegraph_url", "")
            if url:
                col1, col2 = st.columns([1, 3])
                with col1:
                    st.markdown(f"**{term}**")
                with col2:
                    st.code(url, language=None)


def _copy_to_clipboard(text: str) -> None:
    escaped = text.replace("\\", "\\\\").replace("`", "\\`").replace("$", "\\$").replace("\n", "\\n")
    components.html(f'<script>navigator.clipboard.writeText(`{escaped}`);</script>', height=0)


def _send_to_telegram(text: str, terms_with_urls: dict, bot_token: str, chat_id: str) -> None:
    from services.telegram_bot_service import TelegramBotService
    from utils.helpers import show_toast
    try:
        with st.spinner("Sending..."):
            service = TelegramBotService(bot_token)
            service.send_formatted_text(chat_id, text, terms_with_urls)
        show_toast("Message sent!")
        st.success("Message sent to Telegram!")
    except Exception as e:
        st.error(f"Error: {e}")
