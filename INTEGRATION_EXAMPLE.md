# AI Chat Component Integration Example

## Quick Integration

### Add to Main App (app.py)

```python
# At the top with other imports
from components import render_ai_chat

# In your tab structure
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Glossary",
    "Text Processor",
    "Settings",
    "AI Integration",
    "AI Chat"  # New tab
])

# In the tab content section
with tab5:
    render_ai_chat()
```

### Complete Example

```python
import streamlit as st
from components import (
    render_glossary_manager,
    render_text_processor,
    render_settings,
    render_ai_integration,
    render_ai_chat  # Import the new component
)

st.set_page_config(
    page_title="Telegraph Glossary Manager",
    page_icon="📖",
    layout="wide"
)

# Create tabs
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📖 Glossary",
    "✏️ Text Processor",
    "⚙️ Settings",
    "🤖 AI Integration",
    "💬 AI Chat"  # New tab with chat icon
])

with tab1:
    render_glossary_manager()

with tab2:
    render_text_processor()

with tab3:
    render_settings()

with tab4:
    render_ai_integration()

with tab5:
    render_ai_chat()  # Render the AI chat interface
```

## Alternative: Add to AI Integration Tab

If you want to add the chat interface to the existing AI Integration tab instead of creating a new tab:

```python
# In components/ai_integration.py

def render_ai_integration() -> None:
    """Render the AI integration tab."""
    st.header("AI Integration")

    # Existing content...
    st.subheader("MCP Server Configuration")
    _render_mcp_config()

    st.divider()

    # Add the chat interface
    st.subheader("AI Chat Assistant")
    st.markdown("Chat with AI assistants that can manage your glossary using MCP tools.")

    # Import and render the chat component
    from .ai_chat import render_ai_chat
    render_ai_chat()

    st.divider()

    # Rest of existing content...
    st.subheader("Open AI Tools")
    _render_ai_tools()

    st.divider()

    st.subheader("Setup Instructions")
    _render_instructions()
```

## User Flow

### First Time Setup

1. **Configure Telegraph** (Settings tab)
   - User enters Telegraph access token
   - Token saved to URL for persistence

2. **Open AI Chat** (AI Chat tab)
   - Component shows "Please configure your Telegraph token" warning
   - User goes back to Settings

3. **Configure AI Provider** (AI Chat tab)
   - User enters API key (Claude/OpenAI/Gemini)
   - Selects provider from dropdown
   - API key stored in session only

4. **Start Chatting**
   - User types message: "Create a glossary entry for 'API'"
   - AI uses MCP tools to create the page
   - User sees status updates and results

### Returning User

1. **Open App** (with token in URL)
   - Telegraph token auto-loaded
   - Glossary auto-synced

2. **Open AI Chat**
   - User enters API key (not persisted)
   - Start chatting immediately

## Example Conversations

### Create New Term

**User:**
```
Create a glossary entry for "MCP" explaining the Model Context Protocol
```

**AI Response:**
```
I'll create a new glossary entry for MCP.

[Executing create_page...]
[create_page completed]

I've created a new glossary entry for "MCP" that explains the Model
Context Protocol. The entry has been published to your Telegraph glossary
and is now available at: https://telegra.ph/MCP-12-08
```

### Edit Existing Term

**User:**
```
Update the "API" entry to include information about REST APIs
```

**AI Response:**
```
I'll update the API entry with information about REST APIs.

[Executing edit_page...]
[edit_page completed]

I've updated the "API" glossary entry to include information about
REST APIs. The changes have been published to your Telegraph page.
```

### Batch Operations

**User:**
```
Create glossary entries for these terms: JWT, OAuth, CORS
```

**AI Response:**
```
I'll create glossary entries for all three terms.

[Executing create_page for JWT...]
[create_page completed]

[Executing create_page for OAuth...]
[create_page completed]

[Executing create_page for CORS...]
[create_page completed]

I've created three new glossary entries:
1. JWT - JSON Web Token for authentication
2. OAuth - Open Authorization framework
3. CORS - Cross-Origin Resource Sharing

All entries have been published to your Telegraph glossary.
```

## Session State Integration

The AI Chat component integrates seamlessly with existing session state:

```python
# Set by settings_panel.py
st.session_state.glossary = {...}  # Used for context

# Set by user_settings_manager.py
UserSettingsManager.get_access_token()  # Used for MCP client

# Set by ai_chat.py
st.session_state.chat_messages = [...]  # Chat history
st.session_state.ai_api_key = "..."  # User's API key
st.session_state.ai_provider = "Claude"  # Selected provider
```

## Customization Options

### Custom System Prompt

Modify the system prompt to match your use case:

```python
# In components/ai_chat.py, modify _build_system_prompt()

def _build_system_prompt() -> str:
    glossary = st.session_state.get("glossary", {})
    author_name = UserSettingsManager.get_author_name()

    prompt = f"""You are a helpful glossary assistant for {author_name}.

You manage a Telegraph-based glossary with {len(glossary)} terms.

Guidelines:
- Keep entries concise but informative
- Use Markdown formatting
- Add relevant links and examples
- Follow consistent style across entries

Available tools:
- create_page: Create new glossary entries
- edit_page: Update existing entries
- get_page_list: List all pages
- get_page: Get page content
"""
    return prompt
```

### Custom Welcome Message

Add a welcome message when chat is empty:

