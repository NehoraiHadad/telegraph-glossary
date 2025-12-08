"""Claude AI Provider implementation.

Anthropic Claude implementation using the Messages API with native tool use support.
Claude's tool format is compatible with MCP's input_schema structure.
"""

from typing import List, Dict, Any, Optional, Generator
import anthropic

from .base import AIProviderBase


class ClaudeProvider(AIProviderBase):
    """Claude AI provider implementation.

    Uses Anthropic's Messages API with native tool calling support.
    Claude uses `input_schema` which matches MCP format directly.

    Attributes:
        client: Anthropic API client instance
        model: Claude model identifier (claude-sonnet-4-20250514)
    """

    def __init__(self, api_key: str):
        """Initialize Claude provider.

        Args:
            api_key: Anthropic API key
        """
        super().__init__(api_key)
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = "claude-sonnet-4-20250514"

    def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        stream: bool = False
    ) -> Dict[str, Any]:
        """Send a chat message to Claude.

        Args:
            messages: List of messages in Claude format
                [{"role": "user", "content": "..."}, {"role": "assistant", "content": [...]}]
            tools: Optional list of tools in MCP format
            stream: If True, returns a streaming response object

        Returns:
            Claude API response with:
                - id: Message ID
                - content: List of content blocks (text and tool_use)
                - stop_reason: "end_turn" or "tool_use"
                - usage: Token usage information
        """
        # Convert tools if provided
        converted_tools = None
        if tools:
            converted_tools = self.convert_tools_format(tools)

        # Prepare API call parameters
        params = {
            "model": self.model,
            "messages": messages,
            "max_tokens": 4096
        }

        if converted_tools:
            params["tools"] = converted_tools

        # Make API call
        if stream:
            return self.client.messages.stream(**params)
        else:
            response = self.client.messages.create(**params)
            return self._response_to_dict(response)

    def chat_stream(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> Generator[str, None, None]:
        """Stream chat response from Claude.

        Args:
            messages: List of messages in Claude format
            tools: Optional list of tools in MCP format

        Yields:
            Text content as it becomes available
        """
        # Convert tools if provided
        converted_tools = None
        if tools:
            converted_tools = self.convert_tools_format(tools)

        # Prepare API call parameters
        params = {
            "model": self.model,
            "messages": messages,
            "max_tokens": 4096
        }

        if converted_tools:
            params["tools"] = converted_tools

        # Stream the response
        with self.client.messages.stream(**params) as stream:
            for text in stream.text_stream:
                yield text

    def convert_tools_format(self, mcp_tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert MCP tools to Claude format.

        Claude's tool format is already compatible with MCP!
        Both use the same structure with `input_schema`.

        MCP/Claude format:
        {
            "name": "tool_name",
            "description": "Tool description",
            "input_schema": {
                "type": "object",
                "properties": {...},
                "required": [...]
            }
        }

        Args:
            mcp_tools: List of tools in MCP format

        Returns:
            List of tools in Claude format (same as input)
        """
        # Claude format is identical to MCP format - no conversion needed!
        return mcp_tools

    def extract_tool_calls(self, response: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """Extract tool calls from Claude's response.

        Claude returns tool use blocks in the content array when stop_reason is "tool_use".

        Content block structure:
        {
            "type": "tool_use",
            "id": "toolu_01A09q90qw90lq917835lq9",
            "name": "get_weather",
            "input": {"location": "San Francisco, CA"}
        }

        Args:
            response: Claude API response dictionary

        Returns:
            Normalized list of tool calls or None
        """
        if response.get("stop_reason") != "tool_use":
            return None

        content = response.get("content", [])
        tool_calls = []

        for block in content:
            if block.get("type") == "tool_use":
                tool_calls.append({
                    "id": block["id"],
                    "name": block["name"],
                    "input": block["input"]
                })

        return tool_calls if tool_calls else None

    def format_tool_result(self, tool_call_id: str, result: str) -> Dict[str, Any]:
        """Format tool result for Claude.

        Claude expects tool results in the user role with tool_result blocks.

        Format:
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "toolu_01A09q90qw90lq917835lq9",
                    "content": "result string"
                }
            ]
        }

        Args:
            tool_call_id: The ID from the tool_use block
            result: The tool execution result as a string

        Returns:
            Message dictionary with tool result
        """
        return {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": tool_call_id,
                    "content": result
                }
            ]
        }

    def _response_to_dict(self, response: anthropic.types.Message) -> Dict[str, Any]:
        """Convert Anthropic Message object to dictionary.

        Args:
            response: Anthropic Message object

        Returns:
            Dictionary representation of the response
        """
        return {
            "id": response.id,
            "type": response.type,
            "role": response.role,
            "content": [self._content_block_to_dict(block) for block in response.content],
            "model": response.model,
            "stop_reason": response.stop_reason,
            "stop_sequence": response.stop_sequence,
            "usage": {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens
            }
        }

    def _content_block_to_dict(self, block: Any) -> Dict[str, Any]:
        """Convert content block to dictionary.

        Args:
            block: Content block object (TextBlock or ToolUseBlock)

        Returns:
            Dictionary representation
        """
        if hasattr(block, "type"):
            if block.type == "text":
                return {
                    "type": "text",
                    "text": block.text
                }
            elif block.type == "tool_use":
                return {
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": block.input
                }
        return {"type": "unknown"}
