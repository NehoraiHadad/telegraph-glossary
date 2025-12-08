# MCP Client Integration Research - Technical Summary

## Executive Summary

This document provides a comprehensive technical analysis for integrating an MCP (Model Context Protocol) client into the Telegraph Glossary Streamlit application, enabling AI-powered glossary management with a single click.

---

## 1. MCP Python SDK - Technical Overview

### Official SDK
- **Package**: `mcp` (PyPI)
- **Repository**: [github.com/modelcontextprotocol/python-sdk](https://github.com/modelcontextprotocol/python-sdk)
- **Installation**: `pip install mcp`

### Communication Methods
| Transport | Description | Use Case |
|-----------|-------------|----------|
| **stdio** | Standard input/output | Local server processes (npx, python scripts) |
| **SSE** | Server-Sent Events | HTTP-based remote servers |
| **Streamable HTTP** | HTTP with streaming | Cloud-hosted MCP servers |

### Client Implementation Pattern

```python
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Configure stdio connection to telegraph-mcp
server_params = StdioServerParameters(
    command="npx",
    args=["telegraph-mcp"],
    env={"TELEGRAPH_ACCESS_TOKEN": "your_token"}
)

async def connect_to_mcp():
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # List available tools
            tools = await session.list_tools()
            print(f"Available tools: {[t.name for t in tools.tools]}")

            # Call a tool
            result = await session.call_tool(
                "create_page",
                arguments={"title": "Test", "content": "Hello"}
            )
            return result
```

---

## 2. AI Model Integration Comparison

### Tool/Function Calling Support

| Feature | Claude (Anthropic) | GPT-4 (OpenAI) | Gemini (Google) |
|---------|-------------------|----------------|-----------------|
| **Schema Format** | `input_schema` (JSON Schema) | `parameters` (JSON Schema) | Python function introspection |
| **Stop Indicator** | `stop_reason: "tool_use"` | `tool_calls` in response | `FunctionCall` object |
| **Result Format** | `tool_result` with `tool_use_id` | `role: "tool"` with `tool_call_id` | `FunctionResponse` |
| **Auto-execution** | No (manual loop) | No (manual loop) | Yes (optional) |
| **Streaming** | Supported | Supported | Supported |

### Claude (Anthropic) - Recommended

Claude has native MCP support and the most seamless integration:

```python
from anthropic import Anthropic

client = Anthropic(api_key="user_api_key")

# Tools from MCP server (converted to Claude format)
tools = [
    {
        "name": "create_page",
        "description": "Create a new Telegraph page",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Page title"},
                "content": {"type": "string", "description": "Page content (Markdown)"}
            },
            "required": ["title", "content"]
        }
    }
]

response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    tools=tools,
    messages=[{"role": "user", "content": "Create a glossary entry for API"}]
)

# Handle tool_use response
if response.stop_reason == "tool_use":
    tool_use = response.content[0]
    # Execute via MCP: session.call_tool(tool_use.name, tool_use.input)
```

### OpenAI (GPT-4)

```python
from openai import OpenAI

client = OpenAI(api_key="user_api_key")

tools = [{
    "type": "function",
    "function": {
        "name": "create_page",
        "description": "Create a new Telegraph page",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "content": {"type": "string"}
            },
            "required": ["title", "content"]
        }
    }
}]

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Create a glossary entry for API"}],
    tools=tools,
    tool_choice="auto"
)

if response.choices[0].message.tool_calls:
    tool_call = response.choices[0].message.tool_calls[0]
    # Execute via MCP
```

### Gemini (Google)

```python
from google import genai
from google.genai import types

client = genai.Client(api_key="user_api_key")

def create_page(title: str, content: str) -> str:
    """Create a new Telegraph page.

    Args:
        title: Page title
        content: Page content in Markdown
    """
    # This will be intercepted and routed to MCP
    pass

response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents='Create a glossary entry for API',
    config=types.GenerateContentConfig(tools=[create_page])
)
```

---

## 3. Telegraph MCP Server Tools

The `telegraph-mcp` npm package provides 15 tools:

### Account Management
- `create_account` - Create new Telegraph account
- `edit_account` - Update account info
- `get_account_info` - Retrieve account details
- `revoke_access_token` - Revoke token

### Page Management
- `create_page` - Create new page (supports Markdown!)
- `edit_page` - Update existing page
- `get_page` - Retrieve page content
- `get_page_list` - List all pages
- `get_views` - Get page statistics

### Media
- `upload_image` - Upload images
- `upload_video` - Upload videos

### Templates & Export
- Pre-built templates for blog posts, documentation, articles
- Export/backup in Markdown or HTML formats

---

## 4. Recommended Architecture

```
+-------------------+     +------------------+     +------------------+
|   Streamlit UI    |     |   MCP Client     |     |  telegraph-mcp   |
|  (User Interface) |     |   (Python)       |     |  (npm server)    |
+-------------------+     +------------------+     +------------------+
        |                         |                        |
        | User Message            | stdio                  |
        v                         v                        v
+-------------------+     +------------------+     +------------------+
|   AI Provider     |<--->|   Tool Bridge    |<--->|  Telegraph API   |
| (Claude/OpenAI/   |     | (MCP<->Provider) |     |                  |
|  Gemini)          |     |                  |     |                  |
+-------------------+     +------------------+     +------------------+
        ^
        |
  User's API Key
  (session_state)
```

### Flow Description

1. **User Input**: User types a request in Streamlit chat
2. **AI Processing**: Request sent to AI provider with MCP tools
3. **Tool Request**: AI decides to use a tool (e.g., `create_page`)
4. **MCP Execution**: Tool call routed to telegraph-mcp server
5. **Telegraph API**: MCP server executes Telegraph API call
6. **Response**: Result flows back through the chain

---

## 5. Security Considerations

### API Key Management

| Approach | Pros | Cons | Recommendation |
|----------|------|------|----------------|
| **Session State** | Temporary, per-session | Lost on refresh | For AI provider keys |
| **URL Parameters** | Persistent, shareable | Visible in URL | For Telegraph token (current) |
| **st.secrets** | Server-side, secure | Not per-user | For app-level secrets |
| **Browser Storage** | Persistent, client-side | Requires JS | Alternative consideration |

### Recommended Strategy

```python
# AI API Keys - Session state (temporary, user enters each session)
if "ai_api_key" not in st.session_state:
    st.session_state.ai_api_key = None

# Telegraph Token - URL parameters (current approach, persistent)
telegraph_token = UserSettingsManager.get_access_token()

# Never log or expose keys
# Use HTTPS in production
# Implement rate limiting
```

### Security Best Practices

1. **Never store AI API keys persistently** - Users enter per session
2. **Validate all inputs** before passing to AI/MCP
3. **Rate limit API calls** to prevent abuse
4. **Use HTTPS** in production deployments
5. **Monitor usage** for anomalies

---

## 6. Implementation Plan

### Phase 1: MCP Client Setup (Core Infrastructure)

**Tasks:**
1. Add MCP SDK dependency (`pip install mcp`)
2. Create `services/mcp_client.py` with connection management
3. Implement tool discovery and caching
4. Add error handling and reconnection logic

**Files to create/modify:**
- `services/mcp_client.py` (new)
- `requirements.txt` (update)

### Phase 2: AI Provider Integration

**Tasks:**
1. Create unified AI client interface
2. Implement Claude provider (primary)
3. Implement OpenAI provider (secondary)
4. Implement Gemini provider (optional)
5. Add tool format conversion (MCP -> Provider format)

**Files to create/modify:**
- `services/ai_providers/base.py` (new)
- `services/ai_providers/claude_provider.py` (new)
- `services/ai_providers/openai_provider.py` (new)
- `services/ai_providers/gemini_provider.py` (new)

### Phase 3: Chat UI Component

**Tasks:**
1. Create chat interface component
2. Implement message history (session state)
3. Add streaming response display
4. Show tool execution status
5. Handle errors gracefully

**Files to create/modify:**
- `components/ai_chat.py` (new)
- `components/ai_integration.py` (update)

### Phase 4: User Experience Polish

**Tasks:**
1. Add API key input/validation
2. Provider selection dropdown
3. Conversation history export
4. Usage monitoring/limits
5. Help documentation

---

## 7. Code Skeleton

### `services/mcp_client.py`

```python
"""MCP Client for Telegraph server communication."""

import asyncio
from typing import Optional, List, Dict, Any
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp import types


class TelegraphMCPClient:
    """Client for connecting to telegraph-mcp server."""

    def __init__(self, access_token: str):
        self.access_token = access_token
        self.session: Optional[ClientSession] = None
        self._tools_cache: Optional[List[types.Tool]] = None

    def _get_server_params(self) -> StdioServerParameters:
        """Get server parameters for stdio connection."""
        return StdioServerParameters(
            command="npx",
            args=["telegraph-mcp"],
            env={"TELEGRAPH_ACCESS_TOKEN": self.access_token}
        )

    async def connect(self) -> None:
        """Establish connection to MCP server."""
        # Connection is handled via context manager in actual calls
        pass

    async def get_tools(self) -> List[Dict[str, Any]]:
        """Get available tools from MCP server."""
        if self._tools_cache:
            return self._tools_cache

        server_params = self._get_server_params()
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools_response = await session.list_tools()
                self._tools_cache = [
                    {
                        "name": tool.name,
                        "description": tool.description,
                        "input_schema": tool.inputSchema
                    }
                    for tool in tools_response.tools
                ]
                return self._tools_cache

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        """Call a tool on the MCP server."""
        server_params = self._get_server_params()
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(name, arguments=arguments)
                if result.content and len(result.content) > 0:
                    content = result.content[0]
                    if isinstance(content, types.TextContent):
                        return content.text
                return result

    def get_tools_sync(self) -> List[Dict[str, Any]]:
        """Synchronous wrapper for get_tools."""
        return asyncio.run(self.get_tools())

    def call_tool_sync(self, name: str, arguments: Dict[str, Any]) -> Any:
        """Synchronous wrapper for call_tool."""
        return asyncio.run(self.call_tool(name, arguments))
```

### `services/ai_providers/base.py`

```python
"""Base class for AI providers."""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Generator


class AIProviderBase(ABC):
    """Abstract base class for AI providers."""

    def __init__(self, api_key: str):
        self.api_key = api_key

    @abstractmethod
    def chat(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        stream: bool = False
    ) -> Dict[str, Any]:
        """Send a chat message and get a response."""
        pass

    @abstractmethod
    def chat_stream(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> Generator[str, None, None]:
        """Stream a chat response."""
        pass

    @abstractmethod
    def convert_tools_format(
        self,
        mcp_tools: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Convert MCP tools format to provider-specific format."""
        pass

    @abstractmethod
    def extract_tool_calls(
        self,
        response: Dict[str, Any]
    ) -> Optional[List[Dict[str, Any]]]:
        """Extract tool calls from provider response."""
        pass
```

### `services/ai_providers/claude_provider.py`

```python
"""Claude (Anthropic) AI provider implementation."""

from typing import List, Dict, Any, Optional, Generator
from anthropic import Anthropic
from .base import AIProviderBase


class ClaudeProvider(AIProviderBase):
    """Anthropic Claude provider."""

    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.client = Anthropic(api_key=api_key)
        self.model = "claude-sonnet-4-20250514"

    def convert_tools_format(
        self,
        mcp_tools: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Convert MCP tools to Claude format (already compatible)."""
        return [
            {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "input_schema": tool.get("input_schema", {"type": "object", "properties": {}})
            }
            for tool in mcp_tools
        ]

    def chat(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        stream: bool = False
    ) -> Dict[str, Any]:
        """Send chat message to Claude."""
        kwargs = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": messages
        }

        if tools:
            kwargs["tools"] = self.convert_tools_format(tools)

        response = self.client.messages.create(**kwargs)

        return {
            "content": response.content,
            "stop_reason": response.stop_reason,
            "model": response.model,
            "usage": {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens
            }
        }

    def chat_stream(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> Generator[str, None, None]:
        """Stream chat response from Claude."""
        kwargs = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": messages,
            "stream": True
        }

        if tools:
            kwargs["tools"] = self.convert_tools_format(tools)

        with self.client.messages.stream(**kwargs) as stream:
            for text in stream.text_stream:
                yield text

    def extract_tool_calls(
        self,
        response: Dict[str, Any]
    ) -> Optional[List[Dict[str, Any]]]:
        """Extract tool calls from Claude response."""
        if response.get("stop_reason") != "tool_use":
            return None

        tool_calls = []
        for block in response.get("content", []):
            if hasattr(block, "type") and block.type == "tool_use":
                tool_calls.append({
                    "id": block.id,
                    "name": block.name,
                    "arguments": block.input
                })

        return tool_calls if tool_calls else None
```

### `components/ai_chat.py`

```python
"""AI Chat component for Streamlit."""

import streamlit as st
from typing import Optional
import asyncio

from services.mcp_client import TelegraphMCPClient
from services.ai_providers.claude_provider import ClaudeProvider
from services.user_settings_manager import UserSettingsManager


def render_ai_chat() -> None:
    """Render the AI chat interface."""
    st.header("AI Assistant")

    # Initialize session state
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []
    if "ai_api_key" not in st.session_state:
        st.session_state.ai_api_key = ""

    # API Key input
    with st.sidebar:
        st.subheader("AI Configuration")

        provider = st.selectbox(
            "AI Provider",
            ["Claude (Anthropic)", "GPT-4 (OpenAI)", "Gemini (Google)"],
            index=0
        )

        api_key = st.text_input(
            "API Key",
            type="password",
            value=st.session_state.ai_api_key,
            help="Your API key is stored only in session memory"
        )

        if api_key != st.session_state.ai_api_key:
            st.session_state.ai_api_key = api_key

        if st.button("Clear Chat"):
            st.session_state.chat_messages = []
            st.rerun()

    # Check prerequisites
    telegraph_token = UserSettingsManager.get_access_token()
    if not telegraph_token:
        st.warning("Please configure your Telegraph token first.")
        return

    if not st.session_state.ai_api_key:
        st.info("Enter your AI provider API key to start chatting.")
        return

    # Display chat history
    for message in st.session_state.chat_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Chat input
    if prompt := st.chat_input("Ask me to help with your glossary..."):
        # Add user message
        st.session_state.chat_messages.append({
            "role": "user",
            "content": prompt
        })

        with st.chat_message("user"):
            st.markdown(prompt)

        # Get AI response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response = get_ai_response(
                    messages=st.session_state.chat_messages,
                    api_key=st.session_state.ai_api_key,
                    telegraph_token=telegraph_token,
                    provider=provider
                )

            st.markdown(response)

        # Add assistant message
        st.session_state.chat_messages.append({
            "role": "assistant",
            "content": response
        })


def get_ai_response(
    messages: list,
    api_key: str,
    telegraph_token: str,
    provider: str
) -> str:
    """Get response from AI provider with MCP tools."""
    try:
        # Initialize MCP client
        mcp_client = TelegraphMCPClient(telegraph_token)
        tools = mcp_client.get_tools_sync()

        # Initialize AI provider
        if "Claude" in provider:
            ai_provider = ClaudeProvider(api_key)
        else:
            return "Provider not yet implemented"

        # Convert messages to provider format
        formatted_messages = [
            {"role": m["role"], "content": m["content"]}
            for m in messages
        ]

        # Get initial response
        response = ai_provider.chat(formatted_messages, tools)

        # Handle tool calls
        tool_calls = ai_provider.extract_tool_calls(response)

        if tool_calls:
            # Execute tools and continue conversation
            for tool_call in tool_calls:
                tool_result = mcp_client.call_tool_sync(
                    tool_call["name"],
                    tool_call["arguments"]
                )

                # Add tool result to messages
                formatted_messages.append({
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": tool_call["id"],
                            "name": tool_call["name"],
                            "input": tool_call["arguments"]
                        }
                    ]
                })
                formatted_messages.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_call["id"],
                            "content": str(tool_result)
                        }
                    ]
                })

            # Get final response
            final_response = ai_provider.chat(formatted_messages, tools)
            return extract_text_content(final_response)

        return extract_text_content(response)

    except Exception as e:
        return f"Error: {str(e)}"


def extract_text_content(response: dict) -> str:
    """Extract text content from AI response."""
    content = response.get("content", [])
    text_parts = []

    for block in content:
        if hasattr(block, "text"):
            text_parts.append(block.text)
        elif isinstance(block, dict) and block.get("type") == "text":
            text_parts.append(block.get("text", ""))

    return "\n".join(text_parts) if text_parts else "No response generated."
```

---

## 8. Dependencies

Add to `requirements.txt`:

```
# MCP Client
mcp>=1.0.0

# AI Providers
anthropic>=0.30.0
openai>=1.30.0
google-genai>=1.0.0

# Async support
anyio>=4.0.0
```

---

## 9. Alternative Approaches Considered

### Option A: LangChain Integration
- **Pros**: Unified interface, extensive tooling, agent framework
- **Cons**: Heavy dependency, learning curve, abstraction overhead

### Option B: Direct API Integration (without MCP)
- **Pros**: Simpler, fewer dependencies
- **Cons**: Duplicates telegraph-mcp functionality, no tool reuse

### Option C: Embedded MCP Server (Python)
- **Pros**: No npm dependency, pure Python
- **Cons**: Requires reimplementing telegraph-mcp tools

**Recommendation**: Use the official MCP Python SDK with stdio transport to leverage the existing telegraph-mcp npm package. This provides the best balance of functionality and maintainability.

---

## 10. References

### Documentation
- [Model Context Protocol](https://modelcontextprotocol.io)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [Anthropic Claude Tool Use](https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/overview)
- [OpenAI Function Calling](https://platform.openai.com/docs/guides/function-calling)
- [Google Gemini Function Calling](https://ai.google.dev/docs)
- [Streamlit Secrets Management](https://docs.streamlit.io/develop/concepts/connections/secrets-management)
- [Best Practices for GenAI Apps](https://blog.streamlit.io/best-practices-for-building-genai-apps-with-streamlit/)

### Related Projects
- [telegraph-mcp](https://github.com/NehoraiHadad/telegraph-mcp) - MCP server for Telegraph API
- [FastMCP](https://github.com/jlowin/fastmcp) - Fast, Pythonic MCP implementation
- [LangChain MCP Adapters](https://www.npmjs.com/package/@langchain/mcp-adapters)

---

## Next Steps

1. Review and approve this technical plan
2. Begin Phase 1 implementation (MCP Client Setup)
3. Test with existing telegraph-mcp server
4. Implement AI provider integration
5. Build chat UI component
6. User testing and refinement

---

*Generated: December 2025*
