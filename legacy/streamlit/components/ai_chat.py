"""AI Chat component for Streamlit with PydanticAI integration.

This module provides an interactive chat interface using PydanticAI
to connect to multiple AI providers (Claude, OpenAI, Gemini) with
Telegraph MCP tools for glossary management.

Features:
- Real-time streaming responses
- Tool call visibility (shows when AI uses Telegraph tools)
- Progress feedback during execution
"""

import streamlit as st
import logging
import json

from services.pydantic_ai_service import TelegraphAIService, can_use_mcp
from services.stream_types import StreamEvent, EventType
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
    """Display chat message history including tool calls."""
    for message in st.session_state.chat_messages:
        role = message["role"]
        content = message.get("content", "")
        tool_calls = message.get("tool_calls", [])

        if role == "user":
            with st.chat_message("user"):
                st.markdown(content)
        elif role == "assistant":
            with st.chat_message("assistant"):
                # Show tool calls if any were used
                if tool_calls:
                    with st.expander(f"🔧 Tools Used ({len(tool_calls)})", expanded=False):
                        for tc in tool_calls:
                            _render_tool_call_history(tc)
                # Show response text
                st.markdown(content)


def _render_tool_call_history(tool_call: dict) -> None:
    """Render a single tool call from history."""
    tool_name = tool_call.get("name", "Unknown")
    args = tool_call.get("args", {})
    result = tool_call.get("result", "")
    success = tool_call.get("success", True)

    # Format args nicely
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except:
            pass

    args_str = json.dumps(args, indent=2, ensure_ascii=False) if isinstance(args, dict) else str(args)

    if success:
        st.success(f"**{tool_name}**")
    else:
        st.error(f"**{tool_name}** (failed)")

    st.code(args_str, language="json")
    if result:
        st.caption(f"Result: {result[:200]}{'...' if len(result) > 200 else ''}")


def _handle_chat_input() -> None:
    """Handle user chat input and generate streaming response with tool visibility."""
    if prompt := st.chat_input("Ask me to help with your glossary..."):
        # Add user message to history
        st.session_state.chat_messages.append({
            "role": "user",
            "content": prompt
        })

        # Display user message
        with st.chat_message("user"):
            st.markdown(prompt)

        # Generate AI response with event streaming
        with st.chat_message("assistant"):
            # Create containers for different parts of the response
            tools_container = st.container()
            response_container = st.container()

            full_response = ""
            tool_calls = []
            current_tool_expander = None
            tools_shown = False

            try:
                # Create PydanticAI service
                service = TelegraphAIService(
                    provider=st.session_state.ai_provider,
                    api_key=st.session_state.ai_api_key,
                    access_token=UserSettingsManager.get_access_token(),
                    glossary=st.session_state.get("glossary", {})
                )

                # Response placeholder for streaming text
                response_placeholder = response_container.empty()

                # Status indicator
                with tools_container:
                    status = st.status("Processing...", expanded=True)

                # Stream events
                for event in service.chat_stream_with_events(prompt):
                    if event.type == EventType.TOOL_CALL:
                        # Show tool being called
                        tool_name = event.data.get("tool_name", "unknown")
                        args = event.data.get("args", {})

                        # Parse args if string
                        if isinstance(args, str):
                            try:
                                args = json.loads(args)
                            except:
                                pass

                        status.update(label=f"Calling {tool_name}...", state="running")

                        # Add to tool calls list
                        tool_calls.append({
                            "name": tool_name,
                            "args": args,
                            "tool_call_id": event.data.get("tool_call_id"),
                            "result": None,
                            "success": None,
                        })

                        tools_shown = True

                    elif event.type == EventType.TOOL_RESULT:
                        # Update the corresponding tool call with result
                        tool_call_id = event.data.get("tool_call_id")
                        result = event.data.get("result", "")
                        success = event.data.get("success", True)

                        # Find and update the tool call
                        for tc in tool_calls:
                            if tc.get("tool_call_id") == tool_call_id:
                                tc["result"] = result
                                tc["success"] = success
                                break

                        if success:
                            status.update(label="Tool completed", state="running")
                        else:
                            status.update(label="Tool failed", state="error")

                    elif event.type == EventType.TEXT_DELTA:
                        # Streaming text chunk
                        delta = event.data.get("delta", "")
                        full_response += delta
                        response_placeholder.markdown(full_response + "▌")

                    elif event.type == EventType.TEXT:
                        # Complete text (fallback)
                        if not full_response:
                            full_response = event.data.get("text", "")
                            response_placeholder.markdown(full_response)

                    elif event.type == EventType.DONE:
                        # Streaming complete
                        if not full_response:
                            full_response = event.data.get("text", "")
                        status.update(label="Done", state="complete", expanded=False)

                    elif event.type == EventType.ERROR:
                        # Error occurred
                        error_msg = event.data.get("message", "Unknown error")
                        full_response = f"Error: {error_msg}"
                        status.update(label="Error", state="error")
                        response_placeholder.error(full_response)

                # Final render
                response_placeholder.markdown(full_response)

                # Show tool calls summary if any were used
                if tools_shown and tool_calls:
                    with tools_container:
                        with st.expander(f"🔧 Tools Used ({len(tool_calls)})", expanded=False):
                            for tc in tool_calls:
                                _render_tool_call_live(tc)

            except Exception as e:
                logger.error(f"Error getting AI response: {e}", exc_info=True)
                full_response = f"Error: {str(e)}"
                response_container.error(full_response)

        # Add assistant message to history (including tool calls)
        st.session_state.chat_messages.append({
            "role": "assistant",
            "content": full_response,
            "tool_calls": tool_calls if tool_calls else None,
        })


def _render_tool_call_live(tool_call: dict) -> None:
    """Render a tool call during live streaming."""
    tool_name = tool_call.get("name", "Unknown")
    args = tool_call.get("args", {})
    result = tool_call.get("result")
    success = tool_call.get("success")

    # Format args
    args_str = json.dumps(args, indent=2, ensure_ascii=False) if isinstance(args, dict) else str(args)

    # Show tool with status
    if success is None:
        st.info(f"**{tool_name}** (executing...)")
    elif success:
        st.success(f"**{tool_name}**")
    else:
        st.error(f"**{tool_name}** (failed)")

    # Show args in collapsible code block
    with st.expander("Arguments", expanded=False):
        st.code(args_str, language="json")

    # Show result if available
    if result:
        st.caption(f"Result: {result[:300]}{'...' if len(str(result)) > 300 else ''}")

    st.divider()
