# AI Chat Component Documentation

## Overview

The AI Chat component (`ai_chat.py`) provides an interactive chat interface that integrates multiple AI providers (Claude, OpenAI, Gemini) with the Telegraph MCP server, enabling AI assistants to manage glossary entries through natural language conversations.

## File Location

```
/home/ubuntu/projects/telegraph-glossary/components/ai_chat.py
```

## Features

### Multi-Provider Support
- **Claude (Anthropic)**: Claude Sonnet 4 with native tool calling
- **OpenAI**: GPT-4o with function calling
- **Gemini (Google)**: Gemini 2.0 Flash with function declarations

### MCP Tool Integration
- Automatic tool discovery from Telegraph MCP server
- Real-time tool execution with status indicators
- Tool result display and error handling
- Context-aware system prompts with glossary info

### User Interface
- Clean chat interface using Streamlit's `st.chat_message`
- Secure API key input (password field, session-only storage)
- Provider selection dropdown
- Conversation history management
- Clear chat functionality

### Smart Context
- Includes current glossary statistics in system prompt
- Lists existing terms for AI awareness (up to 20 terms)
- Provides guidance on when to use which tools

## Usage

### Basic Integration

```python
from components.ai_chat import render_ai_chat

# In your Streamlit app
render_ai_chat()
```

### Prerequisites

1. **Telegraph Token**: Must be configured via `UserSettingsManager.set_access_token(token)`
2. **AI API Key**: User provides via the UI (stored in session state only)
3. **Dependencies**: All listed in `requirements.txt`

### Session State Variables

The component manages these session state keys:

```python
st.session_state.chat_messages      # List of chat messages
st.session_state.ai_api_key         # User's AI API key
st.session_state.ai_provider        # Selected provider ("Claude", "OpenAI", "Gemini")
st.session_state.mcp_tools_cache    # Cached MCP tools
st.session_state.glossary           # Current glossary dict (managed by other components)
```

## Architecture

### Main Entry Point

```python
render_ai_chat()
```

This function orchestrates the entire chat interface:
1. Initializes session state
2. Renders API configuration UI
3. Checks prerequisites
4. Displays chat history
5. Handles user input

### Core Functions

#### `_get_ai_response() -> str`
The heart of the component. Handles:
- MCP client initialization
- AI provider initialization
- Message building with context
- Tool call detection and execution
- Response extraction

#### `_handle_tool_calls(...) -> str`
Manages tool execution loop:
- Executes each tool requested by AI
- Displays real-time status
- Formats results for AI provider
- Gets final response after tool execution

#### `_build_system_prompt() -> str`
Constructs context-aware system prompt:
- Glossary statistics
- List of existing terms
- Tool usage guidance

### Provider Integration

Each AI provider has a standardized interface via `AIProviderBase`:

```python
# Initialize provider
provider = ClaudeProvider(api_key)
provider = OpenAIProvider(api_key)
provider = GeminiProvider(api_key)

# Get response with tools
response = provider.chat(messages=messages, tools=tools)

# Extract tool calls
tool_calls = provider.extract_tool_calls(response)

# Format tool results
tool_result = provider.format_tool_result(tool_id, tool_name, result)
```

## Example Conversation Flow

### User Message
```
"Create a new glossary entry for 'MCP' explaining Model Context Protocol"
```

### AI Processing
1. Receives message with system prompt containing:
   - Current glossary has 15 terms
   - Existing terms: API, Bot, Cache, ...
   - Tool usage guidelines

2. Decides to use `create_page` tool with arguments:
   ```json
   {
     "title": "MCP",
     "content": "Model Context Protocol (MCP)...",
     "author_name": "Glossary Bot"
   }
   ```

3. Component executes tool via MCP client:
   - Displays status: "Executing create_page..."
   - Shows result preview
   - Updates status: "create_page completed"

4. AI generates final response:
   ```
   I've created a new glossary entry for "MCP" explaining
   the Model Context Protocol. The page has been published
   to your Telegraph glossary.
   ```

## Error Handling

### Connection Errors
```python
try:
    tools = mcp_client.get_tools_sync()
except Exception as e:
    return f"Error: {str(e)}"  # Displayed in chat
```

### Tool Execution Errors
```python
try:
    result = mcp_client.call_tool_sync(tool_name, tool_input)
except Exception as e:
    results.append({
        "id": tool_id,
        "name": tool_name,
        "result": f"Error: {str(e)}"
    })
```

### API Errors
All AI provider errors are caught and displayed as chat messages.

## Security Considerations

### API Key Storage
- API keys are stored in `st.session_state` only
- Never persisted to disk or URL parameters
- Password field prevents shoulder surfing
- Keys cleared when session ends

### Token Management
- Telegraph token retrieved from `UserSettingsManager`
- Token stored in URL for per-user isolation
- Never exposed in client-side code

### Input Validation
- All tool inputs validated by MCP server
- AI provider handles parameter validation
- Error messages sanitized before display

## Integration with Existing Components

