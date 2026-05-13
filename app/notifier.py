import logging

import httpx


class TelegramNotifier:
    def __init__(self, bot_token: str, chat_id: str, thread_id: str | None = None):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.thread_id = thread_id

    def send(self, emoji: str, title: str, body_lines: list[str]) -> bool:
        if not (self.bot_token and self.chat_id):
            return False
        text = f"{emoji} <b>roscomvpn-geo-sync</b> — {title}\n" + "\n".join(body_lines)
        data = {
            "chat_id": self.chat_id,
            "parse_mode": "HTML",
            "text": text,
            "disable_web_page_preview": "true",
        }
        if self.thread_id:
            data["message_thread_id"] = self.thread_id
        try:
            r = httpx.post(
                f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
                data=data,
                timeout=15,
            )
            r.raise_for_status()
            return True
        except httpx.HTTPError as e:
            logging.error(f"Telegram send failed: {e}")
            return False
