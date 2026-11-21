# AI Chat Component Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                      Streamlit Web Interface                     │
│                         (User Browser)                           │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             │ HTTP/WebSocket
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                      Main Application                            │
│                         (app.py)                                 │
│                                                                  │
│  ┌──────────┬──────────┬──────────┬──────────┬──────────┐     │
│  │Glossary  │  Text    │Settings  │   AI     │ AI Chat  │     │
│  │ Manager  │Processor │  Panel   │Integration│ Component│     │
│  └──────────┴──────────┴──────────┴──────────┴────┬─────┘     │
│                                                      │           │
└─────────────────────────────────────────────────────┼───────────┘
                                                       │
                                                       │
        ┌──────────────────────────────────────────────┴──────────────────┐
        │                                                                   │
        │              AI Chat Component (ai_chat.py)                      │
        │                                                                   │
        │  ┌───────────────────────────────────────────────────────────┐  │
        │  │ 1. render_ai_chat()          - Main entry point           │  │
        │  │ 2. _init_chat_state()        - Session state setup        │  │
        │  │ 3. _render_api_config()      - API key UI                 │  │
        │  │ 4. _check_prerequisites()    - Validation                 │  │
        │  │ 5. _render_chat_history()    - Display messages           │  │
        │  │ 6. _handle_chat_input()      - User input                 │  │
        │  │ 7. _get_ai_response()        - Core AI logic              │  │
        │  │ 8. _handle_tool_calls()      - MCP tool execution         │  │
        │  └───────────────────────────────────────────────────────────┘  │
        │                                                                   │
        └───────┬────────────────────────────────────────┬─────────────────┘
                │                                        │
                │                                        │
     ┌──────────▼──────────┐                ┌──────────▼──────────────┐
     │  User Settings      │                │   Session State         │
     │     Manager         │                │                         │
     │                     │                │  - chat_messages        │
     │  - get_access_token │                │  - ai_api_key          │
     │  - get_author_name  │                │  - ai_provider         │
     │  - get_glossary     │                │  - mcp_tools_cache     │
     │                     │                │  - glossary            │
     └──────────┬──────────┘                └─────────────────────────┘
                │
                │ Telegraph Token
                │
     ┌──────────▼──────────┐
     │   MCP Client        │
     │ (mcp_client.py)     │
     │                     │
     │  - get_tools_sync() │
     │  - call_tool_sync() │
     │  - Tool caching     │
     └──────────┬──────────┘
                │
                │ stdio transport
                │
     ┌──────────▼──────────┐
     │  Telegraph MCP      │
     │     Server          │
     │  (npx telegraph-mcp)│
     │                     │
     │  Tools:             │
     │  - create_page      │
     │  - edit_page        │
     │  - get_page         │
     │  - get_page_list    │
     └──────────┬──────────┘
                │
                │ HTTPS
                │
     ┌──────────▼──────────┐
     │  Telegraph API      │
     │  (telegra.ph)       │
     └─────────────────────┘


        ┌────────────────────────────────────────────────┐
        │         AI Provider Selection                  │
        │                                                │
        │  ┌──────────────┐  ┌──────────────┐          │
        │  │   Claude     │  │   OpenAI     │          │
        │  │   Provider   │  │   Provider   │          │
        │  │              │  │              │          │
        │  │ Anthropic    │  │ Chat         │          │
        │  │ Messages API │  │ Completions  │          │
        │  │              │  │ API          │          │
        │  │ Claude       │  │ GPT-4o       │          │
        │  │ Sonnet 4     │  │              │          │
        │  └──────┬───────┘  └──────┬───────┘          │
        │         │                 │                   │
        │         │                 │                   │
        │  ┌──────▼─────────────────▼───────┐          │
        │  │                                 │          │
        │  │     AIProviderBase              │          │
        │  │                                 │          │
        │  │  - chat()                       │          │
        │  │  - chat_stream()                │          │
        │  │  - convert_tools_format()       │          │
        │  │  - extract_tool_calls()         │          │
        │  │  - format_tool_result()         │          │
        │  │                                 │          │
        │  └─────────────┬───────────────────┘          │
        │                │                              │
        │         ┌──────▼───────┐                      │
        │         │   Gemini     │                      │
        │         │   Provider   │                      │
        │         │              │                      │
        │         │ Google       │                      │
        │         │ genai API    │                      │
        │         │              │                      │
        │         │ Gemini 2.0   │                      │
        │         │ Flash        │                      │
        │         └──────────────┘                      │
        │                                                │
        └────────────────────────────────────────────────┘
```

## Data Flow

### User Message Flow

```
User types message
       │
       ▼
[1] _handle_chat_input()
       │
       ├─→ Add to chat_messages
       │
       ├─→ Display in UI
       │
       ▼