### Settings Panel (`settings_panel.py`)
- Provides Telegraph token via `UserSettingsManager.get_access_token()`
- Sets up `st.session_state.glossary`

### Glossary Manager (`glossary_manager.py`)
- Updates `st.session_state.glossary` when terms are added/edited
- Provides glossary context for AI system prompt

### AI Integration (`ai_integration.py`)
- Can be called from AI Integration tab to add chat interface
- Shares Telegraph token configuration

## Performance Considerations

### Tool Caching
```python
if self._tools_cache:
    return self._tools_cache
```
MCP client caches tool list to avoid repeated queries.

### Session Persistence
Chat history maintained in `st.session_state.chat_messages` for conversation continuity.

### Connection Pooling
Each MCP operation uses fresh connection with proper cleanup via context managers.

## Extending the Component

### Adding New Providers

1. Create provider class implementing `AIProviderBase`
2. Add to imports in `ai_chat.py`
3. Update `_get_provider()` function
4. Add to provider dropdown in `_render_api_config()`

### Custom System Prompts

Modify `_build_system_prompt()` to include additional context:

```python
def _build_system_prompt() -> str:
    glossary = st.session_state.get("glossary", {})
    user_name = st.session_state.get("user_name", "User")

    prompt = f"""You are a helpful assistant for {user_name}.
    Current glossary has {len(glossary)} terms.
    ...
    """
    return prompt
```

### Additional Tools

Tools are automatically discovered from MCP server. To add new tools:
1. Update telegraph-mcp server with new tool
2. Component will automatically detect and make available to AI

## Testing

### Manual Testing Checklist

1. **Prerequisites Check**
   - [ ] Warning shown when Telegraph token missing
   - [ ] Info shown when API key missing

2. **API Configuration**
   - [ ] API key input works (password field)
   - [ ] Provider selection changes active provider
   - [ ] Clear chat button clears history

3. **Chat Functionality**
   - [ ] User messages display correctly
   - [ ] AI responses display correctly
   - [ ] Tool execution status shows

4. **Tool Calls**
   - [ ] Tools execute successfully
   - [ ] Results display in expandable status
   - [ ] Errors handled gracefully
   - [ ] Final summary generated

5. **Multi-Provider Support**
   - [ ] Claude works with tool calls
   - [ ] OpenAI works with tool calls
   - [ ] Gemini works with tool calls

### Automated Testing

Run the test suite:
```bash
python3 test_ai_chat.py
```

Expected output:
```
✓ MCP Client imported
✓ AI Providers imported
✓ User Settings Manager imported
✓ AI Chat component imported
✓ render_ai_chat function exists
...
All tests passed!
```

## Troubleshooting

### "No module named 'streamlit'"
**Solution**: Install dependencies:
```bash
pip install -r requirements.txt
```

### "Failed to connect to telegraph-mcp server"
**Solution**:
1. Check Telegraph token is configured
2. Ensure `npx` is available: `which npx`
3. Test MCP server: `npx telegraph-mcp --version`

### "API key is invalid"
**Solution**:
1. Verify API key is correct for selected provider
2. Check provider status page for outages
3. Ensure API key has proper permissions

### Tool calls not working
**Solution**:
1. Check MCP server logs
2. Verify Telegraph token has write permissions
3. Test tools manually with `test_providers.py`

### Chat history lost
**Cause**: Session state cleared on page reload
**Solution**: This is expected behavior. Consider implementing:
- Local storage persistence
- Export/import chat history
- Session recovery from URL params

## Dependencies

```
streamlit>=1.28.0
mcp>=1.0.0
anthropic>=0.30.0
openai>=1.30.0
google-genai>=1.0.0
```

All dependencies are listed in `/home/ubuntu/projects/telegraph-glossary/requirements.txt`

## Future Enhancements

### Potential Improvements

1. **Streaming Responses**
   - Use `chat_stream()` methods
   - Display tokens as they arrive
   - Better UX for long responses

2. **Conversation Export**
   - Download chat as JSON/Markdown
   - Share conversations via URL
   - Conversation templates

3. **Advanced Features**
   - Multi-turn tool calling
   - Parallel tool execution
   - Tool result caching
   - Conversation branching

4. **Enhanced Context**
   - Include recent edits
   - User preferences
   - Conversation memory
   - RAG integration

5. **Analytics**
   - Token usage tracking
   - Tool call statistics
   - Response time metrics
   - Cost estimation

## Contributing

When modifying the AI Chat component:

1. **Maintain Compatibility**: Ensure changes work with all providers
2. **Test Thoroughly**: Test with each AI provider
3. **Document Changes**: Update this README
4. **Follow Style**: Match existing code patterns
5. **Error Handling**: Add try-except blocks for new features

## License

Part of the Telegraph Glossary project.

## Support

For issues specific to:
- **AI Providers**: Check provider documentation
- **MCP Integration**: See `services/mcp_client.py`
- **Telegraph API**: See Telegraph documentation
- **UI Issues**: Check Streamlit documentation
