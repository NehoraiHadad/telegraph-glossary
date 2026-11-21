# MCP Integration Implementation Plan

## Overview

מימוש אינטגרציית MCP Client לאפליקציית Telegraph Glossary, המאפשרת ניהול גלוסרי באמצעות AI עם לחיצת כפתור.

---

## Architecture

```
+-------------------+     +------------------+     +------------------+
|   Streamlit UI    |     |   MCP Client     |     |  telegraph-mcp   |
|  (ai_chat.py)     |<--->|  (mcp_client.py) |<--->|  (npm server)    |
+-------------------+     +------------------+     +------------------+
        |                         |
        v                         v
+-------------------+     +------------------+
|  AI Provider      |     |  Tool Bridge     |
|  Abstraction      |<--->| MCP<->Provider   |
+-------------------+     +------------------+
```

---

## Phase 1: MCP Client Infrastructure

### Agent: backend-architect
**Goal:** יצירת MCP Client שמתחבר ל-telegraph-mcp server

### Files to Create:
- `services/mcp_client.py` - MCP connection manager

### Tasks:
1. Install MCP SDK dependency
2. Create `TelegraphMCPClient` class with:
   - Connection management via stdio
   - Tool discovery and caching
   - Sync wrappers for async operations
   - Error handling and reconnection
3. Test connection to telegraph-mcp

### Dependencies:
```
mcp>=1.0.0
anyio>=4.0.0
```

---

## Phase 2: AI Provider Abstraction Layer

### Agent: backend-architect
**Goal:** יצירת שכבת הפשטה לספקי AI שונים

### Files to Create:
- `services/ai_providers/__init__.py`
- `services/ai_providers/base.py` - Abstract base class
- `services/ai_providers/claude_provider.py` - Claude implementation
- `services/ai_providers/openai_provider.py` - OpenAI implementation
- `services/ai_providers/gemini_provider.py` - Gemini implementation (optional)

### Tasks:
1. Create `AIProviderBase` abstract class with:
   - `chat()` - Send message with tools
   - `chat_stream()` - Stream response
   - `convert_tools_format()` - MCP to provider format
   - `extract_tool_calls()` - Parse tool calls from response

2. Implement `ClaudeProvider`:
   - Native tool format (input_schema)
   - Handle `stop_reason: "tool_use"`
   - Message streaming support

3. Implement `OpenAIProvider`:
   - Function calling format (parameters)
   - Handle `tool_calls` in response

4. (Optional) Implement `GeminiProvider`

### Dependencies:
```
anthropic>=0.30.0
openai>=1.30.0
google-genai>=1.0.0  # optional
```

---

## Phase 3: AI Chat UI Component

### Agent: senior-frontend-dev
**Goal:** יצירת ממשק צ'אט AI ב-Streamlit

### Files to Create/Modify:
- `components/ai_chat.py` - New chat interface
- `components/ai_integration.py` - Update to include chat

### Tasks:
1. Create chat UI with:
   - Message history display (st.chat_message)
   - Chat input (st.chat_input)
   - Streaming response display
   - Tool execution status indicators

2. Session state management:
   - `chat_messages` - Conversation history
   - `ai_api_key` - User's API key (per session)
   - `ai_provider` - Selected provider

3. API key input:
   - Password field in sidebar
   - Provider selection dropdown
   - Key validation

4. Tool execution loop:
   - Send user message + tools to AI
   - If AI requests tool: execute via MCP
   - Send tool result back to AI
   - Display final response

5. Error handling:
   - API key errors
   - MCP connection errors
   - Tool execution errors
   - Rate limiting

---

## Phase 4: Integration & Polish

### Agent: senior-frontend-dev
**Goal:** שילוב הכל יחד ושיפור UX

### Files to Modify:
- `app.py` - Add AI chat to tabs
- `components/ai_integration.py` - Combine config + chat
- `requirements.txt` - Add all dependencies

### Tasks:
1. Update `ai_integration.py` to include:
   - Existing MCP config display
   - NEW: Embedded AI chat interface
   - Provider selection
   - API key management

2. Add system prompt with glossary context:
   - Current glossary terms
   - Available MCP tools
   - Usage guidelines

3. Clear chat / Export history buttons

4. Usage monitoring / token display

---

## Implementation Order

```
Phase 1 (MCP Client)
    |
    v
Phase 2 (AI Providers)
    |
    v
Phase 3 (Chat UI)
    |
    v
Phase 4 (Integration)
```

### Parallel Opportunities:
- Phase 1 + Phase 2 can start in parallel (no dependencies)
- Phase 3 depends on both Phase 1 and Phase 2
- Phase 4 depends on Phase 3

---

## Agent Assignments

| Phase | Agent Type | Responsibility |
|-------|------------|----------------|
| 1 | backend-architect | MCP Client infrastructure |
| 2 | backend-architect | AI Provider abstraction |
| 3 | senior-frontend-dev | Chat UI component |
| 4 | senior-frontend-dev | Integration and polish |

---

## Shared Context for All Agents

### Project Structure:
```
telegraph-glossary/
├── app.py                    # Main Streamlit app
├── components/
│   ├── ai_integration.py     # AI tab (update this)
│   ├── ai_chat.py            # NEW: Chat interface
│   ├── glossary_manager.py
│   ├── settings_panel.py
│   └── ...
├── services/
│   ├── mcp_client.py         # NEW: MCP connection
│   ├── ai_providers/         # NEW: AI provider layer
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── claude_provider.py
│   │   └── openai_provider.py
│   ├── telegraph_service.py
│   ├── user_settings_manager.py
│   └── ...
└── requirements.txt
```

### Key Interfaces:
- `UserSettingsManager.get_access_token()` - Telegraph token
- `st.session_state.glossary` - Current glossary dict
- `st.session_state.ai_api_key` - User's AI API key (new)

### Security Notes:
- AI API keys stored in session only (not URL)
- Telegraph token already in URL (existing)
- Never log API keys

---

## Success Criteria

1. User can enter AI API key in sidebar
2. User can select AI provider (Claude/OpenAI)
3. Chat interface shows message history
4. User can ask AI to manage glossary
5. AI executes MCP tools correctly
6. Results display properly in UI
7. Errors handled gracefully

---

## Testing Plan

1. **Unit Tests:**
   - MCP client connection
   - Tool format conversion
   - Provider response parsing

2. **Integration Tests:**
   - Full chat flow with mock MCP
   - Tool execution chain

3. **Manual Tests:**
   - Create page via chat
   - Edit page via chat
   - List pages via chat
