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
import threading
import queue
from typing import Generator, Dict, Any, Optional, List
from dataclasses import dataclass

from pydantic_ai import Agent
from pydantic_ai.mcp import MCPServerStdio
from pydantic_ai import (
    AgentStreamEvent,
    AgentRunResultEvent,
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    PartDeltaEvent,
    PartStartEvent,
    TextPartDelta,
)
from enum import Enum

logger = logging.getLogger(__name__)

# Model name mappings for PydanticAI (December 2025 - latest models)
MODEL_NAMES = {
    "Claude": "anthropic:claude-opus-4-5-20251101",  # Opus 4.5 - smartest Claude
    "OpenAI": "openai:gpt-5.1",  # GPT-5.1 - released Nov 2025
    "Gemini": "google-gla:gemini-2.5-flash",  # Has free tier (gemini-3-pro requires paid plan)
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


class EventType(str, Enum):
    """Types of streaming events for UI consumption."""
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    TEXT = "text"
    TEXT_DELTA = "text_delta"
    DONE = "done"
    ERROR = "error"


@dataclass
class StreamEvent:
    """
    Structured event for UI consumption during streaming.

    Attributes:
        type: The type of event (tool_call, tool_result, text, etc.)
        data: Event-specific data
    """
    type: EventType
    data: Dict[str, Any]


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

    def chat_stream_with_events(
        self, prompt: str, message_history: Optional[List[Dict]] = None
    ) -> Generator[StreamEvent, None, None]:
        """
        Stream response with full event visibility including tool calls.

        This method yields structured StreamEvent objects that include:
        - Tool calls (when the AI decides to use a tool)
        - Tool results (when a tool returns)
        - Text deltas (streaming text chunks)
        - Done signal (when complete)

        Args:
            prompt: User's message
            message_history: Optional conversation history

        Yields:
            StreamEvent objects for UI consumption
        """
        try:
            if self.use_mcp:
                yield from self._stream_events_with_mcp(prompt)
            else:
                yield from self._stream_events_with_direct_tools(prompt)
        except Exception as e:
            logger.error(f"Error in chat_stream_with_events: {e}", exc_info=True)
            yield StreamEvent(type=EventType.ERROR, data={"message": str(e)})

    def _stream_events_with_mcp(self, prompt: str) -> Generator[StreamEvent, None, None]:
        """Stream events using MCP server."""
        yield from self._run_event_streaming_in_thread(prompt, use_mcp=True)

    def _stream_events_with_direct_tools(self, prompt: str) -> Generator[StreamEvent, None, None]:
        """Stream events using direct Python tools."""
        yield from self._run_event_streaming_in_thread(prompt, use_mcp=False)

    def _run_event_streaming_in_thread(self, prompt: str, use_mcp: bool) -> Generator[StreamEvent, None, None]:
        """
        Run async event streaming in a separate thread.

        Uses a thread-safe queue to pass StreamEvent objects from async context to sync generator.
        """
        event_queue: queue.Queue = queue.Queue()
        error_holder: List[Optional[Exception]] = [None]

        def run_async():
            """Run the async event streaming in a new event loop."""
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self._async_events_to_queue(prompt, event_queue, use_mcp))
            except Exception as e:
                error_holder[0] = e
                event_queue.put(None)  # Signal end
            finally:
                loop.close()

        # Start async streaming in a separate thread
        thread = threading.Thread(target=run_async, daemon=True)
        thread.start()

        # Yield events as they arrive
        while True:
            try:
                event = event_queue.get(timeout=120)  # 2 minute timeout for tool execution
                if event is None:  # End signal
                    break
                yield event
            except queue.Empty:
                yield StreamEvent(type=EventType.ERROR, data={"message": "Streaming timeout"})
                break

        # Wait for thread to finish
        thread.join(timeout=5)

        # Check for errors
        if error_holder[0]:
            yield StreamEvent(type=EventType.ERROR, data={"message": str(error_holder[0])})

    async def _async_events_to_queue(self, prompt: str, event_queue: queue.Queue, use_mcp: bool) -> None:
        """Async method that processes events and puts StreamEvents in queue."""
        full_text = ""

        async def event_handler(ctx, event_stream):
            """Handle tool events from the agent stream (not text - that's handled separately)."""
            async for event in event_stream:
                # Only process tool-related events, skip text (handled by stream_text)
                if isinstance(event, (FunctionToolCallEvent, FunctionToolResultEvent)):
                    stream_event = self._process_agent_event(event, "")
                    if stream_event:
                        event_queue.put(stream_event)

        try:
            if use_mcp:
                mcp_server = self._create_mcp_server()
                async with mcp_server:
                    agent = self._create_agent_with_mcp(mcp_server)
                    async with agent.run_stream(prompt, event_stream_handler=event_handler) as result:
                        async for chunk in result.stream_text():
                            full_text += chunk
                            event_queue.put(StreamEvent(
                                type=EventType.TEXT_DELTA,
                                data={"delta": chunk}
                            ))
            else:
                agent = self._create_agent_with_direct_tools()
                async with agent.run_stream(prompt, event_stream_handler=event_handler) as result:
                    async for chunk in result.stream_text():
                        full_text += chunk
                        event_queue.put(StreamEvent(
                            type=EventType.TEXT_DELTA,
                            data={"delta": chunk}
                        ))

            # Send final done event
            event_queue.put(StreamEvent(type=EventType.DONE, data={"text": full_text}))

        except Exception as e:
            logger.error(f"Error in async events: {e}", exc_info=True)
            event_queue.put(StreamEvent(type=EventType.ERROR, data={"message": str(e)}))

        finally:
            event_queue.put(None)  # Signal end of stream

    def _process_agent_event(self, event: AgentStreamEvent, current_text: str) -> Optional[StreamEvent]:
        """Convert PydanticAI event to StreamEvent for UI consumption."""
        if isinstance(event, FunctionToolCallEvent):
            # Tool is being called
            return StreamEvent(
                type=EventType.TOOL_CALL,
                data={
                    "tool_name": event.part.tool_name,
                    "args": event.part.args,
                    "tool_call_id": event.part.tool_call_id,
                }
            )
        elif isinstance(event, FunctionToolResultEvent):
            # Tool returned result
            result_content = event.result.content
            if isinstance(result_content, dict):
                result_str = str(result_content)
            else:
                result_str = str(result_content)
            return StreamEvent(
                type=EventType.TOOL_RESULT,
                data={
                    "tool_call_id": event.tool_call_id,
                    "result": result_str[:500],  # Truncate long results
                    "success": not hasattr(event.result, 'error') or not event.result.error,
                }
            )
        elif isinstance(event, PartDeltaEvent):
            if isinstance(event.delta, TextPartDelta):
                # Streaming text chunk
                return StreamEvent(
                    type=EventType.TEXT_DELTA,
                    data={"delta": event.delta.content_delta}
                )
        elif isinstance(event, AgentRunResultEvent):
            # Final result (handled in _async_events_to_queue)
            return StreamEvent(
                type=EventType.TEXT,
                data={"text": str(event.result.output)}
            )

        return None

    def _stream_with_mcp(self, prompt: str, message_history: Optional[List[Dict]] = None) -> Generator[str, None, None]:
        """Stream response using MCP server."""
        yield from self._run_streaming_in_thread(prompt, use_mcp=True)

    def _stream_with_direct_tools(self, prompt: str, message_history: Optional[List[Dict]] = None) -> Generator[str, None, None]:
        """Stream response using direct Python tools."""
        yield from self._run_streaming_in_thread(prompt, use_mcp=False)

    def _run_streaming_in_thread(self, prompt: str, use_mcp: bool) -> Generator[str, None, None]:
        """
        Run async streaming in a separate thread to avoid event loop issues.

        Uses a thread-safe queue to pass chunks from async context to sync generator.
        """
        chunk_queue: queue.Queue = queue.Queue()
        error_holder: List[Optional[Exception]] = [None]

        def run_async():
            """Run the async streaming in a new event loop in this thread."""
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self._async_stream_to_queue(prompt, chunk_queue, use_mcp))
            except Exception as e:
                error_holder[0] = e
                chunk_queue.put(None)  # Signal end
            finally:
                loop.close()

        # Start async streaming in a separate thread
        thread = threading.Thread(target=run_async, daemon=True)
        thread.start()

        # Yield chunks as they arrive
        while True:
            try:
                chunk = chunk_queue.get(timeout=60)  # 60 second timeout
                if chunk is None:  # End signal
                    break
                yield chunk
            except queue.Empty:
                yield "Error: Streaming timeout"
                break

        # Wait for thread to finish
        thread.join(timeout=5)

        # Check for errors
        if error_holder[0]:
            yield f"Error: {str(error_holder[0])}"

    async def _async_stream_to_queue(self, prompt: str, chunk_queue: queue.Queue, use_mcp: bool) -> None:
        """Async method that streams response and puts chunks in queue."""
        try:
            if use_mcp:
                mcp_server = self._create_mcp_server()
                async with mcp_server:
                    agent = self._create_agent_with_mcp(mcp_server)
                    async with agent.run_stream(prompt) as result:
                        async for chunk in result.stream_text():
                            chunk_queue.put(chunk)
            else:
                agent = self._create_agent_with_direct_tools()
                async with agent.run_stream(prompt) as result:
                    async for chunk in result.stream_text():
                        chunk_queue.put(chunk)
        finally:
            chunk_queue.put(None)  # Signal end of stream

    def _run_async(self, coro) -> Any:
        """Run an async coroutine synchronously."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
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
