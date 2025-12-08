#!/usr/bin/env python3
"""Standalone validation script for AI providers.

This script validates the provider implementations without requiring
the full application dependencies.
"""

import sys
import os

# Add parent directory to path to import providers directly
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base import AIProviderBase
from claude_provider import ClaudeProvider
from openai_provider import OpenAIProvider


def validate_interface():
    """Validate that all required methods exist in base class."""
    required_methods = [
        'chat',
        'chat_stream',
        'convert_tools_format',
        'extract_tool_calls',
        'format_tool_result',
        'get_model_name'
    ]

    print("Validating base interface...")
    for method in required_methods:
        if not hasattr(AIProviderBase, method):
            print(f"  ✗ Missing method: {method}")
            return False
        print(f"  ✓ {method}")

    return True


def validate_claude():
    """Validate Claude provider implementation."""
    print("\nValidating Claude provider...")

    provider = ClaudeProvider(api_key="test-key")
    print(f"  ✓ Model: {provider.model}")

    # Test tool conversion (should be no-op)
    mcp_tools = [{
        "name": "test",
        "description": "Test tool",
        "input_schema": {"type": "object", "properties": {}}
    }]

    converted = provider.convert_tools_format(mcp_tools)
    if converted == mcp_tools:
        print("  ✓ Tool conversion (MCP native)")
    else:
        print("  ✗ Tool conversion failed")
        return False

    # Test tool result format
    result = provider.format_tool_result("id_123", "result")
    if result["role"] == "user" and result["content"][0]["type"] == "tool_result":
        print("  ✓ Tool result formatting")
    else:
        print("  ✗ Tool result formatting failed")
        return False

    return True


def validate_openai():
    """Validate OpenAI provider implementation."""
    print("\nValidating OpenAI provider...")

    provider = OpenAIProvider(api_key="test-key")
    print(f"  ✓ Model: {provider.model}")

    # Test tool conversion (should convert input_schema to parameters)
    mcp_tools = [{
        "name": "test",
        "description": "Test tool",
        "input_schema": {
            "type": "object",
            "properties": {"param": {"type": "string"}}
        }
    }]

    converted = provider.convert_tools_format(mcp_tools)
    if (converted[0]["type"] == "function" and
        "parameters" in converted[0]["function"] and
        "input_schema" not in converted[0]["function"]):
        print("  ✓ Tool conversion (input_schema -> parameters)")
    else:
        print("  ✗ Tool conversion failed")
        return False

    # Test tool result format
    result = provider.format_tool_result("call_123", "result")
    if result["role"] == "tool" and result["tool_call_id"] == "call_123":
        print("  ✓ Tool result formatting")
    else:
        print("  ✗ Tool result formatting failed")
        return False

    return True


def validate_normalization():
    """Validate that both providers return normalized format."""
    print("\nValidating normalized format...")

    claude = ClaudeProvider(api_key="test")
    openai = OpenAIProvider(api_key="test")

    # Claude response
    claude_resp = {
        "stop_reason": "tool_use",
        "content": [{
            "type": "tool_use",
            "id": "id_1",
            "name": "test_tool",
            "input": {"param": "value"}
        }]
    }

    # OpenAI response
    openai_resp = {
        "choices": [{
            "message": {
                "tool_calls": [{
                    "id": "id_1",
                    "type": "function",
                    "function": {
                        "name": "test_tool",
                        "arguments": '{"param": "value"}'
                    }
                }]
            }
        }]
    }

    claude_calls = claude.extract_tool_calls(claude_resp)
    openai_calls = openai.extract_tool_calls(openai_resp)

    if (claude_calls and openai_calls and
        set(claude_calls[0].keys()) == set(openai_calls[0].keys()) and
        set(claude_calls[0].keys()) == {"id", "name", "input"}):
        print("  ✓ Both providers return normalized format")
        print(f"    Format: {list(claude_calls[0].keys())}")
        return True
    else:
        print("  ✗ Normalized format validation failed")
        return False


def main():
    """Run all validations."""
    print("=" * 60)
    print("AI Provider Abstraction Layer - Validation")
    print("=" * 60)

    results = [
        validate_interface(),
        validate_claude(),
        validate_openai(),
        validate_normalization()
    ]

    print("\n" + "=" * 60)
    if all(results):
        print("✓ All validations passed!")
        print("=" * 60)
        return 0
    else:
        print("✗ Some validations failed")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
