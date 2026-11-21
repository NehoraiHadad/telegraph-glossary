#!/usr/bin/env python3
"""Test script for AI Chat component with PydanticAI.

This script verifies that the PydanticAI-based AI chat component
and all dependencies are properly imported and configured.
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_imports():
    """Test that all required modules can be imported."""
    print("Testing imports...")

    try:
        from services.pydantic_ai_service import TelegraphAIService, can_use_mcp
        print("✓ PydanticAI Service imported")
    except Exception as e:
        print(f"✗ PydanticAI Service import failed: {e}")
        return False

    try:
        from services.direct_telegraph_tools import DirectTelegraphTools
        print("✓ Direct Telegraph Tools imported")
    except Exception as e:
        print(f"✗ Direct Telegraph Tools import failed: {e}")
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

        # Check that private functions exist (simplified version)
        private_functions = [
            '_init_chat_state',
            '_render_api_config',
            '_check_prerequisites',
            '_render_chat_history',
            '_handle_chat_input',
        ]

        for func_name in private_functions:
            assert hasattr(ai_chat, func_name), f"Missing {func_name} function"
            print(f"✓ {func_name} function exists")

        print("\nComponent structure is valid!")
        return True

    except Exception as e:
        print(f"✗ Component structure test failed: {e}")
        return False


def test_pydantic_ai_service():
    """Test that PydanticAI service is properly configured."""
    print("\nTesting PydanticAI service...")

    try:
        from services.pydantic_ai_service import TelegraphAIService, MODEL_NAMES, can_use_mcp

        # Check model names are defined
        assert "Claude" in MODEL_NAMES, "Missing Claude model"
        assert "OpenAI" in MODEL_NAMES, "Missing OpenAI model"
        assert "Gemini" in MODEL_NAMES, "Missing Gemini model"
        print("✓ All model names defined")

        # Check MCP detection works
        mcp_available = can_use_mcp()
        print(f"✓ MCP detection: {'available' if mcp_available else 'not available'}")

        print("\nPydanticAI service configuration valid!")
        return True

    except Exception as e:
        print(f"✗ PydanticAI service test failed: {e}")
        return False


def test_direct_tools():
    """Test that direct Telegraph tools are properly defined."""
    print("\nTesting direct Telegraph tools...")

    try:
        from services.direct_telegraph_tools import DirectTelegraphTools, TELEGRAPH_TOOLS

        # Check tools are defined
        tool_names = [t["name"] for t in TELEGRAPH_TOOLS]
        expected_tools = ["create_page", "edit_page", "get_page", "get_page_list", "get_account_info", "get_views"]

        for tool in expected_tools:
            assert tool in tool_names, f"Missing tool: {tool}"
            print(f"✓ Tool defined: {tool}")

        print("\nDirect Telegraph tools valid!")
        return True

    except Exception as e:
        print(f"✗ Direct tools test failed: {e}")
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("AI Chat Component Test Suite (PydanticAI)")
    print("=" * 60)

    results = []

    results.append(("Imports", test_imports()))
    results.append(("Component Structure", test_component_structure()))
    results.append(("PydanticAI Service", test_pydantic_ai_service()))
    results.append(("Direct Tools", test_direct_tools()))

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