```python
# In _render_chat_history()

if not st.session_state.chat_messages:
    with st.chat_message("assistant"):
        st.markdown("""
        👋 Hello! I'm your glossary assistant.

        I can help you:
        - Create new glossary entries
        - Edit existing entries
        - Search for terms
        - Organize your glossary

        Try asking me to create a new entry or explain an existing term!
        """)
```

### Provider-Specific Settings

Add model selection for advanced users:

```python
# In _render_api_config()

with st.expander("Advanced Settings"):
    if st.session_state.ai_provider == "Claude":
        model = st.selectbox(
            "Claude Model",
            ["claude-sonnet-4-20250514", "claude-opus-4-5-20251101"]
        )
        st.session_state.claude_model = model

    temperature = st.slider("Temperature", 0.0, 1.0, 0.7)
    st.session_state.temperature = temperature
```

## Error Handling Examples

### Handle Missing Prerequisites

```python
# The component already checks prerequisites
if not _check_prerequisites():
    return  # Shows appropriate warnings

# Add custom handling
def _check_prerequisites() -> bool:
    token = UserSettingsManager.get_access_token()

    if not token:
        st.warning("⚠️ Please configure your Telegraph token first.")
        if st.button("Go to Settings"):
            st.switch_page("pages/settings.py")  # If using pages
        return False

    if not st.session_state.ai_api_key:
        st.info("ℹ️ Enter your AI API key above to start chatting.")
        with st.expander("How to get an API key"):
            st.markdown("""
            **Claude**: [Anthropic Console](https://console.anthropic.com/)
            **OpenAI**: [OpenAI Platform](https://platform.openai.com/)
            **Gemini**: [Google AI Studio](https://makersuite.google.com/)
            """)
        return False

    return True
```

### Handle API Errors Gracefully

```python
# In _get_ai_response()

try:
    response = provider.chat(messages=messages, tools=tools)
except Exception as e:
    error_msg = str(e)

    # Provide helpful error messages
    if "invalid_api_key" in error_msg.lower():
        return "❌ Invalid API key. Please check your API key and try again."
    elif "rate_limit" in error_msg.lower():
        return "⏳ Rate limit reached. Please wait a moment and try again."
    elif "quota" in error_msg.lower():
        return "💳 API quota exceeded. Please check your billing settings."
    else:
        return f"❌ Error: {error_msg}"
```

## Performance Tips

### Cache MCP Tools

```python
# Tools are already cached in TelegraphMCPClient
# But you can add session-level caching:

if "mcp_tools" not in st.session_state:
    mcp_client = TelegraphMCPClient(token)
    st.session_state.mcp_tools = mcp_client.get_tools_sync()

tools = st.session_state.mcp_tools
```

### Lazy Load Providers

```python
# Only import providers when needed
def _get_provider():
    provider_name = st.session_state.ai_provider

    if provider_name == "Claude":
        from services.ai_providers import ClaudeProvider
        return ClaudeProvider(st.session_state.ai_api_key)
    # ... etc
```

### Limit Chat History

```python
# Prevent memory issues with very long chats
def _init_chat_state():
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []

    # Limit to last 50 messages
    if len(st.session_state.chat_messages) > 50:
        st.session_state.chat_messages = st.session_state.chat_messages[-50:]
```

## Testing the Integration

### Manual Test Steps

1. Start the app:
   ```bash
   streamlit run app.py
   ```

2. Configure Telegraph token in Settings tab

3. Navigate to AI Chat tab

4. Enter API key and select provider

5. Test basic conversation:
   ```
   "Hello, what can you help me with?"
   ```

6. Test tool calling:
   ```
   "Create a test entry for the term 'testing'"
   ```

7. Verify in Glossary tab that entry was created

### Integration Test Script

```python
# test_integration.py
import streamlit as st
from components import render_ai_chat

# Mock session state
st.session_state.glossary = {"API": {...}, "Bot": {...}}
st.session_state.ai_api_key = "test_key"
st.session_state.ai_provider = "Claude"

# Mock user settings
from services.user_settings_manager import UserSettingsManager
UserSettingsManager.set_access_token("test_token")

# Render component (in test mode)
render_ai_chat()
```

## Deployment Considerations

### Environment Variables

Set up environment variables for production:

```bash
# .env.example
TELEGRAPH_ACCESS_TOKEN=your_token_here
ANTHROPIC_API_KEY=your_key_here  # Optional default
OPENAI_API_KEY=your_key_here     # Optional default
```

### Security Best Practices

1. **API Keys**: Never commit API keys to version control
2. **Token Storage**: Use encrypted storage for production
3. **Rate Limiting**: Implement rate limiting per user
4. **Input Sanitization**: Validate all user inputs
5. **Error Logging**: Log errors without exposing secrets

### Scalability

For multi-user deployments:

```python
# Use user-specific session state
user_id = st.session_state.get("user_id")
chat_key = f"chat_messages_{user_id}"
st.session_state[chat_key] = [...]
```

## Support and Documentation

- **Component Docs**: `/components/AI_CHAT_README.md`
- **MCP Client**: `/services/mcp_client.py`
- **AI Providers**: `/services/ai_providers/`
- **User Settings**: `/services/user_settings_manager.py`

## Next Steps

After integrating the AI Chat component:

1. **Test with Users**: Get feedback on the chat interface
2. **Monitor Usage**: Track which features are most used
3. **Optimize Prompts**: Improve system prompts based on results
4. **Add Features**: Consider streaming, export, analytics
5. **Document Patterns**: Share common conversation patterns

Happy chatting! 🤖💬
