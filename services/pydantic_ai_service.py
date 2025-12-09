"""
PydanticAI service for Telegraph glossary management.

This module provides a unified AI service using PydanticAI that:
- Supports multiple AI providers (Claude, OpenAI, Gemini)
- Integrates Telegraph MCP tools via MCPServerStdio
- Falls back to direct Python tools when npx is unavailable
- Provides streaming support for Streamlit integration
"""

import asyncio
import os
import shutil
import logging
from typing import Generator, Dict, Any, Optional, List
from dataclasses import dataclass

from pydantic_ai import Agent
from pydantic_ai.mcp import MCPServerStdio

logger = logging.getLogger(__name__)

# Model name mappings for PydanticAI
MODEL_NAMES = {
    "Claude": "anthropic:claude-sonnet-4-20250514",
    "OpenAI": "openai:gpt-4o",
    "Gemini": "google-gla:gemini-2.5-flash",
}

# Environment variable names for API keys
API_KEY_ENV_VARS = {
    "Claude": "ANTHROPIC_API_KEY",
    "OpenAI": "OPENAI_API_KEY",
    "Gemini": "GOOGLE_API_KEY",
}


@dataclass
class GlossaryContext:
    """Context for the glossary agent."""
    access_token: str
    glossary: Dict[str, Any]
    author_name: str = "Telegraph Glossary"


def can_use_mcp() -> bool:
    """Check if MCP is available (npx installed)."""
    return shutil.which("npx") is not None


