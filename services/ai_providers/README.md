# AI Provider Abstraction Layer

This module provides a unified interface for multiple AI providers (Claude, OpenAI) with automatic tool format conversion and response handling.

## Overview

The abstraction layer enables the Telegraph Glossary app to work with different AI providers while maintaining a consistent interface. It handles the conversion of MCP (Model Context Protocol) tool definitions to provider-specific formats and normalizes responses.

## Architecture

```
┌─────────────────┐
│   Application   │
│  (Streamlit UI) │
└────────┬────────┘
         │
         v
┌─────────────────┐
│  AIProviderBase │  (Abstract Interface)
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
    v         v
┌───────┐  ┌────────┐
│Claude │  │OpenAI  │
└───────┘  └────────┘
```

## Files

- **`__init__.py`**: Module exports
- **`base.py`**: Abstract base class defining the provider interface
- **`claude_provider.py`**: Claude (Anthropic) implementation
- **`openai_provider.py`**: OpenAI implementation
- **`example_usage.py`**: Usage examples and patterns
- **`README.md`**: This file

## Key Features

### 1. Unified Interface

All providers implement the same interface:

```python
from services.ai_providers import ClaudeProvider, OpenAIProvider

# Both providers work the same way
provider = ClaudeProvider(api_key="...")
# or
provider = OpenAIProvider(api_key="...")

response = provider.chat(messages, tools=mcp_tools)
```

### 2. Automatic Tool Format Conversion

MCP tools are automatically converted to provider-specific formats:

**MCP Format** (input):
```python
{
    "name": "create_page",
    "description": "Create a new Telegraph page",
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string"}
        }
    }
}
```

**Claude Format** (no conversion needed):
```python
# Same as MCP - Claude uses input_schema natively!
```

**OpenAI Format** (auto-converted):
```python
{
    "type": "function",
    "function": {
        "name": "create_page",
        "description": "Create a new Telegraph page",
        "parameters": {  # Note: parameters, not input_schema
            "type": "object",
            "properties": {
                "title": {"type": "string"}
            }
        }
    }
}
```

### 3. Normalized Tool Call Extraction

Both providers return tool calls in a consistent format:

```python
tool_calls = provider.extract_tool_calls(response)
# Always returns:
[
    {
        "id": "call_id",
        "name": "tool_name",
        "input": {"param": "value"}
    }
]
```

### 4. Streaming Support

All providers support streaming responses:

```python
for chunk in provider.chat_stream(messages, tools):
    print(chunk, end="", flush=True)
```

## Usage Examples

### Basic Chat

```python
from services.ai_providers import ClaudeProvider

provider = ClaudeProvider(api_key="sk-ant-...")

messages = [
    {"role": "user", "content": "Hello!"}
]

response = provider.chat(messages)
print(response["content"][0]["text"])
```

### Chat with Tools

```python
from services.ai_providers import OpenAIProvider

provider = OpenAIProvider(api_key="sk-...")

# MCP tools from telegraph-mcp server
mcp_tools = [
    {
        "name": "create_page",
        "description": "Create a Telegraph page",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "content": {"type": "array"}
            },
            "required": ["title", "content"]
        }
    }
]

messages = [
    {
        "role": "user",
        "content": "Create a page titled 'Hello' with content 'World'"
    }
]

# Providers handle tool conversion automatically
response = provider.chat(messages, tools=mcp_tools)

# Check if AI wants to use tools
tool_calls = provider.extract_tool_calls(response)
if tool_calls:
    print(f"AI wants to call: {tool_calls[0]['name']}")
    print(f"With input: {tool_calls[0]['input']}")
```

### Tool Execution Loop

```python
from services.ai_providers import ClaudeProvider

provider = ClaudeProvider(api_key="sk-ant-...")

messages = [
    {"role": "user", "content": "Create a page called 'Test'"}
]

# 1. Initial AI response
response = provider.chat(messages, tools=mcp_tools)

# 2. Add assistant message to conversation
messages.append({
    "role": "assistant",
    "content": response["content"]
})

# 3. Extract and execute tool calls
tool_calls = provider.extract_tool_calls(response)

if tool_calls:
    for tool_call in tool_calls:
        # Execute via MCP client (not shown)
        result = mcp_client.call_tool(
            tool_call["name"],
            tool_call["input"]
        )

        # Format result for conversation
        tool_result = provider.format_tool_result(
            tool_call["id"],
            result
        )
        messages.append(tool_result)

    # 4. Get final AI response
    final_response = provider.chat(messages)
    print(final_response["content"][0]["text"])
```

