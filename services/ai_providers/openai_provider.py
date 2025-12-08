"""OpenAI Provider implementation.

OpenAI implementation using the Chat Completions API with function calling.
Requires conversion from MCP's input_schema to OpenAI's parameters format.
"""

from typing import List, Dict, Any, Optional, Generator
import openai

from .base import AIProviderBase


class OpenAIProvider(AIProviderBase):
    """OpenAI provider implementation.

    Uses OpenAI's Chat Completions API with function calling.
    OpenAI uses 'parameters' instead of 'input_schema' and wraps tools in a function object.

    Attributes:
        client: OpenAI API client instance
        model: OpenAI model identifier (gpt-4o)
    """

    def __init__(self, api_key: str):
        """Initialize OpenAI provider.

        Args:
            api_key: OpenAI API key
        """
        super().__init__(api_key)
        self.client = openai.OpenAI(api_key=api_key)
        self.model = "gpt-4o"

    def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        stream: bool = False
    ) -> Dict[str, Any]:
        """Send a chat message to OpenAI.

        Args:
            messages: List of messages in OpenAI format
                [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
            tools: Optional list of tools in MCP format (will be converted)
            stream: If True, returns a streaming response object

        Returns:
            OpenAI API response with:
                - id: Completion ID
                - choices: List with message and finish_reason
                - usage: Token usage information
        """
        # Convert tools if provided
        converted_tools = None
        if tools:
            converted_tools = self.convert_tools_format(tools)

        # Prepare API call parameters
        params = {
            "model": self.model,
            "messages": messages
        }

        if converted_tools:
            params["tools"] = converted_tools

        # Make API call
        if stream:
            return self.client.chat.completions.create(stream=True, **params)
        else:
            response = self.client.chat.completions.create(**params)
            return self._response_to_dict(response)

    def chat_stream(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> Generator[str, None, None]:
        """Stream chat response from OpenAI.

        Args:
            messages: List of messages in OpenAI format
            tools: Optional list of tools in MCP format (will be converted)

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
            "messages": messages
        }

        if converted_tools:
            params["tools"] = converted_tools

        # Stream the response
        stream = self.client.chat.completions.create(stream=True, **params)
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def convert_tools_format(self, mcp_tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert MCP tools to OpenAI function calling format.

        MCP format:
        {
            "name": "tool_name",
            "description": "Tool description",
            "input_schema": {
                "type": "object",
                "properties": {...},
                "required": [...]
            }
        }

        OpenAI format:
        {
            "type": "function",
            "function": {
                "name": "tool_name",
                "description": "Tool description",
                "parameters": {
                    "type": "object",
                    "properties": {...},
                    "required": [...]
                }
            }
        }

        Args:
            mcp_tools: List of tools in MCP format

        Returns:
            List of tools in OpenAI format
        """
        openai_tools = []

        for tool in mcp_tools:
            openai_tool = {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get("input_schema", {
                        "type": "object",
                        "properties": {}
                    })
                }
            }
            openai_tools.append(openai_tool)

        return openai_tools

    def extract_tool_calls(self, response: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """Extract tool calls from OpenAI's response.

        OpenAI returns tool calls in the message.tool_calls array.

        Tool call structure:
        {
            "id": "call_abc123",
            "type": "function",
            "function": {
                "name": "get_weather",
                "arguments": "{\"location\": \"San Francisco\"}"  # JSON string!
            }
        }

        Args:
            response: OpenAI API response dictionary

        Returns:
            Normalized list of tool calls or None
        """
        choices = response.get("choices", [])
        if not choices:
            return None

        message = choices[0].get("message", {})
        tool_calls = message.get("tool_calls")

        if not tool_calls:
            return None

        # Normalize to our standard format
        normalized_calls = []
        for call in tool_calls:
            # Parse the JSON arguments string
            import json
            arguments = call["function"]["arguments"]
            try:
                input_dict = json.loads(arguments) if isinstance(arguments, str) else arguments
            except json.JSONDecodeError:
                input_dict = {}

            normalized_calls.append({
                "id": call["id"],
                "name": call["function"]["name"],
                "input": input_dict
            })

        return normalized_calls

    def format_tool_result(self, tool_call_id: str, result: str) -> Dict[str, Any]:
        """Format tool result for OpenAI.

        OpenAI expects tool results as messages with role "tool".

        Format:
        {
            "role": "tool",
            "tool_call_id": "call_abc123",
            "content": "result string"
        }

        Args:
            tool_call_id: The ID from the tool call
            result: The tool execution result as a string

        Returns:
            Message dictionary with tool result
        """
        return {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": result
        }

    def _response_to_dict(self, response: openai.types.chat.ChatCompletion) -> Dict[str, Any]:
        """Convert OpenAI ChatCompletion object to dictionary.

        Args:
            response: OpenAI ChatCompletion object

        Returns:
            Dictionary representation of the response
        """
        result = {
            "id": response.id,
            "object": response.object,
            "created": response.created,
            "model": response.model,
            "choices": [],
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }
        }

        # Convert choices
        for choice in response.choices:
            choice_dict = {
                "index": choice.index,
                "message": {
                    "role": choice.message.role,
                    "content": choice.message.content
                },
                "finish_reason": choice.finish_reason
            }

            # Include tool calls if present
            if choice.message.tool_calls:
                choice_dict["message"]["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    }
                    for tc in choice.message.tool_calls
                ]

            result["choices"].append(choice_dict)

        return result