class TelegraphAIService:
    """
    PydanticAI-based service for AI chat with Telegraph tools.

    This service wraps PydanticAI Agent with:
    - Automatic provider selection (Claude, OpenAI, Gemini)
    - MCPServerStdio integration for Telegraph tools
    - Fallback to direct Python tools when npx unavailable
    - Async-to-sync streaming adapter for Streamlit

    Example:
        ```python
        service = TelegraphAIService(
            provider="Claude",
            api_key="sk-...",
            access_token="telegraph_token",
            glossary={"API": {...}}
        )

        # Streaming response
        for chunk in service.chat_stream("Create a page about Python"):
            print(chunk, end="")
        ```
    """

    def __init__(
        self,
        provider: str,
        api_key: str,
        access_token: str,
        glossary: Dict[str, Any],
        use_mcp: Optional[bool] = None
    ):
        """
        Initialize the Telegraph AI service.

        Args:
            provider: AI provider name ("Claude", "OpenAI", "Gemini")
            api_key: API key for the selected provider
            access_token: Telegraph access token
            glossary: Current glossary dictionary
            use_mcp: Force MCP usage (None = auto-detect)
        """
        self.provider = provider
        self.api_key = api_key
        self.access_token = access_token
        self.glossary = glossary
        self.use_mcp = use_mcp if use_mcp is not None else can_use_mcp()

        # Set API key in environment (required by PydanticAI)
        self._set_api_key_env()

        # Build system prompt
        self.system_prompt = self._build_system_prompt()

        # MCP server instance (will be used as context manager)
        self._mcp_server: Optional[MCPServerStdio] = None

        logger.info(f"TelegraphAIService initialized: provider={provider}, use_mcp={self.use_mcp}")

    def _set_api_key_env(self) -> None:
        """Set the appropriate environment variable for the provider."""
        env_var = API_KEY_ENV_VARS.get(self.provider)
        if env_var:
            os.environ[env_var] = self.api_key

    def _build_system_prompt(self) -> str:
        """Build system prompt with glossary context."""
        prompt = f"""You are a helpful assistant that manages a Telegraph glossary.
You have access to tools to create, edit, and manage Telegraph pages.

Current glossary has {len(self.glossary)} terms."""

        if self.glossary:
            terms_list = ", ".join(list(self.glossary.keys())[:20])
            if len(self.glossary) > 20:
                terms_list += f"... and {len(self.glossary) - 20} more"
            prompt += f"\nExisting terms: {terms_list}"

        prompt += """

When the user asks you to create or edit glossary entries:
1. Use the create_page tool for new entries
2. Use the edit_page tool to update existing entries
3. Format content in Markdown
4. Be concise and helpful

Always confirm what action you took after using a tool."""

        return prompt

    def _get_model_name(self) -> str:
        """Get PydanticAI model name for the selected provider."""
        return MODEL_NAMES.get(self.provider, MODEL_NAMES["Claude"])

    def _create_mcp_server(self) -> MCPServerStdio:
        """Create MCP server connection."""
        return MCPServerStdio(
            'npx',
            args=['telegraph-mcp'],
            env={
                **os.environ,
                'TELEGRAPH_ACCESS_TOKEN': self.access_token
            }
        )

    def _create_agent_with_mcp(self, mcp_server: MCPServerStdio) -> Agent:
        """Create PydanticAI agent with MCP toolset."""
        return Agent(
            self._get_model_name(),
            system_prompt=self.system_prompt,
            toolsets=[mcp_server]
        )

    def _create_agent_with_direct_tools(self) -> Agent:
        """Create PydanticAI agent with direct Python tools."""
        from services.direct_telegraph_tools import DirectTelegraphTools

        direct_tools = DirectTelegraphTools(self.access_token)
        agent = Agent(
            self._get_model_name(),
            system_prompt=self.system_prompt,
        )

        # Register tools using tool_plain (no RunContext needed)
        @agent.tool_plain
        def create_page(title: str, content: str, author_name: str = "Telegraph Glossary") -> Dict[str, Any]:
            """Create a new Telegraph page with the given title and content."""
            return direct_tools.call_tool_sync("create_page", {
                "title": title,
                "content": content,
                "author_name": author_name
            })

        @agent.tool_plain
        def edit_page(path: str, title: str, content: str, author_name: str = "Telegraph Glossary") -> Dict[str, Any]:
            """Edit an existing Telegraph page."""
            return direct_tools.call_tool_sync("edit_page", {
                "path": path,
                "title": title,
                "content": content,
                "author_name": author_name
            })

        @agent.tool_plain
        def get_page(path: str) -> Dict[str, Any]:
            """Get the content of an existing Telegraph page."""
            return direct_tools.call_tool_sync("get_page", {"path": path})

        @agent.tool_plain
        def get_page_list(limit: int = 50, offset: int = 0) -> Dict[str, Any]:
            """Get a list of pages in the current Telegraph account."""
            return direct_tools.call_tool_sync("get_page_list", {
                "limit": limit,
                "offset": offset
            })

        @agent.tool_plain
        def get_account_info() -> Dict[str, Any]:
            """Get information about the current Telegraph account."""
            return direct_tools.call_tool_sync("get_account_info", {})

        @agent.tool_plain
        def get_views(path: str, year: Optional[int] = None, month: Optional[int] = None, day: Optional[int] = None) -> Dict[str, Any]:
            """Get the number of views for a Telegraph page."""
            args = {"path": path}
            if year is not None:
                args["year"] = year
            if month is not None:
                args["month"] = month
            if day is not None:
                args["day"] = day
            return direct_tools.call_tool_sync("get_views", args)

        return agent

    def chat(self, prompt: str, message_history: Optional[List[Dict]] = None) -> str:
        """
        Get a non-streaming response from the AI.

        Args:
            prompt: User's message
            message_history: Optional conversation history

        Returns:
            AI response text
        """
        try:
            if self.use_mcp:
                return self._chat_with_mcp(prompt, message_history)
            else:
                return self._chat_with_direct_tools(prompt, message_history)
        except Exception as e:
            logger.error(f"Error in chat: {e}", exc_info=True)
            return f"Error: {str(e)}"

    def _chat_with_mcp(self, prompt: str, message_history: Optional[List[Dict]] = None) -> str:
        """Chat using MCP server."""
        async def async_chat():
            mcp_server = self._create_mcp_server()
            async with mcp_server:
                agent = self._create_agent_with_mcp(mcp_server)
                result = await agent.run(prompt)
                return result.output

        return self._run_async(async_chat())

    def _chat_with_direct_tools(self, prompt: str, message_history: Optional[List[Dict]] = None) -> str:
        """Chat using direct Python tools."""
        agent = self._create_agent_with_direct_tools()
        result = agent.run_sync(prompt)
        return result.output

    def chat_stream(self, prompt: str, message_history: Optional[List[Dict]] = None) -> Generator[str, None, None]:
        """
        Get a streaming response from the AI.

        Args:
            prompt: User's message
            message_history: Optional conversation history

        Yields:
            Text chunks as they arrive
        """
        try:
            if self.use_mcp:
                yield from self._stream_with_mcp(prompt, message_history)
            else:
                yield from self._stream_with_direct_tools(prompt, message_history)
        except Exception as e:
            logger.error(f"Error in chat_stream: {e}", exc_info=True)
            yield f"Error: {str(e)}"

    def _stream_with_mcp(self, prompt: str, message_history: Optional[List[Dict]] = None) -> Generator[str, None, None]:
        """Stream response using MCP server."""
        async def async_stream():
            mcp_server = self._create_mcp_server()
            async with mcp_server:
                agent = self._create_agent_with_mcp(mcp_server)
                async with agent.run_stream(prompt) as result:
                    async for chunk in result.stream_text():
                        yield chunk

        yield from self._run_async_generator(async_stream())

    def _stream_with_direct_tools(self, prompt: str, message_history: Optional[List[Dict]] = None) -> Generator[str, None, None]:
        """Stream response using direct Python tools."""
        async def async_stream():
            agent = self._create_agent_with_direct_tools()
            async with agent.run_stream(prompt) as result:
                async for chunk in result.stream_text():
                    yield chunk

        yield from self._run_async_generator(async_stream())

    def _run_async(self, coro) -> Any:
        """Run an async coroutine synchronously."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    def _run_async_generator(self, async_gen) -> Generator[str, None, None]:
        """
        Convert async generator to sync generator for Streamlit.

        This adapter allows Streamlit (which is synchronous) to consume
        PydanticAI's async streaming responses.
        """
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # Get the async iterator
            ait = async_gen.__aiter__()
            while True:
                try:
                    chunk = loop.run_until_complete(ait.__anext__())
                    yield chunk
                except StopAsyncIteration:
                    break
        except Exception as e:
            logger.error(f"Error in async generator: {e}", exc_info=True)
            yield f"Error during streaming: {str(e)}"
        finally:
            loop.close()

    def get_tools_info(self) -> List[Dict[str, str]]:
        """
        Get information about available tools.

        Returns:
            List of tool info dictionaries with name and description
        """
        if self.use_mcp:
            return [
                {"name": "create_page", "description": "Create a new Telegraph page"},
                {"name": "edit_page", "description": "Edit an existing page"},
                {"name": "get_page", "description": "Get page content"},
                {"name": "get_page_list", "description": "List all pages"},
                {"name": "get_account_info", "description": "Get account info"},
                {"name": "get_views", "description": "Get page views"},
            ]
        else:
            from services.direct_telegraph_tools import TELEGRAPH_TOOLS
            return [{"name": t["name"], "description": t["description"]} for t in TELEGRAPH_TOOLS]
