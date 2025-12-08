"""AI Chat component for Streamlit with MCP tool integration.

This module provides an interactive chat interface that connects AI providers
(Claude, OpenAI, Gemini) with the Telegraph MCP server, enabling AI assistants
to manage glossary entries through natural language.

The chat interface:
- Supports multiple AI providers with automatic format conversion
- Integrates Telegraph MCP tools for glossary management
- Displays tool execution status and results
- Maintains conversation history
- Provides contextual system prompts with glossary info
"""

import streamlit as st
from typing import Optional, List, Dict, Any
import logging

from services.mcp_client import TelegraphMCPClient
from services.ai_providers import ClaudeProvider, OpenAIProvider, GeminiProvider
from services.user_settings_manager import UserSettingsManager

# Configure logging
logger = logging.getLogger(__name__)


def render_ai_chat() -> None:
    """Render the AI chat interface with MCP tool support.

    This is the main entry point for the AI chat component. It handles:
    1. Session state initialization
    2. API key configuration UI
    3. Prerequisites checking (Telegraph token, AI API key)
    4. Chat history display
    5. User input handling
    """

    # 1. Initialize session state for chat
    _init_chat_state()

    # 2. Render API key config in an expander (not sidebar - this is a tab)
    _render_api_config()

    # 3. Check prerequisites (Telegraph token, AI API key)
    if not _check_prerequisites():
        return

    # 4. Display chat history
    _render_chat_history()

    # 5. Handle user input
    _handle_chat_input()


def _init_chat_state() -> None:
    """Initialize session state variables for chat.

    Sets up all necessary session state keys with default values if they
    don't already exist. This ensures the chat component has all required
    state before rendering.
    """
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []

    if "ai_api_key" not in st.session_state:
        st.session_state.ai_api_key = ""

    if "ai_provider" not in st.session_state:
        st.session_state.ai_provider = "Claude"

    if "mcp_tools_cache" not in st.session_state:
        st.session_state.mcp_tools_cache = None


