"""Test script for AI provider abstraction layer.

This script validates that all providers implement the required interface
and that tool format conversion works correctly.
"""

from typing import Dict, Any, List


def test_base_interface():
    """Test that base class defines required interface."""
    from .base import AIProviderBase

    # Check required methods exist
    required_methods = [
        'chat',
        'chat_stream',
        'convert_tools_format',
        'extract_tool_calls',
        'format_tool_result',
        'get_model_name'
    ]

    for method in required_methods:
        assert hasattr(AIProviderBase, method), f"Missing method: {method}"

    print("✓ Base interface validation passed")


def test_claude_provider():
    """Test Claude provider implementation."""
    from .claude_provider import ClaudeProvider

    # Test initialization (without actual API key)
    try:
        provider = ClaudeProvider(api_key="test-key")
        assert provider.model == "claude-sonnet-4-20250514"
        print(f"✓ Claude provider initialized with model: {provider.model}")
    except Exception as e:
        print(f"✗ Claude provider initialization failed: {e}")
        return False

    # Test tool conversion (Claude uses MCP format natively)
    mcp_tools = [
        {
            "name": "test_tool",
            "description": "A test tool",
            "input_schema": {
                "type": "object",
                "properties": {
                    "param": {"type": "string"}
                }
            }
        }
    ]

    converted = provider.convert_tools_format(mcp_tools)
    assert converted == mcp_tools, "Claude should not modify MCP tools"
    print("✓ Claude tool conversion (no-op) works correctly")

    # Test tool result formatting
    tool_result = provider.format_tool_result("test_id", "test_result")
    assert tool_result["role"] == "user"
    assert tool_result["content"][0]["type"] == "tool_result"
    assert tool_result["content"][0]["tool_use_id"] == "test_id"
    print("✓ Claude tool result formatting works correctly")

    return True


def test_openai_provider():
    """Test OpenAI provider implementation."""
    from .openai_provider import OpenAIProvider

    # Test initialization (without actual API key)
    try:
        provider = OpenAIProvider(api_key="test-key")
        assert provider.model == "gpt-4o"
        print(f"✓ OpenAI provider initialized with model: {provider.model}")
    except Exception as e:
        print(f"✗ OpenAI provider initialization failed: {e}")
        return False

    # Test tool conversion (OpenAI needs conversion)
    mcp_tools = [
        {
            "name": "test_tool",
            "description": "A test tool",
            "input_schema": {
                "type": "object",
                "properties": {
                    "param": {"type": "string"}
                },
                "required": ["param"]
            }
        }
    ]

    converted = provider.convert_tools_format(mcp_tools)

    # Verify OpenAI format
    assert len(converted) == 1
    assert converted[0]["type"] == "function"
    assert converted[0]["function"]["name"] == "test_tool"
    assert "parameters" in converted[0]["function"]
    assert "input_schema" not in converted[0]["function"]
    print("✓ OpenAI tool conversion (input_schema -> parameters) works correctly")

    # Test tool result formatting
    tool_result = provider.format_tool_result("test_id", "test_result")
    assert tool_result["role"] == "tool"
    assert tool_result["tool_call_id"] == "test_id"
    assert tool_result["content"] == "test_result"
    print("✓ OpenAI tool result formatting works correctly")

    return True


def test_tool_extraction():
    """Test tool call extraction from responses."""
    from .claude_provider import ClaudeProvider
    from .openai_provider import OpenAIProvider

    # Claude response format
    claude_provider = ClaudeProvider(api_key="test")
    claude_response = {
        "stop_reason": "tool_use",
        "content": [
            {
                "type": "text",
                "text": "I'll create that page for you."
            },
            {
                "type": "tool_use",
                "id": "toolu_123",
                "name": "create_page",
                "input": {"title": "Test", "content": []}
            }
        ]
    }

    claude_calls = claude_provider.extract_tool_calls(claude_response)
    assert claude_calls is not None
    assert len(claude_calls) == 1
    assert claude_calls[0]["id"] == "toolu_123"
    assert claude_calls[0]["name"] == "create_page"
    assert claude_calls[0]["input"]["title"] == "Test"
    print("✓ Claude tool extraction works correctly")

    # OpenAI response format
    openai_provider = OpenAIProvider(api_key="test")
    openai_response = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "I'll create that page for you.",
                    "tool_calls": [
                        {
                            "id": "call_123",
                            "type": "function",
                            "function": {
                                "name": "create_page",
                                "arguments": '{"title": "Test", "content": []}'
                            }
                        }
                    ]
                }
            }
        ]
    }

    openai_calls = openai_provider.extract_tool_calls(openai_response)
    assert openai_calls is not None
    assert len(openai_calls) == 1
    assert openai_calls[0]["id"] == "call_123"
    assert openai_calls[0]["name"] == "create_page"
    assert openai_calls[0]["input"]["title"] == "Test"
    print("✓ OpenAI tool extraction works correctly")


def test_normalized_format():
    """Test that both providers return normalized tool call format."""
    from .claude_provider import ClaudeProvider
    from .openai_provider import OpenAIProvider

    # Both providers should return the same normalized format
    expected_format = {
        "id": str,
        "name": str,
        "input": dict
    }

    # Test with mock responses
    claude_provider = ClaudeProvider(api_key="test")
    openai_provider = OpenAIProvider(api_key="test")

    claude_response = {
        "stop_reason": "tool_use",
        "content": [
            {
                "type": "tool_use",
                "id": "test_id",
                "name": "test_tool",
                "input": {"param": "value"}
            }
        ]
    }

    openai_response = {
        "choices": [
            {
                "message": {
                    "tool_calls": [
                        {
                            "id": "test_id",
                            "type": "function",
                            "function": {
                                "name": "test_tool",
                                "arguments": '{"param": "value"}'
                            }
                        }
                    ]
                }
            }
        ]
    }

    claude_calls = claude_provider.extract_tool_calls(claude_response)
    openai_calls = openai_provider.extract_tool_calls(openai_response)

    # Both should have the same structure
    assert set(claude_calls[0].keys()) == set(openai_calls[0].keys())
    assert claude_calls[0]["name"] == openai_calls[0]["name"]
    assert claude_calls[0]["input"] == openai_calls[0]["input"]

    print("✓ Both providers return normalized tool call format")


def run_all_tests():
    """Run all validation tests."""
    print("=" * 60)
    print("AI Provider Abstraction Layer - Validation Tests")
    print("=" * 60)
    print()

    tests = [
        ("Base Interface", test_base_interface),
        ("Claude Provider", test_claude_provider),
        ("OpenAI Provider", test_openai_provider),
        ("Tool Extraction", test_tool_extraction),
        ("Normalized Format", test_normalized_format)
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        print(f"\nTesting: {name}")
        print("-" * 60)
        try:
            result = test_func()
            if result is None or result is True:
                passed += 1
                print(f"✓ {name} tests passed\n")
            else:
                failed += 1
                print(f"✗ {name} tests failed\n")
        except Exception as e:
            failed += 1
            print(f"✗ {name} tests failed with error: {e}\n")

    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
