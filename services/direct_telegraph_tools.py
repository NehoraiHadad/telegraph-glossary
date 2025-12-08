"""
Direct Telegraph Tools - Python-native tool execution without MCP.

This module provides a drop-in replacement for TelegraphMCPClient that
calls the Telegraph API directly using TelegraphService. No Node.js required!

Use this for environments like Streamlit Cloud where npx is not available.
"""

import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from services.telegraph_service import TelegraphService

logger = logging.getLogger(__name__)


# Tool definitions matching telegraph-mcp format
TELEGRAPH_TOOLS = [
    {
        "name": "create_page",
        "description": "Create a new Telegraph page with the given title and content. Content can be in Markdown or HTML format.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "The title of the page"
                },
                "content": {
                    "type": "string",
                    "description": "The content of the page (Markdown or HTML)"
                },
                "author_name": {
                    "type": "string",
                    "description": "Author name to display on the page"
                }
            },
            "required": ["title", "content"]
        }
    },
    {
        "name": "edit_page",
        "description": "Edit an existing Telegraph page. Requires the page path.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The path of the page to edit (e.g., 'My-Page-01-01')"
                },
                "title": {
                    "type": "string",
                    "description": "New title for the page"
                },
                "content": {
                    "type": "string",
                    "description": "New content for the page (Markdown or HTML)"
                },
                "author_name": {
                    "type": "string",
                    "description": "Author name to display on the page"
                }
            },
            "required": ["path", "title", "content"]
        }
    },
    {
        "name": "get_page",
        "description": "Get the content of an existing Telegraph page.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The path of the page to retrieve"
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "get_page_list",
        "description": "Get a list of pages in the current Telegraph account.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of pages to return (default: 50)"
                },
                "offset": {
                    "type": "integer",
                    "description": "Number of pages to skip (for pagination)"
                }
            }
        }
    },
    {
        "name": "get_account_info",
        "description": "Get information about the current Telegraph account.",
        "input_schema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "get_views",
        "description": "Get the number of views for a Telegraph page.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The path of the page"
                },
                "year": {
                    "type": "integer",
                    "description": "Year for view statistics (optional)"
                },
                "month": {
                    "type": "integer",
                    "description": "Month for view statistics (optional)"
                },
                "day": {
                    "type": "integer",
                    "description": "Day for view statistics (optional)"
                }
            },
            "required": ["path"]
        }
    }
]


