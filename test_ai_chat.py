#!/usr/bin/env python3
"""Test script for AI Chat component.

This script demonstrates the AI chat component integration
and verifies that all dependencies are properly imported.
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test that all required modules can be imported."""
    print("Testing imports...")

    try:
        from services.mcp_client import TelegraphMCPClient
        print("✓ MCP Client imported")
    except Exception as e:
        print(f"✗ MCP Client import failed: {e}")
        return False

    try:
        from services.ai_providers import ClaudeProvider, OpenAIProvider, GeminiProvider
        print("✓ AI Providers imported")
    except Exception as e:
        print(f"✗ AI Providers import failed: {e}")
        return False

    try:
        from services.user_settings_manager import UserSettingsManager
        print("✓ User Settings Manager imported")
    except Exception as e:
        print(f"✗ User Settings Manager import failed: {e}")
        return False

    try:
        from components.ai_chat import render_ai_chat
        print("✓ AI Chat component imported")
    except Exception as e:
        print(f"✗ AI Chat component import failed: {e}")
        return False

    print("\nAll imports successful!")
    return True


def test_component_structure():
    """Test that the component has all required functions."""
    print("\nTesting component structure...")

    try:
        from components import ai_chat

        # Check that main render function exists
        assert hasattr(ai_chat, 'render_ai_chat'), "Missing render_ai_chat function"
        print("✓ render_ai_chat function exists")

        # Check that private functions exist
        private_functions = [
            '_init_chat_state',
            '_render_api_config',
            '_check_prerequisites',
            '_render_chat_history',
            '_handle_chat_input',
            '_get_ai_response',
            '_get_provider',
            '_build_messages_for_ai',
            '_build_system_prompt',
            '_handle_tool_calls',
            '_extract_text_response'
        ]

        for func_name in private_functions:
            assert hasattr(ai_chat, func_name), f"Missing {func_name} function"
            print(f"✓ {func_name} function exists")

        print("\nComponent structure is valid!")
        return True

    except Exception as e:
        print(f"✗ Component structure test failed: {e}")
        return False


def test_provider_initialization():
    """Test that AI providers can be initialized with dummy keys."""
    print("\nTesting AI provider initialization...")

    try:
        from services.ai_providers import ClaudeProvider, OpenAIProvider, GeminiProvider

        # Test with dummy API keys (won't make actual calls)
        dummy_key = "test_key_12345"

        claude = ClaudeProvider(dummy_key)
        print(f"✓ Claude Provider initialized (model: {claude.get_model_name()})")

        openai = OpenAIProvider(dummy_key)
        print(f"✓ OpenAI Provider initialized (model: {openai.get_model_name()})")

        gemini = GeminiProvider(dummy_key)
        print(f"✓ Gemini Provider initialized (model: {gemini.get_model_name()})")

        print("\nAll providers initialized successfully!")
        return True

    except Exception as e:
        print(f"✗ Provider initialization failed: {e}")
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("AI Chat Component Test Suite")
    print("=" * 60)

    results = []

    results.append(("Imports", test_imports()))
    results.append(("Component Structure", test_component_structure()))
    results.append(("Provider Initialization", test_provider_initialization()))

    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)

    for test_name, passed in results:
        status = "PASSED" if passed else "FAILED"
        symbol = "✓" if passed else "✗"
        print(f"{symbol} {test_name}: {status}")

    all_passed = all(result[1] for result in results)
    print("\n" + "=" * 60)
    if all_passed:
        print("All tests passed!")
    else:
        print("Some tests failed!")
    print("=" * 60)

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
