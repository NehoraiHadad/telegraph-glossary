"""Gemini (Google) AI provider implementation."""

from typing import List, Dict, Any, Optional, Generator
from .base import AIProviderBase

# Use google-genai package
from google import genai
from google.genai import types


class GeminiProvider(AIProviderBase):
    """Google Gemini provider.

    This provider implements the AIProviderBase interface for Google's Gemini models,
    handling tool/function calling with proper format conversion.

    Note: Gemini uses 'model' role instead of 'assistant' and FunctionDeclaration
    format for tools.
    """

    def __init__(self, api_key: str):
        """Initialize Gemini provider.

        Args:
            api_key: Google AI API key for authentication
        """
        super().__init__(api_key)
        self.client = genai.Client(api_key=api_key)
        self.model = "gemini-2.0-flash-exp"  # Latest flash model

    def convert_tools_format(self, mcp_tools: List[Dict[str, Any]]) -> List[types.Tool]:
        """Convert MCP tools to Gemini function declarations.

        Gemini uses FunctionDeclaration objects with parameters schema.

        Args:
            mcp_tools: List of tools in MCP format with name, description, and input_schema

        Returns:
            List containing a single Tool object with all function declarations
        """
        function_declarations = []
        for tool in mcp_tools:
            # Gemini format uses FunctionDeclaration
            func_decl = types.FunctionDeclaration(
                name=tool["name"],
                description=tool.get("description", ""),
                parameters=tool.get("input_schema", {"type": "object", "properties": {}})
            )
            function_declarations.append(func_decl)

        # Gemini wraps all function declarations in a single Tool object
        return [types.Tool(function_declarations=function_declarations)]

    def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        stream: bool = False
    ) -> Dict[str, Any]:
        """Send chat message to Gemini.

        Args:
            messages: List of message dictionaries with 'role' and 'content'
            tools: Optional list of tools in MCP format
            stream: Whether to stream response (ignored, use chat_stream instead)

        Returns:
            Dictionary with standardized response format:
            {
                "content": [{"type": "text", "text": "..."}],
                "function_calls": [{"name": "...", "args": {...}}],
                "usage": {"input_tokens": 0, "output_tokens": 0}
            }
        """
        # Convert messages to Gemini Content format
        contents = self._convert_messages(messages)

        config = types.GenerateContentConfig(
            temperature=0.7,
        )

        if tools:
            config = types.GenerateContentConfig(
                temperature=0.7,
                tools=self.convert_tools_format(tools),
            )

        response = self.client.models.generate_content(
            model=self.model,
            contents=contents,
            config=config
        )

        return self._parse_response(response)

    def chat_stream(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> Generator[str, None, None]:
        """Stream chat response from Gemini.

        Args:
            messages: List of message dictionaries with 'role' and 'content'
            tools: Optional list of tools in MCP format

        Yields:
            Text chunks as they become available
        """
        contents = self._convert_messages(messages)

        config = types.GenerateContentConfig(
            temperature=0.7,
        )

        if tools:
            config = types.GenerateContentConfig(
                temperature=0.7,
                tools=self.convert_tools_format(tools),
            )

        for chunk in self.client.models.generate_content_stream(
            model=self.model,
            contents=contents,
            config=config
        ):
            if chunk.text:
                yield chunk.text

    def extract_tool_calls(self, response: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """Extract function calls from Gemini response.

        Args:
            response: Parsed response dictionary from _parse_response

        Returns:
            List of tool calls in normalized format:
            [
                {
                    "id": "call_0",  # Generated ID (Gemini doesn't provide IDs)
                    "name": "tool_name",
                    "input": {"param": "value"}
                }
            ]
            Returns None if no tool calls were made.
        """
        function_calls = response.get("function_calls", [])
        if not function_calls:
            return None

        return [
            {
                "id": f"call_{i}",  # Gemini doesn't provide IDs, so we generate them
                "name": fc["name"],
                "input": fc["args"]  # Map 'args' to 'input' for consistency
            }
            for i, fc in enumerate(function_calls)
        ]

    def format_tool_result(self, tool_call_id: str, tool_name: str, result: str) -> Dict[str, Any]:
        """Format tool result for Gemini conversation.

        Gemini uses FunctionResponse format wrapped in a user message.

        Args:
            tool_call_id: The ID of the tool call (generated by us, not used by Gemini)
            tool_name: The name of the tool that was called
            result: The result string from executing the tool

        Returns:
            Message dictionary in Gemini format with FunctionResponse
        """
        return {
            "role": "user",  # Gemini expects function results as user messages
            "parts": [
                types.FunctionResponse(
                    name=tool_name,
                    response={"result": result}
                )
            ]
        }

    def _convert_messages(self, messages: List[Dict[str, Any]]) -> List[types.Content]:
        """Convert standard messages to Gemini Content format.

        Handles role mapping (assistant -> model) and various content types.

        Args:
            messages: List of messages with 'role' and 'content' keys

        Returns:
            List of Gemini Content objects
        """
        contents = []
        for msg in messages:
            role = msg["role"]
            # Gemini uses "user" and "model" roles (not "assistant")
            if role == "assistant":
                role = "model"

            content = msg.get("content", "")

            if isinstance(content, str):
                # Simple text content - use Part(text=...) instead of Part.from_text()
                contents.append(types.Content(
                    role=role,
                    parts=[types.Part(text=content)]
                ))
            elif isinstance(content, list):
                # Structured content (tool results, multiple parts, etc.)
                parts = []
                for item in content:
                    if isinstance(item, dict):
                        if item.get("type") == "text":
                            parts.append(types.Part(text=item.get("text", "")))
                        elif item.get("type") == "function_response":
                            parts.append(types.FunctionResponse(
                                name=item.get("name", ""),
                                response=item.get("response", {})
                            ))
                if parts:
                    contents.append(types.Content(role=role, parts=parts))

        return contents

    def _parse_response(self, response) -> Dict[str, Any]:
        """Parse Gemini response to standard format.

        Extracts text content, function calls, and usage metadata.

        Args:
            response: Raw Gemini API response object

        Returns:
            Standardized response dictionary
        """
        result = {
            "content": [],
            "function_calls": [],
            "usage": {}
        }

        # Extract text content
        if response.text:
            result["content"].append({
                "type": "text",
                "text": response.text
            })

        # Extract function calls from candidates
        if response.candidates:
            for candidate in response.candidates:
                if candidate.content and candidate.content.parts:
                    for part in candidate.content.parts:
                        # Check if part has a function_call attribute
                        if hasattr(part, "function_call") and part.function_call:
                            result["function_calls"].append({
                                "name": part.function_call.name,
                                "args": dict(part.function_call.args) if part.function_call.args else {}
                            })

        # Extract usage metadata if available
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            result["usage"] = {
                "input_tokens": getattr(response.usage_metadata, "prompt_token_count", 0),
                "output_tokens": getattr(response.usage_metadata, "candidates_token_count", 0)
            }

        return result
