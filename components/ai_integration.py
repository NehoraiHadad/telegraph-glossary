"""AI integration UI component with embedded chat."""

import json
import subprocess
import platform
import streamlit as st
import streamlit.components.v1 as components

from utils.helpers import show_toast
from components.ai_chat import render_ai_chat


def render_ai_integration() -> None:
    """Render the AI integration tab with chat and configuration."""
    st.header("AI Integration")

    # Create sub-tabs for Chat and Configuration
    chat_tab, config_tab = st.tabs(["AI Chat", "MCP Configuration"])

    with chat_tab:
        st.markdown("Chat with AI to manage your glossary using natural language.")
        render_ai_chat()

    with config_tab:
        st.markdown("Connect your glossary to AI tools like Claude Desktop or Claude Code using the Telegraph MCP server.")
        st.subheader("MCP Server Configuration")
        _render_mcp_config()
        st.divider()
        st.subheader("Open AI Tools")
        _render_ai_tools()
        st.divider()
        st.subheader("Setup Instructions")
        _render_instructions()


def _render_mcp_config() -> None:
    config = st.session_state.get("config", {})
    access_token = config.get("telegraph", {}).get("access_token", "")
    mcp_config = {"mcpServers": {"telegraph": {"command": "npx", "args": ["telegraph-mcp"], "env": {"TELEGRAPH_ACCESS_TOKEN": access_token if access_token else "<your_token_here>"}}}}
    config_json = json.dumps(mcp_config, indent=2)
    st.code(config_json, language="json")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("Copy Config", type="primary", use_container_width=True):
            _copy_to_clipboard(config_json)
            st.toast("Configuration copied!")
    with col2:
        st.download_button("Download Config", config_json, file_name="mcp_config.json", mime="application/json", use_container_width=True)
    with col3:
        if access_token:
            if st.button("Copy Token Only", use_container_width=True):
                _copy_to_clipboard(access_token)
                st.toast("Token copied!")
    if access_token:
        st.success("Your access token is configured.")
    else:
        st.warning("No access token found.")


def _render_ai_tools() -> None:
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### Claude Desktop")
        if st.button("Open Claude Desktop", use_container_width=True):
            _open_claude_desktop()
    with col2:
        st.markdown("### Claude Code")
        st.code("claude", language="bash")
    st.markdown("---")
    st.markdown("**Install Telegraph MCP Server:**")
    col1, col2 = st.columns(2)
    with col1:
        st.code("claude mcp add telegraph -- npx telegraph-mcp", language="bash")
    with col2:
        st.code("npx telegraph-mcp", language="bash")


def _render_instructions() -> None:
    st.markdown("""### For Claude Desktop:\n1. Copy the MCP configuration\n2. Add to Claude Desktop config file\n3. Restart Claude Desktop""")
    config = st.session_state.get("config", {})
    access_token = config.get("telegraph", {}).get("access_token", "")
    if access_token:
        st.code(f"export TELEGRAPH_ACCESS_TOKEN={access_token}", language="bash")


def _copy_to_clipboard(text: str) -> None:
    escaped = text.replace("\\", "\\\\").replace("`", "\\`").replace("$", "\\$").replace("\n", "\\n")
    components.html(f'<script>navigator.clipboard.writeText(`{escaped}`);</script>', height=0)


def _open_claude_desktop() -> None:
    system = platform.system()
    try:
        if system == "Darwin":
            subprocess.run(["open", "-a", "Claude"], capture_output=True, timeout=5)
        elif system == "Windows":
            subprocess.run(["start", "Claude"], shell=True, capture_output=True, timeout=5)
        else:
            st.info("Please open Claude Desktop manually.")
    except Exception:
        st.info("Could not open Claude Desktop.")
