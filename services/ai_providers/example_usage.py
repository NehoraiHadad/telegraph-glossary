"""Example usage of AI Provider abstraction layer.

This demonstrates how to use the AI providers with MCP tools.
"""

from typing import List, Dict, Any

# Example MCP tools (from telegraph-mcp server)
EXAMPLE_MCP_TOOLS = [
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
                    "type": "array",
                    "description": "Page content as Node array"
                }
            },
            "required": ["title", "content"]
        }
    },
    {
        "name": "edit_page",
        "description": "Edit an existing Telegraph page",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Page path"
                },
                "title": {
                    "type": "string",
                    "description": "New title"
                },
                "content": {
                    "type": "array",
                    "description": "New content"
                }
            },
            "required": ["path", "title", "content"]
        }
    }
]


def example_claude_usage():
    """Example: Using Claude provider."""
    from .claude_provider import ClaudeProvider

    # Initialize provider
    provider = ClaudeProvider(api_key="your-api-key")

    # Convert tools to Claude format (no-op, already compatible!)
    claude_tools = provider.convert_tools_format(EXAMPLE_MCP_TOOLS)
    print(f"Claude tools: {len(claude_tools)} tools")

    # Prepare messages
    messages = [
        {
            "role": "user",
            "content": "Create a new page titled 'Test' with content 'Hello World'"
        }
    ]

    # Send chat request with tools
    response = provider.chat(messages, tools=claude_tools)

    # Extract tool calls if any
    tool_calls = provider.extract_tool_calls(response)
    if tool_calls:
        print(f"Claude wants to call: {tool_calls[0]['name']}")

        # Format tool result
        tool_result = provider.format_tool_result(
            tool_calls[0]["id"],
            '{"success": true, "path": "Test-12-31"}'
        )
        print(f"Tool result message: {tool_result['role']}")


def example_openai_usage():
    """Example: Using OpenAI provider."""
    from .openai_provider import OpenAIProvider

    # Initialize provider
    provider = OpenAIProvider(api_key="your-api-key")

    # Convert tools to OpenAI format (input_schema -> parameters)
    openai_tools = provider.convert_tools_format(EXAMPLE_MCP_TOOLS)
    print(f"OpenAI tools: {len(openai_tools)} tools")
    print(f"First tool structure: {openai_tools[0]['type']}")

    # Prepare messages
    messages = [
        {
            "role": "user",
            "content": "Create a new page titled 'Test' with content 'Hello World'"
        }
    ]

    # Send chat request with tools
    response = provider.chat(messages, tools=openai_tools)

    # Extract tool calls if any
    tool_calls = provider.extract_tool_calls(response)
    if tool_calls:
        print(f"OpenAI wants to call: {tool_calls[0]['name']}")

        # Format tool result
        tool_result = provider.format_tool_result(
            tool_calls[0]["id"],
            '{"success": true, "path": "Test-12-31"}'
        )
        print(f"Tool result message: {tool_result['role']}")


def example_streaming():
    """Example: Streaming responses."""
    from .claude_provider import ClaudeProvider

    provider = ClaudeProvider(api_key="your-api-key")

    messages = [
        {
            "role": "user",
            "content": "Write a short poem about Telegraph"
        }
    ]

    print("Streaming response:")
    for chunk in provider.chat_stream(messages):
        print(chunk, end="", flush=True)
    print()


def example_tool_execution_loop():
    """Example: Full tool execution loop.

    This demonstrates the typical flow:
    1. User sends message
    2. AI responds with tool calls
    3. Execute tools via MCP
    4. Send results back to AI
    5. AI provides final response
    """
    from .claude_provider import ClaudeProvider

    provider = ClaudeProvider(api_key="your-api-key")

    # Step 1: Initial user message
    messages = [
        {
            "role": "user",
            "content": "Create a page called 'Getting Started' with some intro content"
        }
    ]

    # Step 2: AI responds with tool call
    response = provider.chat(messages, tools=EXAMPLE_MCP_TOOLS)

    # Extract assistant message
    messages.append({
        "role": "assistant",
        "content": response["content"]
    })

    # Step 3: Check for tool calls
    tool_calls = provider.extract_tool_calls(response)

    if tool_calls:
        for tool_call in tool_calls:
            print(f"Executing tool: {tool_call['name']}")
            print(f"With input: {tool_call['input']}")

            # Step 4: Execute tool (via MCP client - not shown)
            # result = mcp_client.call_tool(tool_call['name'], tool_call['input'])
            mock_result = '{"success": true, "path": "Getting-Started-12-31"}'

            # Format and add tool result to conversation
            tool_result = provider.format_tool_result(tool_call["id"], mock_result)
            messages.append(tool_result)

        # Step 5: Get final AI response
        final_response = provider.chat(messages)
        print(f"Final response: {final_response['content'][0]['text']}")


if __name__ == "__main__":
    print("AI Provider Usage Examples")
    print("=" * 50)
    print("\nNOTE: These are demonstrations only.")
    print("Replace 'your-api-key' with actual API keys to run.\n")

    print("\n1. Claude Provider")
    print("-" * 50)
    print("Claude uses input_schema (MCP native format)")

    print("\n2. OpenAI Provider")
    print("-" * 50)
    print("OpenAI uses parameters (converted from input_schema)")

    print("\n3. Tool Execution Flow")
    print("-" * 50)
    print("User -> AI -> Tool Call -> Execute -> Result -> AI -> Response")
