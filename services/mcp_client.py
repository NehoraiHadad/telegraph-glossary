"""
MCP Client for Telegraph server communication.

This module provides a client for connecting to the telegraph-mcp server
via the Model Context Protocol (MCP) using stdio transport.

The client supports:
- Discovering available tools from the telegraph-mcp server
- Calling tools with arguments
- Both async and synchronous interfaces
- Connection pooling and tool caching for performance

Example:
    ```python
    client = TelegraphMCPClient(access_token="your_token")

    # Get available tools
    tools = client.get_tools_sync()

    # Call a tool
    result = client.call_tool_sync(
        "create_page",
        {"title": "Test", "content": "Hello World"}
    )
    ```
"""

import asyncio
import logging
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from mcp import types
except ImportError:
    raise ImportError(
        "MCP package not found. Please install it with: pip install mcp"
    )

# Configure logging
logger = logging.getLogger(__name__)


class TelegraphMCPClient:
    """
    Client for connecting to telegraph-mcp server via stdio.

    This client manages connections to the telegraph-mcp npm package,
    which provides Telegraph API functionality through the Model Context
    Protocol (MCP).

    Attributes:
        access_token: Telegraph access token for authentication
        session: Current MCP client session (None when not connected)
        _tools_cache: Cached list of available tools to avoid repeated queries
    """

    def __init__(self, access_token: str):
        """
        Initialize the Telegraph MCP client.

        Args:
            access_token: Telegraph access token for API authentication

        Raises:
            ValueError: If access_token is empty or None
        """
        if not access_token:
            raise ValueError("Telegraph access token is required")

        self.access_token = access_token
        self.session: Optional[ClientSession] = None
        self._tools_cache: Optional[List[Dict[str, Any]]] = None

        logger.info("TelegraphMCPClient initialized")

    def _get_server_params(self) -> StdioServerParameters:
        """
        Get server parameters for stdio connection.

        Configures the connection to run the telegraph-mcp server via npx
        with the Telegraph access token passed as an environment variable.

        Returns:
            StdioServerParameters configured for telegraph-mcp connection
        """
        import shutil
        import os

        # Find npx - try common locations
        npx_cmd = shutil.which("npx")
        if not npx_cmd:
            # Try common paths
            for path in ["/usr/bin/npx", "/usr/local/bin/npx", os.path.expanduser("~/.nvm/current/bin/npx")]:
                if os.path.exists(path):
                    npx_cmd = path
                    break

        if not npx_cmd:
            raise RuntimeError("npx not found. Please install Node.js/npm.")

        # Include current PATH in environment
        env = os.environ.copy()
        env["TELEGRAPH_ACCESS_TOKEN"] = self.access_token

        return StdioServerParameters(
            command=npx_cmd,
            args=["telegraph-mcp"],
            env=env
        )

    @asynccontextmanager
    async def _get_session(self):
        """
        Context manager for MCP session.

        Creates a new stdio connection and client session for each operation.
        This ensures clean connections and proper resource cleanup.

        Yields:
            ClientSession: Active MCP client session

        Example:
            ```python
            async with client._get_session() as session:
                tools = await session.list_tools()
            ```
        """
        server_params = self._get_server_params()

        try:
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    logger.debug("MCP session initialized")
                    yield session
        except Exception as e:
            logger.error(f"Error creating MCP session: {e}")
            raise

    async def get_tools(self) -> List[Dict[str, Any]]:
        """
        Get available tools from the MCP server.

        Lists all tools provided by the telegraph-mcp server and caches
        the result for subsequent calls. Each tool includes its name,
        description, and input schema for validation.

        Returns:
            List of tool dictionaries, each containing:
                - name: Tool identifier (e.g., "create_page")
                - description: Human-readable description
                - input_schema: JSON Schema for tool parameters

        Raises:
            Exception: If connection to MCP server fails

        Example:
            ```python
            tools = await client.get_tools()
            for tool in tools:
                print(f"{tool['name']}: {tool['description']}")
            ```
        """
        if self._tools_cache:
            logger.debug("Returning cached tools")
            return self._tools_cache

        try:
            async with self._get_session() as session:
                logger.info("Fetching tools from MCP server")
                tools_response = await session.list_tools()

                self._tools_cache = [
                    {
                        "name": tool.name,
                        "description": tool.description or "",
                        "input_schema": tool.inputSchema or {
                            "type": "object",
                            "properties": {}
                        }
                    }
                    for tool in tools_response.tools
                ]

                logger.info(f"Retrieved {len(self._tools_cache)} tools from MCP server")
                return self._tools_cache

        except Exception as e:
            logger.error(f"Failed to get tools from MCP server: {e}")
            raise RuntimeError(f"Failed to connect to telegraph-mcp server: {e}")

    async def call_tool(
        self,
        name: str,
        arguments: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        Call a tool on the MCP server.

        Executes a specific tool with the provided arguments and returns
        the result. The tool must be one of those listed by get_tools().

        Args:
            name: Name of the tool to call (e.g., "create_page")
            arguments: Dictionary of arguments matching the tool's input schema

        Returns:
            Tool execution result. For most tools this is a string or dict.
            The exact format depends on the specific tool being called.

        Raises:
            Exception: If tool execution fails or tool doesn't exist

        Example:
            ```python
            result = await client.call_tool(
                "create_page",
                {
                    "title": "My Page",
                    "content": "Page content in Markdown",
                    "author_name": "John Doe"
                }
            )
            print(result)  # {"url": "https://telegra.ph/...", ...}
            ```
        """
        if arguments is None:
            arguments = {}

        try:
            async with self._get_session() as session:
                logger.info(f"Calling tool '{name}' with arguments: {arguments}")
                result = await session.call_tool(name, arguments=arguments)

                # Extract content from result
                if result.content and len(result.content) > 0:
                    content = result.content[0]

                    # Handle different content types
                    if isinstance(content, types.TextContent):
                        logger.debug(f"Tool '{name}' returned text content")
                        return content.text
                    elif isinstance(content, types.ImageContent):
                        logger.debug(f"Tool '{name}' returned image content")
                        return {
                            "type": "image",
                            "data": content.data,
                            "mimeType": content.mimeType
                        }
                    elif isinstance(content, types.EmbeddedResource):
                        logger.debug(f"Tool '{name}' returned embedded resource")
                        return {
                            "type": "resource",
                            "uri": content.resource.uri,
                            "mimeType": content.resource.mimeType
                        }

                # Return raw result if content extraction failed
                logger.warning(f"Could not extract content from tool '{name}' result")
                return result

        except Exception as e:
            logger.error(f"Failed to call tool '{name}': {e}")
            raise RuntimeError(f"Tool execution failed for '{name}': {e}")

    def get_tools_sync(self) -> List[Dict[str, Any]]:
        """
        Synchronous wrapper for get_tools().

        Provides a blocking interface to get_tools() for use in
        non-async contexts like Streamlit components.

        Returns:
            List of tool dictionaries (see get_tools() for format)

        Raises:
            Exception: If connection to MCP server fails

        Example:
            ```python
            tools = client.get_tools_sync()
            ```
        """
        return self._run_async(self.get_tools())

    def call_tool_sync(
        self,
        name: str,
        arguments: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        Synchronous wrapper for call_tool().

        Provides a blocking interface to call_tool() for use in
        non-async contexts like Streamlit components.

        Args:
            name: Name of the tool to call
            arguments: Dictionary of arguments for the tool

        Returns:
            Tool execution result (see call_tool() for format)

        Raises:
            Exception: If tool execution fails

        Example:
            ```python
            result = client.call_tool_sync("get_page_list", {"limit": 10})
            ```
        """
        return self._run_async(self.call_tool(name, arguments))

    def _run_async(self, coro) -> Any:
        """
        Run an async coroutine synchronously.

        Handles the complexities of running async code in Streamlit's
        thread environment where there may not be a current event loop.

        Args:
            coro: The coroutine to run

        Returns:
            The result of the coroutine
        """
        try:
            # Try asyncio.run() first (works in most cases)
            return asyncio.run(coro)
        except RuntimeError as e:
            if "no current event loop" in str(e).lower() or "no running event loop" in str(e).lower():
                # Create a new event loop for this thread
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    return loop.run_until_complete(coro)
                finally:
                    loop.close()
                    asyncio.set_event_loop(None)
            elif "already running" in str(e).lower():
                # Event loop is already running (e.g., Jupyter)
                import nest_asyncio
                nest_asyncio.apply()
                return asyncio.run(coro)
            else:
                raise

    def clear_cache(self) -> None:
        """
        Clear the cached tools list.

        Forces the next get_tools() call to fetch fresh data from the
        MCP server. Useful if the server's tool list has changed.
        """
        self._tools_cache = None
        logger.debug("Tools cache cleared")

    def __repr__(self) -> str:
        """String representation of the client."""
        token_preview = f"{self.access_token[:8]}..." if len(self.access_token) > 8 else "***"
        return f"TelegraphMCPClient(token={token_preview}, cached_tools={len(self._tools_cache) if self._tools_cache else 0})"