[2] _get_ai_response()
       │
       ├─→ Initialize MCP client
       │   │
       │   └─→ TelegraphMCPClient.get_tools_sync()
       │       │
       │       └─→ telegraph-mcp server
       │           │
       │           └─→ Returns: [create_page, edit_page, ...]
       │
       ├─→ Initialize AI provider
       │   │
       │   └─→ ClaudeProvider / OpenAIProvider / GeminiProvider
       │
       ├─→ Build messages with context
       │   │
       │   └─→ _build_system_prompt()
       │       │
       │       └─→ "You are a glossary assistant..."
       │           "Current glossary has N terms"
       │           "Existing terms: API, Bot, ..."
       │
       ├─→ Send to AI with tools
       │   │
       │   └─→ provider.chat(messages, tools)
       │       │
       │       └─→ AI API (Claude/OpenAI/Gemini)
       │           │
       │           └─→ Returns: response with/without tool calls
       │
       ▼
[3] Check for tool calls
       │
       ├─→ No tools? → Extract text → Display
       │
       └─→ Yes tools? → _handle_tool_calls()
                         │
                         ├─→ For each tool call:
                         │   │
                         │   ├─→ Show status: "Executing..."
                         │   │
                         │   ├─→ mcp_client.call_tool_sync()
                         │   │   │
                         │   │   └─→ telegraph-mcp server
                         │   │       │
                         │   │       └─→ Telegraph API
                         │   │           │
                         │   │           └─→ Creates/edits page
                         │   │
                         │   ├─→ Show result
                         │   │
                         │   └─→ Update status: "Completed"
                         │
                         ├─→ Format tool results
                         │
                         ├─→ Send back to AI
                         │   │
                         │   └─→ provider.chat(messages + results, tools)
                         │       │
                         │       └─→ Returns: final summary
                         │
                         └─→ Extract text → Display
```

## Component Architecture

### Layer 1: User Interface

```python
def render_ai_chat():
    """Main UI orchestrator"""
    _init_chat_state()           # Setup
    _render_api_config()         # Configuration UI
    if not _check_prerequisites(): # Validation
        return
    _render_chat_history()       # Display
    _handle_chat_input()         # Input handling
```

### Layer 2: State Management

```python
Session State:
├── chat_messages: List[Dict]     # Conversation history
├── ai_api_key: str              # User's API key
├── ai_provider: str             # "Claude", "OpenAI", "Gemini"
├── mcp_tools_cache: List[Dict]  # Cached tools
└── glossary: Dict               # Current glossary

User Settings Manager:
├── access_token                 # Telegraph token
├── author_name                  # For pages
└── index_page_path              # Glossary index
```

### Layer 3: AI Provider Abstraction

```python
AIProviderBase (Abstract)
├── chat(messages, tools) → response
├── chat_stream(messages, tools) → Generator
├── convert_tools_format(mcp_tools) → provider_tools
├── extract_tool_calls(response) → List[Dict]
└── format_tool_result(id, name, result) → Dict

Implementations:
├── ClaudeProvider
│   ├── Model: claude-sonnet-4-20250514
│   ├── API: anthropic.Anthropic
│   └── Tools: Native input_schema
│
├── OpenAIProvider
│   ├── Model: gpt-4o
│   ├── API: openai.OpenAI
│   └── Tools: Function calling (parameters)
│
└── GeminiProvider
    ├── Model: gemini-2.0-flash-exp
    ├── API: genai.Client
    └── Tools: FunctionDeclaration
```

### Layer 4: MCP Integration

```python
TelegraphMCPClient
├── __init__(access_token)
├── get_tools_sync() → List[Dict]
│   └── Caches tools for performance
├── call_tool_sync(name, args) → result
│   └── Executes via stdio transport
└── clear_cache()

