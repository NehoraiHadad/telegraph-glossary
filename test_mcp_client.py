"""
Test script for TelegraphMCPClient.

This script demonstrates how to use the TelegraphMCPClient to interact
with the telegraph-mcp server.

Usage:
    python test_mcp_client.py

Note: Requires TELEGRAPH_ACCESS_TOKEN to be set or passed via command line.
"""

import sys
import json
from services.mcp_client import TelegraphMCPClient


def main():
    """Test the MCP client functionality."""
    # Get access token from command line or prompt
    if len(sys.argv) > 1:
        access_token = sys.argv[1]
    else:
        access_token = input("Enter your Telegraph access token: ").strip()

    if not access_token:
        print("Error: Access token is required")
        sys.exit(1)

    try:
        # Initialize client
        print("\n1. Initializing TelegraphMCPClient...")
        client = TelegraphMCPClient(access_token=access_token)
        print(f"   Client: {client}")

        # Get available tools
        print("\n2. Fetching available tools...")
        tools = client.get_tools_sync()
        print(f"   Found {len(tools)} tools:")
        for tool in tools:
            print(f"   - {tool['name']}: {tool['description']}")

        # Example: Get account info
        print("\n3. Testing 'get_account_info' tool...")
        account_info = client.call_tool_sync("get_account_info", {})
        print(f"   Result: {json.dumps(account_info, indent=2)}")

        # Example: Get page list
        print("\n4. Testing 'get_page_list' tool...")
        page_list = client.call_tool_sync("get_page_list", {"limit": 5})
        print(f"   Result: {json.dumps(page_list, indent=2)}")

        print("\n✓ All tests passed!")

    except Exception as e:
        print(f"\n✗ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
