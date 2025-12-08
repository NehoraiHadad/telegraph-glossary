"""Telegram Bot service for sending messages with hyperlinks."""

import requests
from typing import Dict, Optional, Tuple
import re


class TelegramBotService:
    """Service for sending messages via Telegram Bot API."""

    BASE_URL = "https://api.telegram.org/bot{token}/{method}"

    def __init__(self, bot_token: str):
        self.bot_token = bot_token

    def _call_api(self, method: str, params: dict) -> dict:
        if not self.bot_token:
            raise Exception("Bot token is not configured. Check Streamlit secrets.")
        url = self.BASE_URL.format(token=self.bot_token, method=method)
        response = requests.post(url, json=params, timeout=30)
        result = response.json()
        if not result.get("ok"):
            error_code = result.get("error_code", "")
            error_msg = result.get("description", "Unknown error")
            # Add helpful hints based on error type
            hint = ""
            if error_code == 404 or "Not Found" in error_msg:
                hint = " (Check: Is bot added as admin to the channel?)"
            elif error_code == 401 or "Unauthorized" in error_msg:
                hint = " (Check: Is the bot token correct?)"
            elif "chat not found" in error_msg.lower():
                hint = " (Check: Is the Chat ID correct? For private channels use -100XXXXXXXXXX)"
            raise Exception(f"Telegram API error [{error_code}]: {error_msg}{hint}")
        return result.get("result", {})

    def get_me(self) -> dict:
        return self._call_api("getMe", {})

    def send_message(self, chat_id: str, text: str, parse_mode: str = "MarkdownV2", disable_web_page_preview: bool = True) -> dict:
        params = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode, "disable_web_page_preview": disable_web_page_preview}
        return self._call_api("sendMessage", params)

    def send_formatted_text(self, chat_id: str, text: str, terms_with_urls: Dict[str, str]) -> dict:
        formatted_text = self._format_with_links_html(text, terms_with_urls)
        return self.send_message(chat_id, formatted_text, parse_mode="HTML")

    def _format_with_links_html(self, text: str, terms_with_urls: Dict[str, str]) -> str:
        result = self._escape_html(text)
        for term, url in terms_with_urls.items():
            pattern = re.compile(re.escape(term), re.IGNORECASE)
            def make_link(match):
                original_term = match.group(0)
                escaped_term = self._escape_html(original_term)
                return f'<a href="{url}">{escaped_term}</a>'
            result = pattern.sub(make_link, result)
        return result

    def _escape_html(self, text: str) -> str:
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    @staticmethod
    def validate_token(token: str) -> Tuple[bool, str, Optional[dict]]:
        if not token or not token.strip():
            return False, "Token is empty", None
        try:
            service = TelegramBotService(token.strip())
            bot_info = service.get_me()
            bot_name = bot_info.get("username", "Unknown")
            return True, f"Valid! Bot: @{bot_name}", bot_info
        except Exception as e:
            return False, str(e), None

    @staticmethod
    def validate_chat_id(token: str, chat_id: str) -> Tuple[bool, str]:
        if not chat_id or not chat_id.strip():
            return False, "Chat ID is empty"
        try:
            service = TelegramBotService(token)
            result = service._call_api("getChat", {"chat_id": chat_id.strip()})
            chat_title = result.get("title") or result.get("username") or result.get("first_name", "Unknown")
            return True, f"Valid! Chat: {chat_title}"
        except Exception as e:
            return False, str(e)