Telegraph MCP Server (external)
├── create_page
├── edit_page
├── get_page
├── get_page_list
└── delete_page (if available)
```

## Message Format Examples

### User Message

```python
{
    "role": "user",
    "content": "Create a glossary entry for 'API'",
    "display_content": "Create a glossary entry for 'API'"
}
```

### Assistant Message (Text Only)

```python
{
    "role": "assistant",
    "content": "I'll create that entry for you.",
    "display_content": "I'll create that entry for you."
}
```

### Assistant Message (With Tool Calls)

**Claude Format:**
```python
{
    "role": "assistant",
    "content": [
        {
            "type": "text",
            "text": "I'll create that entry."
        },
        {
            "type": "tool_use",
            "id": "toolu_123",
            "name": "create_page",
            "input": {
                "title": "API",
                "content": "Application Programming Interface...",
                "author_name": "Glossary Bot"
            }
        }
    ]
}
```

**OpenAI Format:**
```python
{
    "role": "assistant",
    "content": None,
    "tool_calls": [
        {
            "id": "call_123",
            "type": "function",
            "function": {
                "name": "create_page",
                "arguments": "{\"title\":\"API\",\"content\":\"...\"}
            }
        }
    ]
}
```

**Gemini Format:**
```python
{
    "role": "model",
    "content": [],
    "function_calls": [
        {
            "name": "create_page",
            "args": {
                "title": "API",
                "content": "...",
                "author_name": "Glossary Bot"
            }
        }
    ]
}
```

### Tool Result Message

**Claude:**
```python
{
    "role": "user",
    "content": [
        {
            "type": "tool_result",
            "tool_use_id": "toolu_123",
            "content": '{"url": "https://telegra.ph/API-12-08", ...}'
        }
    ]
}
```

**OpenAI:**
```python
{
    "role": "tool",
    "tool_call_id": "call_123",
    "content": '{"url": "https://telegra.ph/API-12-08", ...}'
}
```

**Gemini:**
```python
{
    "role": "user",
    "parts": [
        FunctionResponse(
            name="create_page",
            response={"result": '{"url": "https://telegra.ph/API-12-08", ...}'}
        )
    ]
}
```

## Tool Schema Example

### MCP Tool Format

```python
{
    "name": "create_page",
    "description": "Create a new Telegraph page",
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Page title"
            },
            "content": {
                "type": "string",
                "description": "Page content in Markdown"
            },
            "author_name": {
                "type": "string",
                "description": "Author name (optional)"
            }
        },
        "required": ["title", "content"]
    }
}
```

### Provider-Specific Conversion

**Claude**: No conversion needed (same format)

**OpenAI**:
```python
{
    "type": "function",
    "function": {
        "name": "create_page",
        "description": "Create a new Telegraph page",
        "parameters": {  # input_schema → parameters
            "type": "object",
            "properties": {...},
            "required": [...]
        }
    }
}
```

**Gemini**:
```python
FunctionDeclaration(
    name="create_page",
    description="Create a new Telegraph page",
    parameters={  # input_schema → parameters
        "type": "object",
        "properties": {...},
        "required": [...]
    }
)
```

## Error Handling Flow

```
Error Occurs
     │
     ├─→ MCP Connection Error
     │   └─→ "Failed to connect to telegraph-mcp server"
     │
     ├─→ AI API Error
     │   ├─→ Invalid API key
     │   ├─→ Rate limit
     │   ├─→ Quota exceeded
     │   └─→ Network error
     │
     ├─→ Tool Execution Error
     │   ├─→ Invalid arguments
     │   ├─→ Telegraph API error
     │   └─→ Timeout
     │
     └─→ General Error
         └─→ Log and display user-friendly message
```

## Security Architecture

```
User Input
     │
     ├─→ API Key
     │   ├─→ Password field (UI)
     │   ├─→ Session state only
     │   └─→ Never logged or persisted
     │
     ├─→ Telegraph Token
     │   ├─→ URL parameter (per-user)
     │   ├─→ UserSettingsManager
     │   └─→ Environment variable to MCP
     │
     └─→ Chat Messages
         ├─→ Session state
         ├─→ Sanitized before display
         └─→ Not persisted
```

## Performance Optimizations

```
1. Tool Caching
   ├─→ Cache MCP tools on first fetch
   └─→ Reuse until session ends

2. Connection Pooling
   ├─→ Fresh connection per operation
   └─→ Context manager cleanup

3. Lazy Loading
   ├─→ Import providers on demand
   └─→ Initialize only when needed

4. Session Persistence
   ├─→ Chat history in session state
   └─→ Avoid re-rendering entire history
```

## Extensibility Points

### 1. Custom Providers

```python
class CustomProvider(AIProviderBase):
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.model = "custom-model"
        # Your implementation
```

### 2. Custom System Prompts

```python
def _build_system_prompt() -> str:
    # Add custom context
    return f"Custom prompt with {custom_data}"
```

### 3. Additional Tools

```python
# Tools automatically discovered from MCP server
# Add new tools by extending telegraph-mcp server
```

### 4. Streaming Support

```python
# Already available in providers
for chunk in provider.chat_stream(messages, tools):
    st.write(chunk)
```

## Dependencies Graph

```
ai_chat.py
├── streamlit
├── typing
├── logging
├── services/
│   ├── mcp_client
│   │   ├── mcp (external)
│   │   └── asyncio
│   ├── ai_providers/
│   │   ├── base
│   │   ├── claude_provider
│   │   │   └── anthropic (external)
│   │   ├── openai_provider
│   │   │   └── openai (external)
│   │   └── gemini_provider
│   │       └── google-genai (external)
│   └── user_settings_manager
│       ├── streamlit
│       └── urllib.parse
└── External Services
    ├── Telegraph API (telegra.ph)
    ├── Anthropic API (api.anthropic.com)
    ├── OpenAI API (api.openai.com)
    └── Google AI API (generativelanguage.googleapis.com)
```

---

This architecture provides:
- **Modularity**: Clear separation of concerns
- **Extensibility**: Easy to add providers/features
- **Maintainability**: Well-documented and structured
- **Security**: Proper key management and validation
- **Performance**: Caching and optimization
- **Reliability**: Comprehensive error handling
