# Telegraph MCP Client - Usage Guide

## Overview

The `TelegraphMCPClient` provides a Python interface to the [telegraph-mcp](https://github.com/NehoraiHadad/telegraph-mcp) npm package using the Model Context Protocol (MCP). This enables programmatic access to Telegraph API functionality with both async and synchronous interfaces.

## Installation

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Ensure Node.js and npm are installed (for telegraph-mcp):
```bash
node --version  # Should be >= 16.0.0
npm --version
```

3. The telegraph-mcp package will be automatically installed when first used via `npx`.

## Quick Start

### Basic Usage

```python
from services.mcp_client import TelegraphMCPClient

# Initialize with your Telegraph access token
client = TelegraphMCPClient(access_token="your_telegraph_token")

# Get available tools
tools = client.get_tools_sync()
print(f"Available tools: {len(tools)}")

# Call a tool
result = client.call_tool_sync(
    "get_account_info",
    {}
)
print(result)
```

### Async Usage

```python
import asyncio
from services.mcp_client import TelegraphMCPClient

async def main():
    client = TelegraphMCPClient(access_token="your_token")

    # Get tools asynchronously
    tools = await client.get_tools()

    # Call tool asynchronously
    result = await client.call_tool("create_page", {
        "title": "My Page",
        "content": "Page content in **Markdown**"
    })
    print(result)

asyncio.run(main())
```

## Available Tools

The telegraph-mcp server provides the following tools:

### Account Management
- `create_account` - Create a new Telegraph account
- `edit_account` - Update account information
- `get_account_info` - Retrieve account details
- `revoke_access_token` - Revoke access token

### Page Management
- `create_page` - Create a new Telegraph page (supports Markdown!)
- `edit_page` - Update an existing page
- `get_page` - Retrieve page content
- `get_page_list` - List all pages for the account
- `get_views` - Get page view statistics

### Media
- `upload_image` - Upload images to Telegraph
- `upload_video` - Upload videos to Telegraph

### Export & Templates
- Various template and export utilities

## API Reference

### `TelegraphMCPClient`

#### Constructor

```python
client = TelegraphMCPClient(access_token: str)
```

**Parameters:**
- `access_token` (str): Your Telegraph access token

**Raises:**
- `ValueError`: If access_token is empty or None

#### Methods

##### `get_tools_sync() -> List[Dict[str, Any]]`

Get available tools from the MCP server (synchronous).

**Returns:**
- List of tool dictionaries with:
  - `name`: Tool identifier
  - `description`: Human-readable description
  - `input_schema`: JSON Schema for parameters

**Example:**
```python
tools = client.get_tools_sync()
for tool in tools:
    print(f"{tool['name']}: {tool['description']}")
```

##### `call_tool_sync(name: str, arguments: Dict[str, Any] = None) -> Any`

Call a tool on the MCP server (synchronous).

**Parameters:**
- `name`: Tool name (e.g., "create_page")
- `arguments`: Dictionary of tool arguments

**Returns:**
- Tool execution result (format depends on the specific tool)

**Raises:**
- `RuntimeError`: If tool execution fails

**Example:**
```python
result = client.call_tool_sync("create_page", {
    "title": "My Article",
    "content": "# Heading\n\nContent here",
    "author_name": "John Doe"
})
```

##### `get_tools() -> List[Dict[str, Any]]` (async)

Async version of `get_tools_sync()`.

##### `call_tool(name: str, arguments: Dict[str, Any] = None) -> Any` (async)

Async version of `call_tool_sync()`.

##### `clear_cache() -> None`

Clear the cached tools list. Forces next `get_tools()` to fetch fresh data.

## Common Use Cases

### 1. Create a Telegraph Page

```python
result = client.call_tool_sync("create_page", {
    "title": "API Documentation",
    "content": """
# API Overview

This is a **markdown** formatted page.

## Features
- Support for markdown
- Images and media
- Clean URLs
    """,
    "author_name": "Tech Team",
    "author_url": "https://example.com"
})

print(f"Page URL: {result['url']}")
```

### 2. Get Page List

```python
pages = client.call_tool_sync("get_page_list", {
    "offset": 0,
    "limit": 10
})

for page in pages['pages']:
    print(f"{page['title']}: {page['url']}")
```

### 3. Update Existing Page

```python
result = client.call_tool_sync("edit_page", {
    "path": "your-page-path",  # From page URL
    "title": "Updated Title",
    "content": "# Updated content"
})
```

### 4. Get Page Statistics

```python
stats = client.call_tool_sync("get_views", {
    "path": "your-page-path",
    "year": 2025,
    "month": 12,
    "day": 8
})

print(f"Total views: {stats['views']}")
```

### 5. Upload Image

```python
# Upload from URL
result = client.call_tool_sync("upload_image", {
    "url": "https://example.com/image.jpg"
})

print(f"Image URL: {result}")

# Upload from file (base64)
import base64

with open("image.jpg", "rb") as f:
    image_data = base64.b64encode(f.read()).decode()

result = client.call_tool_sync("upload_image", {
    "data": image_data
})
```

## Integration with Streamlit

### Example Component

```python
import streamlit as st
from services.mcp_client import TelegraphMCPClient
from services.user_settings_manager import UserSettingsManager

def render_mcp_tools():
    """Display available MCP tools in Streamlit."""
    st.header("Telegraph MCP Tools")

    # Get access token
    token = UserSettingsManager.get_access_token()
    if not token:
        st.warning("Please configure Telegraph token first")
        return

    # Initialize client
    client = TelegraphMCPClient(access_token=token)

    # Show tools
    with st.spinner("Loading tools..."):
        tools = client.get_tools_sync()

    st.success(f"Found {len(tools)} tools")

    for tool in tools:
        with st.expander(tool['name']):
            st.write(tool['description'])
            st.json(tool['input_schema'])
```

## Error Handling

The client includes comprehensive error handling:

```python
try:
    result = client.call_tool_sync("create_page", {
        "title": "Test",
        "content": "Content"
    })
except ValueError as e:
    # Invalid parameters
    print(f"Invalid parameters: {e}")
except RuntimeError as e:
    # MCP server connection/execution error
    print(f"MCP error: {e}")
except Exception as e:
    # Other errors
    print(f"Unexpected error: {e}")
```

## Performance Considerations

1. **Tool Caching**: Tools are cached after first fetch. Call `clear_cache()` if tools change.

2. **Connection Pooling**: Each tool call creates a new connection. For multiple calls, consider batching operations.

3. **Async vs Sync**: Use async methods in async contexts for better performance. Use sync methods in Streamlit or other sync contexts.

## Debugging

Enable logging to see MCP client activity:

```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("services.mcp_client")
logger.setLevel(logging.DEBUG)
```

## Troubleshooting

### Issue: "MCP package not found"
**Solution:** Run `pip install mcp`

### Issue: "telegraph-mcp: command not found"
**Solution:** Ensure Node.js and npm are installed, or run `npx telegraph-mcp` manually to trigger installation.

### Issue: "Event loop is already running"
**Solution:** The client automatically handles this. If it persists, use the async methods directly.

### Issue: Tool execution timeout
**Solution:** Check network connectivity and Telegraph API status. Some operations may take longer.

## Security Best Practices

1. **Never commit tokens**: Keep Telegraph tokens in environment variables or secure storage
2. **Validate inputs**: Always validate user inputs before passing to tools
3. **Rate limiting**: Implement rate limiting to prevent API abuse
4. **Error messages**: Don't expose internal errors to end users

## Next Steps

- Integrate with AI providers (Claude, GPT-4, Gemini) for intelligent glossary management
- Build chat interface using the AI chat component
- Implement batch operations for multiple pages
- Add retry logic for transient failures

## Resources

- [Telegraph API Documentation](https://telegra.ph/api)
- [telegraph-mcp GitHub](https://github.com/NehoraiHadad/telegraph-mcp)
- [Model Context Protocol](https://modelcontextprotocol.io)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
