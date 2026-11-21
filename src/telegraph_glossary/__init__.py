"""Telegraph Glossary: glossary terms as Telegraph pages, auto-linked into Telegram posts."""

from .glossary import Entry, Glossary
from .linker import link_text

__all__ = ["Glossary", "Entry", "link_text"]
__version__ = "2.0.0"