class DirectTelegraphTools:
    """
    Direct Telegraph API tools without MCP dependency.

    This class provides the same interface as TelegraphMCPClient but
    executes tools directly using the Telegraph Python library.
    Perfect for Streamlit Cloud and other environments without Node.js.

    Example:
        ```python
        tools_client = DirectTelegraphTools(access_token="your_token")

        # Get available tools
        tools = tools_client.get_tools_sync()

        # Create a page
        result = tools_client.call_tool_sync("create_page", {
            "title": "API",
            "content": "Application Programming Interface"
        })
        ```
    """

    def __init__(self, access_token: str):
        """
        Initialize the direct tools client.

        Args:
            access_token: Telegraph access token for API authentication
        """
        if not access_token:
            raise ValueError("Telegraph access token is required")

        self.access_token = access_token
        self.service = TelegraphService(access_token)
        self._tools_cache = None

        logger.info("DirectTelegraphTools initialized (no MCP required)")

    def get_tools_sync(self) -> List[Dict[str, Any]]:
        """
        Get available tools (synchronous).

        Returns:
            List of tool definitions with name, description, and input_schema
        """
        if self._tools_cache is None:
            self._tools_cache = TELEGRAPH_TOOLS.copy()
        return self._tools_cache

    def call_tool_sync(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> Any:
        """
        Execute a tool by name (synchronous).

        Args:
            name: Name of the tool to execute
            arguments: Tool arguments

        Returns:
            Tool execution result

        Raises:
            ValueError: If tool name is unknown
            Exception: If tool execution fails
        """
        arguments = arguments or {}
        logger.info(f"Executing tool: {name} with args: {list(arguments.keys())}")

        try:
            if name == "create_page":
                return self._create_page(arguments)
            elif name == "edit_page":
                return self._edit_page(arguments)
            elif name == "get_page":
                return self._get_page(arguments)
            elif name == "get_page_list":
                return self._get_page_list(arguments)
            elif name == "get_account_info":
                return self._get_account_info(arguments)
            elif name == "get_views":
                return self._get_views(arguments)
            else:
                raise ValueError(f"Unknown tool: {name}")
        except Exception as e:
            logger.error(f"Tool {name} failed: {e}")
            raise

    def _create_page(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new Telegraph page."""
        title = args.get("title", "Untitled")
        content = args.get("content", "")
        author_name = args.get("author_name", "Telegraph Glossary")

        # Convert markdown to HTML if needed
        html_content = self._markdown_to_html(content)

        result = self.service.client.create_page(
            title=title,
            html_content=html_content,
            author_name=author_name
        )

        return {
            "success": True,
            "path": result.get("path"),
            "url": f"https://telegra.ph/{result.get('path')}",
            "title": result.get("title")
        }

    def _edit_page(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Edit an existing Telegraph page."""
        path = args.get("path")
        title = args.get("title", "Untitled")
        content = args.get("content", "")
        author_name = args.get("author_name", "Telegraph Glossary")

        if not path:
            raise ValueError("path is required for edit_page")

        # Convert markdown to HTML if needed
        html_content = self._markdown_to_html(content)

        result = self.service.client.edit_page(
            path=path,
            title=title,
            html_content=html_content,
            author_name=author_name
        )

        return {
            "success": True,
            "path": result.get("path"),
            "url": f"https://telegra.ph/{result.get('path')}",
            "title": result.get("title")
        }

    def _get_page(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get a Telegraph page."""
        path = args.get("path")

        if not path:
            raise ValueError("path is required for get_page")

        result = self.service.get_page(path)

        if not result:
            return {"success": False, "error": "Page not found"}

        return {
            "success": True,
            "path": result.get("path"),
            "url": f"https://telegra.ph/{result.get('path')}",
            "title": result.get("title"),
            "description": result.get("description"),
            "author_name": result.get("author_name"),
            "views": result.get("views"),
            "content": self.service.get_page_content(path)
        }

    def _get_page_list(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get list of pages in the account."""
        limit = args.get("limit", 50)
        offset = args.get("offset", 0)

        result = self.service.client.get_page_list(
            offset=offset,
            limit=limit
        )

        pages = result.get("pages", [])

        return {
            "success": True,
            "total_count": result.get("total_count", len(pages)),
            "pages": [
                {
                    "path": p.get("path"),
                    "url": f"https://telegra.ph/{p.get('path')}",
                    "title": p.get("title"),
                    "description": p.get("description"),
                    "views": p.get("views"),
                    "can_edit": p.get("can_edit", True)
                }
                for p in pages
            ]
        }

    def _get_account_info(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get account information."""
        result = self.service.client.get_account_info(
            fields=["short_name", "author_name", "author_url", "page_count"]
        )

        return {
            "success": True,
            "short_name": result.get("short_name"),
            "author_name": result.get("author_name"),
            "author_url": result.get("author_url"),
            "page_count": result.get("page_count")
        }

    def _get_views(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get page views."""
        path = args.get("path")

        if not path:
            raise ValueError("path is required for get_views")

        kwargs = {"path": path}
        if "year" in args:
            kwargs["year"] = args["year"]
        if "month" in args:
            kwargs["month"] = args["month"]
        if "day" in args:
            kwargs["day"] = args["day"]

        result = self.service.client.get_views(**kwargs)

        return {
            "success": True,
            "path": path,
            "views": result.get("views", 0)
        }

    def _markdown_to_html(self, content: str) -> str:
        """
        Convert markdown content to HTML.

        Simple conversion for common markdown elements.
        """
        if not content:
            return ""

        # If it looks like HTML already, return as-is
        if content.strip().startswith("<"):
            return content

        import re

        html = content

        # Headers
        html = re.sub(r'^### (.+)$', r'<h4>\1</h4>', html, flags=re.MULTILINE)
        html = re.sub(r'^## (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
        html = re.sub(r'^# (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)

        # Bold and italic
        html = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', html)
        html = re.sub(r'\*(.+?)\*', r'<i>\1</i>', html)

        # Links
        html = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', html)

        # Code blocks
        html = re.sub(r'```(\w*)\n(.*?)```', r'<pre>\2</pre>', html, flags=re.DOTALL)
        html = re.sub(r'`([^`]+)`', r'<code>\1</code>', html)

        # Lists
        lines = html.split('\n')
        in_list = False
        result_lines = []

        for line in lines:
            if line.strip().startswith('- ') or line.strip().startswith('* '):
                if not in_list:
                    result_lines.append('<ul>')
                    in_list = True
                item = line.strip()[2:]
                result_lines.append(f'<li>{item}</li>')
            else:
                if in_list:
                    result_lines.append('</ul>')
                    in_list = False
                result_lines.append(line)

        if in_list:
            result_lines.append('</ul>')

        html = '\n'.join(result_lines)

        # Paragraphs - wrap remaining text blocks
        paragraphs = html.split('\n\n')
        processed = []
        for p in paragraphs:
            p = p.strip()
            if p and not p.startswith('<'):
                p = f'<p>{p}</p>'
            processed.append(p)

        html = '\n'.join(processed)

        # Clean up newlines within paragraphs
        html = re.sub(r'<p>([^<]*)\n([^<]*)</p>', r'<p>\1 \2</p>', html)

        return html

    def clear_cache(self) -> None:
        """Clear the tools cache."""
        self._tools_cache = None
