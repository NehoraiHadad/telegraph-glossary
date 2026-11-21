"""Stream event types for AI chat integration."""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any


class EventType(str, Enum):
    """Types of streaming events for UI consumption."""
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    TEXT = "text"
    TEXT_DELTA = "text_delta"
    DONE = "done"
    ERROR = "error"


@dataclass
class StreamEvent:
    """
    Structured event for UI consumption during streaming.

    Attributes:
        type: The type of event (tool_call, tool_result, text, etc.)
        data: Event-specific data
    """
    type: EventType
    data: Dict[str, Any]
