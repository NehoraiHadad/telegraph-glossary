"""Text parser for marking syntax replacement."""

import re
from typing import Dict, List, Tuple, Any, Optional

DEFAULT_SYNTAX_PATTERNS: Dict[str, Dict[str, str]] = {
    "<?>": {"pattern": r"(\w+)<\?>", "display": "term<?>", "example": "The CPU<?> is fast"},
    "[[]]": {"pattern": r"\[\[(\w+)\]\]", "display": "[[term]]", "example": "The [[CPU]] is fast"},
    "{{}}": {"pattern": r"\{\{(\w+)\}\}", "display": "{{term}}", "example": "The {{CPU}} is fast"},
    "<<>>": {"pattern": r"<<(\w+)>>", "display": "<<term>>", "example": "The <<CPU>> is fast"},
}

SYNTAX_PATTERNS: Dict[str, Dict[str, str]] = DEFAULT_SYNTAX_PATTERNS.copy()


def create_custom_syntax(prefix: str, suffix: str) -> Dict[str, str]:
    escaped_prefix = re.escape(prefix)
    escaped_suffix = re.escape(suffix)
    pattern = f"{escaped_prefix}([\\w\\s]+?){escaped_suffix}"
    return {"pattern": pattern, "display": f"{prefix}term{suffix}", "example": f"The {prefix}CPU{suffix} is fast"}


def register_custom_syntax(name: str, prefix: str, suffix: str) -> None:
    SYNTAX_PATTERNS[name] = create_custom_syntax(prefix, suffix)


def validate_custom_syntax(prefix: str, suffix: str) -> Tuple[bool, str]:
    if not prefix or not suffix:
        return False, "Both prefix and suffix are required"
    if len(prefix) > 10 or len(suffix) > 10:
        return False, "Prefix and suffix must be 10 characters or less"
    try:
        escaped_prefix = re.escape(prefix)
        escaped_suffix = re.escape(suffix)
        pattern = f"{escaped_prefix}([\\w\\s]+?){escaped_suffix}"
        re.compile(pattern)
    except re.error as e:
        return False, f"Invalid pattern: {e}"
    return True, ""


class TextParser:
    def __init__(self, syntax: str, glossary: Dict[str, Dict[str, Any]], custom_prefix: Optional[str] = None, custom_suffix: Optional[str] = None):
        self.syntax = syntax
        self.glossary = glossary
        if syntax == "custom" and custom_prefix and custom_suffix:
            custom_info = create_custom_syntax(custom_prefix, custom_suffix)
            self.pattern = custom_info["pattern"]
        elif syntax in SYNTAX_PATTERNS:
            self.pattern = SYNTAX_PATTERNS[syntax]["pattern"]
        else:
            raise ValueError(f"Unknown syntax: {syntax}")

    def process_text(self, text: str, output_format: str = "markdown") -> Tuple[str, List[str], List[str]]:
        found_terms: List[str] = []
        missing_terms: List[str] = []

        def replacer(match: re.Match) -> str:
            term = match.group(1)
            if term in self.glossary:
                found_terms.append(term)
                url = self.glossary[term].get("telegraph_url", "")
                return self._format_link(term, url, output_format)
            term_lower = term.lower()
            for glossary_term, data in self.glossary.items():
                if glossary_term.lower() == term_lower:
                    found_terms.append(glossary_term)
                    url = data.get("telegraph_url", "")
                    return self._format_link(term, url, output_format)
            missing_terms.append(term)
            return self._format_missing(term, output_format)

        processed = re.sub(self.pattern, replacer, text)
        return processed, list(set(found_terms)), list(set(missing_terms))

    def extract_terms(self, text: str) -> List[str]:
        matches = re.findall(self.pattern, text)
        return list(set(matches))

    def _format_link(self, term: str, url: str, output_format: str) -> str:
        if output_format == "html":
            return f'<a href="{url}">{term}</a>'
        elif output_format == "telegram":
            return term
        else:
            return f"[{term}]({url})"

    def _format_missing(self, term: str, output_format: str) -> str:
        if output_format == "html":
            return f'<span style="color: red;">{term}</span>'
        elif output_format == "telegram":
            return f"[{term}?]"
        else:
            return f"**{term}**"

    @staticmethod
    def get_syntax_info(syntax: str) -> Dict[str, str]:
        return SYNTAX_PATTERNS.get(syntax, {})

    @staticmethod
    def get_available_syntaxes() -> List[str]:
        return list(SYNTAX_PATTERNS.keys())
