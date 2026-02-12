"""QQ group push channel via OneBot v11 HTTP API."""

from __future__ import annotations

import logging

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from arxiv_recent.config import Settings

logger = logging.getLogger(__name__)

MAX_MSG_LENGTH = 3000  # QQ 单条消息安全上限


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=15),
    reraise=True,
)
def _send_group_msg(api_url: str, group_id: str, text: str, token: str = "") -> None:
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    with httpx.Client(timeout=30.0) as client:
        resp = client.post(
            f"{api_url.rstrip('/')}/send_group_msg",
            json={"group_id": int(group_id), "message": text},
            headers=headers,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("retcode") != 0:
            raise RuntimeError(f"OneBot API error: {data}")


def _send_forward_msg(
    api_url: str, group_id: str, segments: list[str], bot_name: str, token: str = ""
) -> bool:
    """Try sending as forward message (合并转发). Returns False if unsupported."""
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    nodes = [
        {
            "type": "node",
            "data": {"name": bot_name, "uin": "0", "content": seg},
        }
        for seg in segments
    ]

    try:
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(
                f"{api_url.rstrip('/')}/send_group_forward_msg",
                json={"group_id": int(group_id), "messages": nodes},
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("retcode") != 0:
                logger.warning(
                    "Forward msg failed (retcode=%s), will split send", data.get("retcode")
                )
                return False
            return True
    except Exception:
        logger.warning("Forward msg not supported, falling back to split send")
        return False


def _split_digest(plaintext: str) -> list[str]:
    """Split digest into chunks that fit QQ message length."""
    lines = plaintext.split("\n")
    chunks: list[str] = []
    chunk = ""

    for line in lines:
        # Paper separator: starts with a number followed by a dot
        if line.strip() and line.strip()[0].isdigit() and ". " in line and len(chunk) > 500:
            chunks.append(chunk.strip())
            chunk = line + "\n"
        elif len(chunk) + len(line) + 1 > MAX_MSG_LENGTH:
            if chunk:
                chunks.append(chunk.strip())
            chunk = line + "\n"
        else:
            chunk += line + "\n"

    if chunk.strip():
        chunks.append(chunk.strip())

    return chunks


def send_qq(plaintext: str, settings: Settings) -> None:
    """Send digest to QQ group, using forward msg or split messages."""
    api_url = settings.qq_bot_api
    group_id = settings.qq_group_id
    token = settings.qq_bot_token
    bot_name = "arXiv Daily"

    segments = _split_digest(plaintext)
    logger.info("QQ digest split into %d segments", len(segments))

    # Try forward message first (cleaner, single bubble)
    if len(segments) > 1 and _send_forward_msg(api_url, group_id, segments, bot_name, token):
        logger.info("QQ forward message sent to group %s", group_id)
        return

    # Fallback: send as individual messages
    import time

    for i, seg in enumerate(segments):
        _send_group_msg(api_url, group_id, seg, token)
        if i < len(segments) - 1:
            time.sleep(1)  # avoid flood

    logger.info("QQ sent %d messages to group %s", len(segments), group_id)
