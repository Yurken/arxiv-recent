"""Push channels for delivering digests."""

from __future__ import annotations

import logging

from arxiv_recent.config import Settings, get_settings
from arxiv_recent.push.email_push import send_email
from arxiv_recent.push.qq import send_qq

# from arxiv_recent.push.telegram import send_telegram  # Telegram 暂时禁用

logger = logging.getLogger(__name__)


def push_digest(
    markdown: str,
    plaintext: str,
    run_date: str,
    settings: Settings | None = None,
) -> dict[str, bool]:
    """Push digest through all configured channels. Returns {channel: success}."""
    cfg = settings or get_settings()
    results: dict[str, bool] = {}

    channels = cfg.push_channels
    if not channels:
        logger.info("No push channels configured, skipping push")
        return results

    for channel in channels:
        channel = channel.strip().lower()
        try:
            if channel == "email":
                if not cfg.email_configured:
                    logger.warning("Email channel requested but not configured")
                    results["email"] = False
                    continue
                send_email(
                    subject=f"arXiv Digest {run_date}",
                    body_html=_markdown_to_simple_html(markdown),
                    body_text=plaintext,
                    settings=cfg,
                )
                results["email"] = True
                logger.info("Email sent successfully")

            elif channel == "qq":
                if not cfg.qq_configured:
                    logger.warning("QQ channel requested but not configured")
                    results["qq"] = False
                    continue
                send_qq(plaintext, settings=cfg)
                results["qq"] = True
                logger.info("QQ group message sent successfully")

            # elif channel == "telegram":
            #     if not cfg.telegram_configured:
            #         logger.warning("Telegram channel requested but not configured")
            #         results["telegram"] = False
            #         continue
            #     send_telegram(markdown, settings=cfg)
            #     results["telegram"] = True
            #     logger.info("Telegram message sent successfully")

            else:
                logger.warning("Unknown push channel: %s", channel)
                results[channel] = False

        except Exception:
            logger.exception("Failed to push via %s", channel)
            results[channel] = False

    return results


def _markdown_to_simple_html(md: str) -> str:
    """Minimal markdown-to-HTML for email. Not a full parser."""
    import re

    html = md
    # Headers
    html = re.sub(r"^### (.+)$", r"<h3>\1</h3>", html, flags=re.MULTILINE)
    html = re.sub(r"^## (.+)$", r"<h2>\1</h2>", html, flags=re.MULTILINE)
    html = re.sub(r"^# (.+)$", r"<h1>\1</h1>", html, flags=re.MULTILINE)
    # Bold
    html = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", html)
    # Links
    html = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', html)
    # List items
    html = re.sub(r"^- (.+)$", r"<li>\1</li>", html, flags=re.MULTILINE)
    # Horizontal rules
    html = html.replace("---", "<hr>")
    # Line breaks
    html = html.replace("\n", "<br>\n")
    return f"<html><body>{html}</body></html>"
