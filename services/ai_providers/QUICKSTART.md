# AI Provider Abstraction Layer - Quick Start

## Installation

```bash
pip install anthropic>=0.30.0 openai>=1.30.0
```

## Basic Usage

### 1. Simple Chat (Claude)

```python
from services.ai_providers import ClaudeProvider

provider = ClaudeProvider(api_key="sk-ant-api03-...")

messages = [
    {"role": "user", "content": "Hello! How are you?"}
]

response = provider.chat(messages)
print(response["content"][0]["text"])
```

### 2. Simple Chat (OpenAI)

```python
from services.ai_providers import OpenAIProvider

provider = OpenAIProvider(api_key="sk-...")

messages = [
    {"role": "user", "content": "Hello! How are you?"}
]

response = provider.chat(messages)
print(response["choices"][0]["message"]["content"])
```

### 3. Chat with MCP Tools

```python
from services.ai_providers import ClaudeProvider

provider = ClaudeProvider(api_key="sk-ant-api03-...")

# MCP tools (from telegraph-mcp server)
tools = [
    {
        "name": "create_page",
        "description": "Create a new Telegraph page",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Page title"},
                "content": {"type": "array", "description": "Page content"}
            },
            "required": ["title", "content"]
        }
    }
]

messages = [
    {
        "role": "user",
        "content": "Create a page titled 'Hello World' with text 'This is my first page'"
    }
]

# Send request with tools (automatically converted to provider format)
response = provider.chat(messages, tools=tools)

# Check if AI wants to use tools
tool_calls = provider.extract_tool_calls(response)

if tool_calls:
    print(f"AI wants to call: {tool_calls[0]['name']}")
    print(f"With parameters: {tool_calls[0]['input']}")
else:
    print("No tool calls")
```

### 4. Complete Tool Execution Loop

```python
from services.ai_providers import ClaudeProvider

provider = ClaudeProvider(api_key="sk-ant-api03-...")

tools = [...]  # Your MCP tools

messages = [
    {"role": "user", "content": "Create a page called 'Getting Started'"}
]

# Step 1: Initial AI response
response = provider.chat(messages, tools=tools)

# Add assistant's response to conversation
messages.append({
    "role": "assistant",
    "content": response["content"]
})

# Step 2: Check for tool calls
tool_calls = provider.extract_tool_calls(response)

if tool_calls:
    # Step 3: Execute each tool
    for call in tool_calls:
        print(f"Executing: {call['name']} with {call['input']}")

        # Execute via your MCP client
        result = your_mcp_client.call_tool(call["name"], call["input"])

        # Format result for conversation
        tool_result = provider.format_tool_result(call["id"], result)
        messages.append(tool_result)

    # Step 4: Get final AI response
    final_response = provider.chat(messages)
    print("AI:", final_response["content"][0]["text"])
```

### 5. Streaming Response

```python
from services.ai_providers import ClaudeProvider

provider = ClaudeProvider(api_key="sk-ant-api03-...")

messages = [
    {"role": "user", "content": "Write me a short poem about technology"}
]

print("AI: ", end="", flush=True)
for chunk in provider.chat_stream(messages):
    print(chunk, end="", flush=True)
print()
```

### 6. Provider-Agnostic Code

```python
from services.ai_providers import ClaudeProvider, OpenAIProvider

def chat_with_any_provider(provider_type: str, api_key: str, message: str):
    """Works with any provider!"""

    # Create provider based on type
    if provider_type == "claude":
        provider = ClaudeProvider(api_key)
    elif provider_type == "openai":
        provider = OpenAIProvider(api_key)
    else:
        raise ValueError(f"Unknown provider: {provider_type}")

    # Same interface for both!
    messages = [{"role": "user", "content": message}]
    response = provider.chat(messages)

    # Extract text (provider-specific but simple)
    if provider_type == "claude":
        return response["content"][0]["text"]
    else:
        return response["choices"][0]["message"]["content"]

# Use it
answer = chat_with_any_provider("claude", "sk-ant-...", "Hello!")
print(answer)
```

### 7. With MCP Client Integration

```python
from services.mcp_client import TelegraphMCPClient
from services.ai_providers import ClaudeProvider

# Initialize both
mcp = TelegraphMCPClient()
ai = ClaudeProvider(api_key="sk-ant-...")

# Get tools from MCP
tools = mcp.list_tools()

# Chat with AI
messages = [{"role": "user", "content": "List all my pages"}]
response = ai.chat(messages, tools=tools)

# Execute tool calls
tool_calls = ai.extract_tool_calls(response)
if tool_calls:
    for call in tool_calls:
        # Execute via MCP
        result = mcp.call_tool(call["name"], call["input"])

        # Add to conversation
        messages.append({"role": "assistant", "content": response["content"]})
        messages.append(ai.format_tool_result(call["id"], result))

    # Get final response
    final = ai.chat(messages)
    print(final["content"][0]["text"])
```

## Key Concepts

### Tool Format Conversion

The providers automatically convert MCP tools to the correct format:

**MCP Format** (input):
```python
{
    "name": "create_page",
    "input_schema": {...}  # MCP uses input_schema
}
```

**Claude** (no change needed):
```python
{
    "name": "create_page",
    "input_schema": {...}  # Claude uses input_schema too!
}
```

**OpenAI** (automatically converted):
```python
{
    "type": "function",
    "function": {
        "name": "create_page",
        "parameters": {...}  # OpenAI uses parameters
    }
}
```

### Normalized Tool Calls

Both providers return the same format:

```python
[
    {
        "id": "unique_call_id",
        "name": "tool_name",
        "input": {"param": "value"}  # Already parsed and ready!
    }
]
```

### Provider Models

- **Claude**: `claude-sonnet-4-20250514`
- **OpenAI**: `gpt-4o`

To change the model, modify the `model` attribute after initialization:

```python
provider = ClaudeProvider(api_key="...")
provider.model = "claude-opus-4-5-20251101"  # Use a different model
```

## Error Handling

```python
from services.ai_providers import ClaudeProvider
import anthropic

provider = ClaudeProvider(api_key="sk-ant-...")

try:
    response = provider.chat(messages, tools=tools)
except anthropic.APIError as e:
    print(f"API Error: {e}")
except anthropic.RateLimitError as e:
    print(f"Rate limit exceeded: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

## Best Practices

1. **Always validate API keys** before making requests
2. **Handle tool calls in a loop** - AI may need multiple tool executions
3. **Stream responses** in interactive UIs for better UX
4. **Track token usage** via response metadata for cost monitoring
5. **Use type hints** for better IDE support
6. **Never log API keys** or sensitive data

## Troubleshooting

### Import Error

```python
# Wrong
from ai_providers import ClaudeProvider  # ✗ Won't work

# Right
from services.ai_providers import ClaudeProvider  # ✓ Correct
```

### Missing Dependencies

```bash
pip install anthropic openai
```

### Tool Format Issues

The providers handle conversion automatically. If you get tool-related errors:

1. Verify your MCP tools have `input_schema` (not `parameters`)
2. Check tool names are valid Python identifiers
3. Ensure `required` fields are in the schema

## Next Steps

- Read the full [README.md](README.md) for detailed documentation
- Check [example_usage.py](example_usage.py) for more patterns
- See [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) for architecture details

## Support

For issues or questions:
1. Check the [README.md](README.md) documentation
2. Review the example files
3. Verify your API keys are valid
4. Ensure all dependencies are installed
