"""Content converter service for Markdown/HTML conversion."""

import re
from typing import Optional

import bleach
import markdown
from markdown.extensions import fenced_code, tables


# Telegraph supported HTML tags
TELEGRAPH_ALLOWED_TAGS = [
    'a', 'aside', 'b', 'blockquote', 'br', 'code', 'em', 'figcaption',
    'figure', 'h3', 'h4', 'hr', 'i', 'iframe', 'img', 'li', 'ol', 'p',
    'pre', 's', 'strong', 'u', 'ul', 'video'
]

TELEGRAPH_ALLOWED_ATTRIBUTES = {
    'a': ['href', 'target'],
    'img': ['src', 'alt'],
    'iframe': ['src', 'width', 'height', 'frameborder', 'allowfullscreen'],
    'video': ['src', 'controls', 'autoplay', 'loop'],
}


class ContentConverter:
    """Convert between Markdown, HTML, and sanitize for Telegraph."""

    @staticmethod
    def markdown_to_html(markdown_text: str) -> str:
        """
        Convert Markdown to Telegraph-compatible HTML.

        Args:
            markdown_text: Markdown formatted text

        Returns:
            HTML string compatible with Telegraph
        """
        if not markdown_text:
            return ""

        # Configure markdown extensions
        md = markdown.Markdown(
            extensions=[
                'fenced_code',
                'tables',
                'nl2br',  # Convert newlines to <br>
            ],
            output_format='html'
        )

        html = md.convert(markdown_text)

        # Post-process for Telegraph compatibility
        html = ContentConverter._post_process_html(html)

        # Sanitize to only allow Telegraph-supported tags
        html = ContentConverter.sanitize_for_telegraph(html)

        return html

    @staticmethod
    def _post_process_html(html: str) -> str:
        """Post-process HTML for Telegraph compatibility."""
        # Convert <strong> to <b>
        html = re.sub(r'<strong>(.*?)</strong>', r'<b>\1</b>', html, flags=re.DOTALL)

        # Convert <em> to <i>
        html = re.sub(r'<em>(.*?)</em>', r'<i>\1</i>', html, flags=re.DOTALL)

        # Ensure images are wrapped in <figure>
        def wrap_img_in_figure(match):
            img_tag = match.group(0)
            # Check if already inside a figure
            return f'<figure>{img_tag}</figure>'

        # Only wrap standalone images (not already in figure)
        html = re.sub(r'(?<!<figure>)<img([^>]*)>', wrap_img_in_figure, html)

        # Fix double-wrapped figures
        html = re.sub(r'<figure><figure>', '<figure>', html)
        html = re.sub(r'</figure></figure>', '</figure>', html)

        return html

    @staticmethod
    def html_to_markdown(html_content: str) -> str:
        """
        Convert HTML back to Markdown (best effort).

        Args:
            html_content: HTML string

        Returns:
            Markdown formatted text
        """
        if not html_content:
            return ""

        text = html_content

        # Convert common HTML tags to Markdown
        # Bold
        text = re.sub(r'<b>(.*?)</b>', r'**\1**', text, flags=re.DOTALL)
        text = re.sub(r'<strong>(.*?)</strong>', r'**\1**', text, flags=re.DOTALL)

        # Italic
        text = re.sub(r'<i>(.*?)</i>', r'*\1*', text, flags=re.DOTALL)
        text = re.sub(r'<em>(.*?)</em>', r'*\1*', text, flags=re.DOTALL)

        # Strikethrough
        text = re.sub(r'<s>(.*?)</s>', r'~~\1~~', text, flags=re.DOTALL)

        # Inline code
        text = re.sub(r'<code>(.*?)</code>', r'`\1`', text, flags=re.DOTALL)

        # Code blocks
        text = re.sub(r'<pre><code>(.*?)</code></pre>', r'```\n\1\n```', text, flags=re.DOTALL)

        # Links
        text = re.sub(r'<a href="([^"]*)"[^>]*>(.*?)</a>', r'[\2](\1)', text, flags=re.DOTALL)

        # Images (extract from figure if present)
        text = re.sub(r'<figure>\s*<img src="([^"]*)"[^>]*/?>\s*(?:<figcaption>(.*?)</figcaption>)?\s*</figure>',
                      lambda m: f'![{m.group(2) or "image"}]({m.group(1)})', text, flags=re.DOTALL)
        text = re.sub(r'<img src="([^"]*)"[^>]*/?>',
                      lambda m: f'![image]({m.group(1)})', text)

        # Headings
        text = re.sub(r'<h3>(.*?)</h3>', r'### \1', text, flags=re.DOTALL)
        text = re.sub(r'<h4>(.*?)</h4>', r'#### \1', text, flags=re.DOTALL)

        # Lists
        text = re.sub(r'<li>(.*?)</li>', r'- \1', text, flags=re.DOTALL)
        text = re.sub(r'</?[ou]l>', '', text)

        # Blockquotes
        text = re.sub(r'<blockquote>(.*?)</blockquote>',
                      lambda m: '\n'.join(f'> {line}' for line in m.group(1).strip().split('\n')),
                      text, flags=re.DOTALL)

        # Paragraphs and line breaks
        text = re.sub(r'<br\s*/?>', '\n', text)
        text = re.sub(r'<p>(.*?)</p>', r'\1\n\n', text, flags=re.DOTALL)

        # Remove remaining HTML tags
        text = re.sub(r'<[^>]+>', '', text)

        # Clean up whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = text.strip()

        return text

    @staticmethod
    def sanitize_for_telegraph(html: str) -> str:
        """
        Sanitize HTML to only include Telegraph-supported tags.

        Args:
            html: HTML string to sanitize

        Returns:
            Sanitized HTML with only allowed tags
        """
        if not html:
            return ""

        return bleach.clean(
            html,
            tags=TELEGRAPH_ALLOWED_TAGS,
            attributes=TELEGRAPH_ALLOWED_ATTRIBUTES,
            strip=True
        )

    @staticmethod
    def wrap_definition_content(term: str, content_html: str, escape_term: bool = True) -> str:
        """
        Wrap content with term header for Telegraph page.

        Args:
            term: The glossary term (title)
            content_html: The HTML content for the definition
            escape_term: Whether to escape HTML in the term

        Returns:
            Complete HTML for the Telegraph page
        """
        if escape_term:
            term = ContentConverter._escape_html(term)

        return f"<h3>{term}</h3>\n{content_html}"

    @staticmethod
    def _escape_html(text: str) -> str:
        """Escape HTML special characters."""
        return (text
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;"))

    @staticmethod
    def extract_plain_text(html: str) -> str:
        """
        Extract plain text from HTML for display/search.

        Args:
            html: HTML string

        Returns:
            Plain text without HTML tags
        """
        if not html:
            return ""

        # Remove all HTML tags
        text = re.sub(r'<[^>]+>', ' ', html)

        # Decode HTML entities
        text = text.replace('&amp;', '&')
        text = text.replace('&lt;', '<')
        text = text.replace('&gt;', '>')
        text = text.replace('&quot;', '"')
        text = text.replace('&nbsp;', ' ')

        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()

        return text

    @staticmethod
    def is_html_content(content: str) -> bool:
        """
        Check if content appears to be HTML.

        Args:
            content: Content string to check

        Returns:
            True if content contains HTML tags
        """
        if not content:
            return False

        # Check for common HTML tags
        html_pattern = r'<(p|b|i|a|img|ul|ol|li|h[1-6]|code|pre|blockquote|figure)[^>]*>'
        return bool(re.search(html_pattern, content, re.IGNORECASE))
