"""Abstract base class for AI providers.

Defines the common interface that all AI providers must implement,
enabling provider-agnostic tool calling and chat functionality.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Generator


class AIProviderBase(ABC):
    """Abstract base class for AI provider implementations.

    This class defines the interface that all AI providers (Claude, OpenAI, etc.)
    must implement to work with the MCP integration layer.

    Attributes:
        api_key: The API key for authenticating with the provider's API
        model: The model identifier to use for chat completions
    """

    def __init__(self, api_key: str):
        """Initialize the AI provider with an API key.

        Args:
            api_key: The API key for the provider's API
        """
        self.api_key = api_key
        self.model: str = ""  # Subclasses should set this

    @abstractmethod
    def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        stream: bool = False
    ) -> Dict[str, Any]:
        """Send a chat message and get a response.

        Args:
            messages: List of message dictionaries in provider format
            tools: Optional list of tools in MCP format (will be converted)
            stream: Whether to stream the response (if True, returns partial responses)

        Returns:
            Dict containing the provider's response with tool calls if any
        """
        pass

    @abstractmethod
    def chat_stream(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> Generator[str, None, None]:
        """Stream chat response token by token.

        Args:
            messages: List of message dictionaries in provider format
            tools: Optional list of tools in MCP format (will be converted)

        Yields:
            Text chunks as they become available
        """
        pass

    @abstractmethod
    def convert_tools_format(self, mcp_tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert MCP tool definitions to provider-specific format.

        MCP tools use the format:
        {
            "name": "tool_name",
            "description": "...",
            "input_schema": {"type": "object", "properties": {...}}
        }

        Args:
            mcp_tools: List of tools in MCP format

        Returns:
            List of tools in provider-specific format
        """
        pass

    @abstractmethod
    def extract_tool_calls(self, response: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """Extract tool calls from the provider's response.

        Returns a normalized format regardless of provider:
        [
            {
                "id": "call_id",
                "name": "tool_name",
                "input": {"param": "value"}
            }
        ]

        Args:
            response: The raw response from the provider's API

        Returns:
            List of tool calls in normalized format, or None if no tools were called
        """
        pass

    @abstractmethod
    def format_tool_result(self, tool_call_id: str, result: str) -> Dict[str, Any]:
        """Format a tool execution result for inclusion in conversation.

        Args:
            tool_call_id: The ID of the tool call this is a result for
            result: The result string from executing the tool

        Returns:
            A message dictionary in provider format containing the tool result
        """
        pass

    def get_model_name(self) -> str:
        """Get the model identifier being used.

        Returns:
            The model name/identifier string
        """
        return self.model
