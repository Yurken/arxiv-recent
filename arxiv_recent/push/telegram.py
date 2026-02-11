"""Telegram push channel."""

from __future__ import annotations

import logging

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from arxiv_recent.config import Settings

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org"
MAX_MESSAGE_LENGTH = 4096


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=15),
    reraise=True,
)
def _send_message(bot_token: str, chat_id: str, text: str, parse_mode: str = "Markdown") -> None:
    url = f"{TELEGRAM_API}/bot{bot_token}/sendMessage"
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(
            url,
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": parse_mode,
                "disable_web_page_preview": True,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("ok"):
            raise RuntimeError(f"Telegram API error: {data}")


def send_telegram(markdown: str, settings: Settings) -> None:
    """Send digest to Telegram, splitting if necessary."""
    bot_token = settings.telegram_bot_token
    chat_id = settings.telegram_chat_id

    # Split into chunks if too long
    if len(markdown) <= MAX_MESSAGE_LENGTH:
        _send_message(bot_token, chat_id, markdown)
        return

    # Split by paper sections (---)
    sections = markdown.split("\n---\n")
    chunk = ""
    for section in sections:
        candidate = chunk + "\n---\n" + section if chunk else section
        if len(candidate) > MAX_MESSAGE_LENGTH:
            if chunk:
                _send_message(bot_token, chat_id, chunk)
            chunk = section
        else:
            chunk = candidate

    if chunk:
        _send_message(bot_token, chat_id, chunk)

    logger.info("Telegram message(s) sent to chat %s", chat_id)