### Streaming Response

```python
from services.ai_providers import ClaudeProvider

provider = ClaudeProvider(api_key="sk-ant-...")

messages = [
    {"role": "user", "content": "Write a short poem"}
]

print("AI: ", end="")
for chunk in provider.chat_stream(messages):
    print(chunk, end="", flush=True)
print()
```

## Provider Differences

### Claude (Anthropic)

- **Model**: `claude-sonnet-4-20250514`
- **Tool Format**: Uses `input_schema` (MCP native)
- **Tool Calls**: `stop_reason: "tool_use"`, content blocks with `type: "tool_use"`
- **Tool Results**: User role with `tool_result` blocks
- **Streaming**: Full streaming support with `text_stream`

### OpenAI

- **Model**: `gpt-4o`
- **Tool Format**: Uses `type: "function"` with `parameters` (converted from `input_schema`)
- **Tool Calls**: `message.tool_calls` array
- **Tool Results**: `role: "tool"` messages
- **Streaming**: Chunk-based streaming with `delta.content`

## Integration with MCP Client

The AI providers work seamlessly with the MCP client:

```python
from services.mcp_client import TelegraphMCPClient
from services.ai_providers import ClaudeProvider

# Initialize
mcp_client = TelegraphMCPClient()
ai_provider = ClaudeProvider(api_key="...")

# Get tools from MCP server
mcp_tools = mcp_client.list_tools()

# Use with AI provider
response = ai_provider.chat(messages, tools=mcp_tools)

# Execute tool calls via MCP
tool_calls = ai_provider.extract_tool_calls(response)
if tool_calls:
    for call in tool_calls:
        result = mcp_client.call_tool(call["name"], call["input"])
        # Continue conversation...
```

## Error Handling

All providers raise appropriate exceptions:

```python
try:
    response = provider.chat(messages, tools=mcp_tools)
except anthropic.APIError as e:
    print(f"API Error: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

## Type Safety

The module uses Python type hints throughout:

```python
from typing import List, Dict, Any, Optional, Generator

def chat(
    self,
    messages: List[Dict[str, Any]],
    tools: Optional[List[Dict[str, Any]]] = None,
    stream: bool = False
) -> Dict[str, Any]:
    ...
```

## Dependencies

Required packages (in `requirements.txt`):

```
anthropic>=0.30.0
openai>=1.30.0
```

## Testing

To test the providers:

```python
# Test imports
from services.ai_providers import AIProviderBase, ClaudeProvider, OpenAIProvider

# Test tool conversion
provider = ClaudeProvider(api_key="test")
converted = provider.convert_tools_format(mcp_tools)
print(f"Converted {len(converted)} tools")

# Test basic functionality (requires valid API key)
response = provider.chat([{"role": "user", "content": "Hello"}])
print(response)
```

## Future Extensions

To add a new provider:

1. Create `services/ai_providers/new_provider.py`
2. Implement `AIProviderBase` abstract methods
3. Add to `__init__.py` exports
4. Update this README

Example structure:

```python
from .base import AIProviderBase

class NewProvider(AIProviderBase):
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.model = "new-model-name"

    def chat(self, messages, tools=None, stream=False):
        # Implementation
        pass

    # Implement other abstract methods...
```

## Best Practices

1. **Always handle errors**: Wrap API calls in try-except blocks
2. **Validate inputs**: Check message format before sending
3. **Monitor token usage**: Track costs via response usage data
4. **Use streaming for UX**: Stream responses in interactive interfaces
5. **Normalize data**: Use the standard format for tool calls
6. **Security**: Never log API keys or sensitive data

## Related Documentation

- [MCP Client Documentation](../mcp_client.py)
- [Implementation Plan](../../IMPLEMENTATION_PLAN.md)
- [MCP Integration Research](../../MCP_INTEGRATION_RESEARCH_RESULTS.md)
