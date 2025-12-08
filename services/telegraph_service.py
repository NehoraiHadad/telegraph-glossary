"""Telegraph API service wrapper for glossary management."""

import json
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from telegraph import Telegraph


class TelegraphService:
    """Wrapper for Telegraph API with glossary-specific functionality."""

    def __init__(self, access_token: Optional[str] = None):
        self.client = Telegraph(access_token) if access_token else Telegraph()
        self.access_token = access_token
        self.index_path: Optional[str] = None

    def create_account(self, short_name: str, author_name: str = "") -> Dict[str, Any]:
        """Create a new Telegraph account."""
        result = self.client.create_account(
            short_name=short_name,
            author_name=author_name if author_name else None,
        )
        self.access_token = result.get("access_token")
        return result

    def create_term_page(self, term: str, definition: str, author_name: str = "Telegraph Glossary", is_html: bool = False) -> Dict[str, str]:
        """Create a Telegraph page for a glossary term.

        Args:
            term: The glossary term
            definition: The definition text or HTML content
            author_name: Author name for the page
            is_html: If True, definition is treated as pre-formatted HTML.
                    If False, definition is escaped and wrapped in <p> tags.
        """
        if is_html:
            # Use definition as raw HTML
            html_content = f"<h3>{self._escape_html(term)}</h3>\n{definition}"
        else:
            # Escape definition and wrap in <p> tags (backward compatible)
            html_content = f"""<h3>{self._escape_html(term)}</h3>
<p>{self._escape_html(definition)}</p>"""

        result = self.client.create_page(
            title=term,
            html_content=html_content,
            author_name=author_name,
        )
        return {"path": result["path"], "url": f"https://telegra.ph/{result['path']}"}

    def update_term_page(self, path: str, term: str, definition: str, author_name: str = "Telegraph Glossary", is_html: bool = False) -> Dict[str, str]:
        """Update an existing term page.

        Args:
            path: The Telegraph page path
            term: The glossary term
            definition: The definition text or HTML content
            author_name: Author name for the page
            is_html: If True, definition is treated as pre-formatted HTML.
                    If False, definition is escaped and wrapped in <p> tags.
        """
        if is_html:
            # Use definition as raw HTML
            html_content = f"<h3>{self._escape_html(term)}</h3>\n{definition}"
        else:
            # Escape definition and wrap in <p> tags (backward compatible)
            html_content = f"""<h3>{self._escape_html(term)}</h3>
<p>{self._escape_html(definition)}</p>"""

        result = self.client.edit_page(
            path=path,
            title=term,
            html_content=html_content,
            author_name=author_name,
        )

        # Verify the update actually happened (skip for HTML content as structure may differ)
        if not is_html:
            verification = self.get_page(path)
            if verification:
                content = verification.get("content", [])
                content_str = str(content)
                # Check if the definition (first 50 chars) is in the content
                # Check both raw and escaped versions since Telegraph might return either
                check_text = definition[:50] if len(definition) >= 50 else definition
                check_text_escaped = self._escape_html(check_text)
                if check_text not in content_str and check_text_escaped not in content_str:
                    raise ValueError(
                        f"Telegraph page update verification failed - content mismatch. "
                        f"The page may not have been updated. Try deleting and recreating the term."
                    )

        return {"path": result["path"], "url": f"https://telegra.ph/{result['path']}"}

    def upload_image(self, file_path: str) -> str:
        """Upload image to Telegraph and return URL.

        Args:
            file_path: Path to the image file to upload

        Returns:
            The full Telegraph URL of the uploaded image
        """
        from services.image_upload_service import ImageUploadService
        upload_service = ImageUploadService()
        return upload_service.upload_from_file_path(file_path)

    def get_page_content(self, path: str) -> Optional[str]:
        """Get the HTML content of an existing page.

        Args:
            path: The Telegraph page path

        Returns:
            The HTML content of the page, or None if the page doesn't exist
        """
        page = self.get_page(path)
        if not page:
            return None

        content = page.get("content", [])
        if isinstance(content, str):
            return content

        # Convert content nodes to HTML string
        html_parts = []
        for node in content:
            if isinstance(node, str):
                html_parts.append(node)
            elif isinstance(node, dict):
                html_parts.append(self._node_to_html(node))

        return "".join(html_parts)

    def _node_to_html(self, node: Dict[str, Any]) -> str:
        """Convert a Telegraph content node to HTML string.

        Args:
            node: A Telegraph content node dictionary

        Returns:
            HTML string representation of the node
        """
        tag = node.get("tag", "")
        attrs = node.get("attrs", {})
        children = node.get("children", [])

        # Build opening tag with attributes
        if attrs:
            attr_str = " ".join(f'{k}="{v}"' for k, v in attrs.items())
            opening_tag = f"<{tag} {attr_str}>"
        else:
            opening_tag = f"<{tag}>" if tag else ""

        # Process children
        children_html = []
        for child in children:
            if isinstance(child, str):
                children_html.append(child)
            elif isinstance(child, dict):
                children_html.append(self._node_to_html(child))

        # Build closing tag
        closing_tag = f"</{tag}>" if tag else ""

        return opening_tag + "".join(children_html) + closing_tag

    def create_index_page(self, glossary: Dict[str, Dict[str, Any]], existing_path: Optional[str] = None) -> Dict[str, str]:
        """Create or update the glossary index page."""
        html_content = self._generate_index_html(glossary)
        if existing_path:
            result = self.client.edit_page(path=existing_path, title="Glossary Index", html_content=html_content, author_name="Telegraph Glossary")
        else:
            result = self.client.create_page(title="Glossary Index", html_content=html_content, author_name="Telegraph Glossary")
        self.index_path = result["path"]
        return {"path": result["path"], "url": f"https://telegra.ph/{result['path']}"}

    def load_glossary_from_index(self, index_path: str) -> Dict[str, Dict[str, Any]]:
        """Load glossary data from the index page."""
        try:
            page = self.client.get_page(index_path, return_content=True)
        except Exception:
            return {}
        content = page.get("content", [])
        if isinstance(content, str):
            return self._parse_glossary_from_html(content)
        for node in content:
            if isinstance(node, dict):
                json_str = self._extract_json_from_node(node)
                if json_str:
                    try:
                        metadata = json.loads(json_str)
                        terms = metadata.get("terms", [])
                        return {t["term"]: t for t in terms if "term" in t}
                    except (json.JSONDecodeError, TypeError):
                        pass
        return {}

    def _parse_glossary_from_html(self, html_content: str) -> Dict[str, Dict[str, Any]]:
        import html
        code_match = re.search(r'<code>([^<]+)</code>', html_content)
        if code_match:
            json_str = html.unescape(code_match.group(1))
            try:
                metadata = json.loads(json_str)
                terms = metadata.get("terms", [])
                return {t["term"]: t for t in terms if "term" in t}
            except (json.JSONDecodeError, TypeError):
                pass
        return {}

    def get_page(self, path: str) -> Optional[Dict[str, Any]]:
        try:
            return self.client.get_page(path, return_content=True)
        except Exception:
            return None

    def _generate_index_html(self, glossary: Dict[str, Dict[str, Any]]) -> str:
        entries = []
        terms_metadata = []
        for term, data in sorted(glossary.items()):
            url = data.get("telegraph_url", "")
            definition = data.get("definition", "")
            short_def = definition[:100] + "..." if len(definition) > 100 else definition
            entries.append(f'<p><b>{self._escape_html(term)}</b>: <a href="{url}">{self._escape_html(short_def)}</a></p>')
            terms_metadata.append({"term": term, "definition": definition, "telegraph_path": data.get("telegraph_path", ""), "telegraph_url": url, "created_at": data.get("created_at", ""), "updated_at": data.get("updated_at", "")})
        metadata = {"version": "1.0", "updated": datetime.now().isoformat(), "terms": terms_metadata}
        html_parts = ["<h3>Glossary Index</h3>", f"<p><i>{len(glossary)} terms</i></p>"]
        if entries:
            html_parts.extend(entries)
        else:
            html_parts.append("<p><i>No terms yet. Add your first term!</i></p>")
        html_parts.append(f'<pre><code>{json.dumps(metadata)}</code></pre>')
        return "\n".join(html_parts)

    def _extract_json_from_node(self, node: Dict[str, Any]) -> Optional[str]:
        if node.get("tag") in ("pre", "code"):
            children = node.get("children", [])
            text = self._extract_text_from_children(children)
            if text and text.strip().startswith("{"):
                return text.strip()
        for child in node.get("children", []):
            if isinstance(child, dict):
                result = self._extract_json_from_node(child)
                if result:
                    return result
        return None

    def _extract_text_from_children(self, children: List[Any]) -> str:
        text_parts = []
        for child in children:
            if isinstance(child, str):
                text_parts.append(child)
            elif isinstance(child, dict):
                text_parts.append(self._extract_text_from_children(child.get("children", [])))
        return "".join(text_parts)

    def _escape_html(self, text: str) -> str:
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
