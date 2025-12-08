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

    def create_term_page(self, term: str, definition: str, author_name: str = "Telegraph Glossary") -> Dict[str, str]:
        """Create a Telegraph page for a glossary term."""
        html_content = f"""<h3>{self._escape_html(term)}</h3>
<p>{self._escape_html(definition)}</p>"""
        result = self.client.create_page(
            title=term,
            html_content=html_content,
            author_name=author_name,
        )
        return {"path": result["path"], "url": f"https://telegra.ph/{result['path']}"}

    def update_term_page(self, path: str, term: str, definition: str, author_name: str = "Telegraph Glossary") -> Dict[str, str]:
        """Update an existing term page."""
        html_content = f"""<h3>{self._escape_html(term)}</h3>
<p>{self._escape_html(definition)}</p>"""
        result = self.client.edit_page(
            path=path,
            title=term,
            html_content=html_content,
            author_name=author_name,
        )

        # Verify the update actually happened
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
