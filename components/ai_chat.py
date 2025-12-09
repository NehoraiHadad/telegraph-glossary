"""AI Chat component for Streamlit with PydanticAI integration.

This module provides an interactive chat interface using PydanticAI
to connect to multiple AI providers (Claude, OpenAI, Gemini) with
Telegraph MCP tools for glossary management.
"""

import streamlit as st
import logging

from services.pydantic_ai_service import TelegraphAIService, can_use_mcp
from services.user_settings_manager import UserSettingsManager

logger = logging.getLogger(__name__)


def render_ai_chat() -> None:
    """Render the AI chat interface with PydanticAI integration."""
    _init_chat_state()
    _render_api_config()

    if not _check_prerequisites():
        return

    _render_chat_history()
    _handle_chat_input()


def _init_chat_state() -> None:
    """Initialize session state variables for chat."""
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []
    if "ai_api_key" not in st.session_state:
        st.session_state.ai_api_key = ""
    if "ai_provider" not in st.session_state:
        st.session_state.ai_provider = "Claude"


def _render_api_config() -> None:
    """Render API key configuration section."""
    with st.expander("AI Configuration", expanded=not st.session_state.ai_api_key):
        col1, col2 = st.columns([2, 1])

        with col1:
            api_key = st.text_input(
                "API Key",
                type="password",
                value=st.session_state.ai_api_key,
                placeholder="Enter your API key...",
                help="Your API key is stored only in session memory",
                key="ai_api_key_input"
            )
            if api_key != st.session_state.ai_api_key:
                st.session_state.ai_api_key = api_key

        with col2:
            provider = st.selectbox(
                "Provider",
                ["Claude", "OpenAI", "Gemini"],
                index=["Claude", "OpenAI", "Gemini"].index(st.session_state.ai_provider),
                key="ai_provider_select"
            )
            if provider != st.session_state.ai_provider:
                st.session_state.ai_provider = provider

        # Show MCP status
        if can_use_mcp():
            st.caption("Using Telegraph MCP server (npx)")
        else:
            st.caption("Using direct Telegraph API (no npx)")

        if st.session_state.chat_messages:
            if st.button("Clear Chat", type="secondary", key="clear_chat_btn"):
                st.session_state.chat_messages = []
                st.rerun()


def _check_prerequisites() -> bool:
    """Check if all prerequisites are met for chat."""
    telegraph_token = UserSettingsManager.get_access_token()

    if not telegraph_token:
        st.warning("Please configure your Telegraph token in the Settings tab first.")
        return False

    if not st.session_state.ai_api_key:
        st.info("Enter your AI provider API key above to start chatting.")
        return False

    return True


def _render_chat_history() -> None:
    """Display chat message history."""
    for message in st.session_state.chat_messages:
        role = message["role"]
        content = message.get("content", "")

        if role in ["user", "assistant"]:
            with st.chat_message(role):
                st.markdown(content)


def _handle_chat_input() -> None:
    """Handle user chat input and generate streaming response."""
    if prompt := st.chat_input("Ask me to help with your glossary..."):
        # Add user message to history
        st.session_state.chat_messages.append({
            "role": "user",
            "content": prompt
        })

        # Display user message
        with st.chat_message("user"):
            st.markdown(prompt)

        # Generate AI response with streaming
        with st.chat_message("assistant"):
            response_placeholder = st.empty()
            full_response = ""

            try:
                # Create PydanticAI service
                service = TelegraphAIService(
                    provider=st.session_state.ai_provider,
                    api_key=st.session_state.ai_api_key,
                    access_token=UserSettingsManager.get_access_token(),
                    glossary=st.session_state.get("glossary", {})
                )

                # Show status while connecting
                with st.status("Connecting to AI...", expanded=False) as status:
                    # Stream the response
                    for chunk in service.chat_stream(prompt):
                        full_response += chunk
                        response_placeholder.markdown(full_response + "")
                    status.update(label="Done", state="complete")

                response_placeholder.markdown(full_response)

            except Exception as e:
                logger.error(f"Error getting AI response: {e}", exc_info=True)
                full_response = f"Error: {str(e)}"
                response_placeholder.error(full_response)

        # Add assistant message to history
        st.session_state.chat_messages.append({
            "role": "assistant",
            "content": full_response
        })