def _render_api_config() -> None:
    """Render API key configuration section.

    Displays an expander with:
    - API key input (password field for security)
    - Provider selection dropdown (Claude/OpenAI/Gemini)
    - Clear chat button

    The expander is auto-expanded if no API key is configured yet.
    """
    with st.expander("AI Configuration", expanded=not st.session_state.ai_api_key):
        col1, col2 = st.columns([2, 1])

        with col1:
            api_key = st.text_input(
                "API Key",
                type="password",
                value=st.session_state.ai_api_key,
                placeholder="Enter your API key...",
                help="Your API key is stored only in session memory (not saved)",
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

        # Clear chat button
        if st.session_state.chat_messages:
            if st.button("Clear Chat", type="secondary", key="clear_chat_btn"):
                st.session_state.chat_messages = []
                st.rerun()


def _check_prerequisites() -> bool:
    """Check if all prerequisites are met for chat.

    Verifies:
    1. Telegraph token is configured (from UserSettingsManager)
    2. AI API key is provided

    Returns:
        True if all prerequisites are met, False otherwise.
        Displays appropriate warnings/info messages if prerequisites are missing.
    """
    telegraph_token = UserSettingsManager.get_access_token()

    if not telegraph_token:
        st.warning("Please configure your Telegraph token in the Settings tab first.")
        return False

    if not st.session_state.ai_api_key:
        st.info("Enter your AI provider API key above to start chatting.")
        return False

    return True


def _render_chat_history() -> None:
    """Display chat message history.

    Iterates through chat messages and displays them using Streamlit's
    chat_message component. Skips tool-related messages (role: tool/function)
    as they're displayed inline during execution.

    Handles both string content and structured content (lists with text blocks).
    """
    for message in st.session_state.chat_messages:
        role = message["role"]
        content = message.get("display_content", message.get("content", ""))

        # Skip tool-related messages in display
        if role in ["tool", "function"]:
            continue

        with st.chat_message(role):
            if isinstance(content, str):
                st.markdown(content)
            elif isinstance(content, list):
                # Handle structured content (with tool results)
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        st.markdown(item.get("text", ""))


def _handle_chat_input() -> None:
    """Handle user chat input and generate response.

    Processes new user messages:
    1. Adds user message to history
    2. Displays user message in chat
    3. Generates AI response with tool support
    4. Displays assistant response
    5. Adds assistant response to history
    """
    if prompt := st.chat_input("Ask me to help with your glossary..."):
        # Add user message to history
        st.session_state.chat_messages.append({
            "role": "user",
            "content": prompt,
            "display_content": prompt
        })

        # Display user message
        with st.chat_message("user"):
            st.markdown(prompt)

        # Generate AI response
        with st.chat_message("assistant"):
            response_text = _get_ai_response()
            st.markdown(response_text)

        # Add assistant message to history
        st.session_state.chat_messages.append({
            "role": "assistant",
            "content": response_text,
            "display_content": response_text
        })


def _get_ai_response() -> str:
    """Get response from AI provider with MCP tool support.

    This is the core function that:
    1. Initializes MCP client and fetches available tools
    2. Initializes the selected AI provider
    3. Builds conversation messages with system prompt
    4. Sends request to AI with tools available
    5. Handles tool calls if AI decides to use them
    6. Returns final text response

    Returns:
        The AI's text response as a string.
        Returns error message string if any exception occurs.
    """
    try:
        telegraph_token = UserSettingsManager.get_access_token()

        # Initialize MCP client and get tools
        mcp_client = TelegraphMCPClient(telegraph_token)

        with st.status("Connecting to Telegraph MCP...", expanded=False) as status:
            tools = mcp_client.get_tools_sync()
            status.update(label=f"Found {len(tools)} tools", state="complete")
            logger.info(f"Retrieved {len(tools)} MCP tools")

        # Initialize AI provider
        provider = _get_provider()

        # Build messages for AI (filter out display-only fields)
        messages = _build_messages_for_ai()

        # Add system prompt with context
        system_prompt = _build_system_prompt()

        # Get AI response with tools
        with st.status("Thinking...", expanded=False) as status:
            # For first message, include system prompt inline
            if len(messages) == 1:
                full_messages = [{
                    "role": "user",
                    "content": system_prompt + "\n\n" + messages[-1]["content"]
                }]
            else:
                # For multi-turn, add system as separate message if provider supports it
                # Claude and Gemini handle system prompts differently
                if st.session_state.ai_provider == "Claude":
                    # Claude expects system in messages with proper role handling
                    full_messages = messages
                else:
                    full_messages = [{"role": "system", "content": system_prompt}] + messages

            response = provider.chat(
                messages=full_messages,
                tools=tools
            )
            status.update(label="Got response", state="complete")
            logger.debug(f"Received response from {st.session_state.ai_provider}")

        # Check for tool calls
        tool_calls = provider.extract_tool_calls(response)

        if tool_calls:
            logger.info(f"AI requested {len(tool_calls)} tool calls")
            return _handle_tool_calls(tool_calls, mcp_client, provider, messages, tools, system_prompt)

        # Extract text response
        return _extract_text_response(response)

    except Exception as e:
        logger.error(f"Error getting AI response: {e}", exc_info=True)
        return f"Error: {str(e)}"


def _get_provider():
    """Get the selected AI provider instance.

    Creates and returns an instance of the appropriate AI provider
    based on the user's selection in session state.

    Returns:
        An instance of ClaudeProvider, OpenAIProvider, or GeminiProvider.

    Raises:
        ValueError: If an unknown provider is selected.
    """
    provider_name = st.session_state.ai_provider
    api_key = st.session_state.ai_api_key

    if provider_name == "Claude":
        return ClaudeProvider(api_key)
    elif provider_name == "OpenAI":
        return OpenAIProvider(api_key)
    elif provider_name == "Gemini":
        return GeminiProvider(api_key)
    else:
        raise ValueError(f"Unknown provider: {provider_name}")


def _build_messages_for_ai() -> List[Dict[str, Any]]:
    """Build message list for AI from chat history.

    Filters chat history to include only user and assistant messages
    with simple content format. Tool messages are handled separately
    during tool execution.

    Returns:
        List of message dictionaries with 'role' and 'content' keys.
    """
    messages = []
    for msg in st.session_state.chat_messages:
        role = msg["role"]
        content = msg.get("content", "")

        if role in ["user", "assistant"]:
            if isinstance(content, str):
                messages.append({"role": role, "content": content})

    return messages


def _build_system_prompt() -> str:
    """Build system prompt with glossary context.

    Creates a comprehensive system prompt that:
    - Defines the AI's role as a glossary management assistant
    - Provides context about available MCP tools
    - Includes current glossary statistics
    - Lists existing terms (up to 20, with ellipsis if more)
    - Gives guidance on when and how to use tools

    Returns:
        The complete system prompt string.
    """
    glossary = st.session_state.get("glossary", {})

    prompt = """You are a helpful assistant that manages a Telegraph glossary.
You have access to MCP tools to create, edit, and manage Telegraph pages.

Current glossary has {term_count} terms.
""".format(term_count=len(glossary))

    if glossary:
        terms_list = ", ".join(list(glossary.keys())[:20])
        if len(glossary) > 20:
            terms_list += f"... and {len(glossary) - 20} more"
        prompt += f"\nExisting terms: {terms_list}"

    prompt += """

When the user asks you to create or edit glossary entries:
1. Use the create_page tool for new entries
2. Use the edit_page tool to update existing entries
3. Format content in Markdown
4. Be concise and helpful

Always confirm what action you took after using a tool."""

    return prompt


def _handle_tool_calls(
    tool_calls: List[Dict],
    mcp_client: TelegraphMCPClient,
    provider,
    messages: List[Dict],
    tools: List[Dict],
    system_prompt: str
) -> str:
    """Execute tool calls and get final response.

    This function handles the tool execution loop:
    1. Executes each tool call requested by the AI
    2. Displays execution status and results to the user
    3. Formats tool results for the AI provider
    4. Sends tool results back to AI for final response generation

    Args:
        tool_calls: List of tool call dictionaries from AI
        mcp_client: Telegraph MCP client instance
        provider: AI provider instance
        messages: Conversation messages so far
        tools: List of available tools
        system_prompt: System prompt for context

    Returns:
        The AI's final text response after processing tool results.
    """
    results = []

    # Execute each tool call
    for tool_call in tool_calls:
        tool_name = tool_call["name"]
        tool_input = tool_call.get("input", tool_call.get("arguments", {}))
        tool_id = tool_call.get("id", f"call_{len(results)}")

        with st.status(f"Executing {tool_name}...", expanded=True) as status:
            try:
                result = mcp_client.call_tool_sync(tool_name, tool_input)
                status.update(label=f"{tool_name} completed", state="complete")
                logger.info(f"Tool {tool_name} executed successfully")

                results.append({
                    "id": tool_id,
                    "name": tool_name,
                    "result": str(result)
                })

                # Display result preview (truncated if long)
                result_preview = str(result)[:500]
                if len(str(result)) > 500:
                    result_preview += "..."
                st.code(result_preview, language="json")

            except Exception as e:
                status.update(label=f"{tool_name} failed", state="error")
                logger.error(f"Tool {tool_name} failed: {e}")
                results.append({
                    "id": tool_id,
                    "name": tool_name,
                    "result": f"Error: {str(e)}"
                })

    # Build messages with tool results for follow-up
    follow_up_messages = messages.copy()

    # Add assistant message with tool calls (provider-specific format)
    # This is needed for some providers to maintain conversation state

    # Add tool results
    for result in results:
        # Format tool result according to provider's requirements
        tool_result_msg = provider.format_tool_result(
            result["id"],
            result.get("name", ""),
            result["result"]
        )
        follow_up_messages.append(tool_result_msg)

    # Get final response from AI after tool execution
    with st.status("Generating summary...", expanded=False) as status:
        # Include system prompt for context
        if st.session_state.ai_provider == "Claude":
            final_messages = follow_up_messages
        else:
            final_messages = [{"role": "system", "content": system_prompt}] + follow_up_messages

        final_response = provider.chat(
            messages=final_messages,
            tools=tools
        )
        status.update(label="Done", state="complete")
        logger.debug("Received final response after tool execution")

    return _extract_text_response(final_response)


def _extract_text_response(response: Dict) -> str:
    """Extract text content from AI response.

    Handles different response formats from various AI providers:
    - String content (simple text)
    - List of content blocks (structured response)
    - Provider-specific response objects

    Args:
        response: The raw response dictionary from AI provider

    Returns:
        Extracted text content as a string.
        Returns fallback message if no text can be extracted.
    """
    content = response.get("content", [])

    # Handle string content directly
    if isinstance(content, str):
        return content

    # Handle list of content blocks
    text_parts = []
    for item in content:
        if isinstance(item, dict):
            if item.get("type") == "text":
                text_parts.append(item.get("text", ""))
        elif hasattr(item, "text"):
            # Handle objects with text attribute
            text_parts.append(item.text)
        elif hasattr(item, "type") and item.type == "text":
            # Handle typed objects
            text_parts.append(item.text)

    if text_parts:
        return "\n".join(text_parts)

    # Fallback if no text content found
    logger.warning("No text content found in response")
    return "No response generated."
