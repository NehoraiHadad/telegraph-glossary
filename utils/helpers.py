"""Utility helpers for Telegraph Glossary."""

import streamlit as st
import streamlit.components.v1 as components
from functools import wraps
from typing import Any, Callable


def show_toast(message: str, icon: str = "") -> None:
    st.toast(message, icon=icon if icon else None)


def handle_telegraph_errors(func: Callable) -> Callable:
    @wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        try:
            return func(*args, **kwargs)
        except ConnectionError:
            st.error("Cannot connect to Telegraph.")
        except Exception as e:
            error_msg = str(e)
            if "ACCESS_TOKEN_INVALID" in error_msg.upper():
                st.error("Telegraph access token is invalid.")
            elif "PAGE_NOT_FOUND" in error_msg.upper():
                st.error("Page not found on Telegraph.")
            elif "FLOOD_WAIT" in error_msg.upper():
                st.error("Too many requests. Please wait.")
            else:
                st.error(f"Telegraph error: {error_msg}")
        return None
    return wrapper


def copy_to_clipboard(text: str, button_text: str = "Copy") -> bool:
    key = f"copy_{hash(text) % 10000}"
    if st.button(button_text, key=key):
        escaped_text = text.replace("\\", "\\\\").replace("`", "\\`").replace("$", "\\$")
        components.html(f'<script>navigator.clipboard.writeText(`{escaped_text}`);</script>', height=0)
        return True
    return False


def get_rtl_css() -> str:
    return """
    <style>
        .rtl-text { direction: rtl; text-align: right; unicode-bidi: bidi-override; }
        .rtl-container { direction: rtl; }
        .stTextArea textarea { unicode-bidi: plaintext; }
        .stTextInput input { unicode-bidi: plaintext; }
        .term-card { background-color: #f0f2f6; border-radius: 8px; padding: 1rem; margin-bottom: 0.5rem; }
        .term-card:hover { background-color: #e0e2e6; }
        @media (prefers-color-scheme: dark) {
            .term-card { background-color: #262730; }
            .term-card:hover { background-color: #363740; }
        }
    </style>
    """


def inject_custom_css() -> None:
    st.markdown(get_rtl_css(), unsafe_allow_html=True)


def format_date(date_str: str) -> str:
    if not date_str:
        return ""
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M")
    except (ValueError, AttributeError):
        return date_str


def truncate_text(text: str, max_length: int = 100) -> str:
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."
