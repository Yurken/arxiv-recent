"""LLM client wrapper for vLLM-compatible OpenAI chat completions API."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from arxiv_recent.config import Settings, get_settings

logger = logging.getLogger(__name__)


class RateLimiter:
    """Sliding-window rate limiter for async calls."""

    def __init__(self, rpm: int) -> None:
        self._rpm = rpm
        self._interval = 60.0 / rpm
        self._timestamps: list[float] = []
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            # Purge timestamps older than 60s
            cutoff = now - 60.0
            self._timestamps = [t for t in self._timestamps if t > cutoff]

            if len(self._timestamps) >= self._rpm:
                sleep_until = self._timestamps[0] + 60.0
                wait_time = sleep_until - now
                if wait_time > 0:
                    logger.debug("Rate limiter: sleeping %.1fs", wait_time)
                    await asyncio.sleep(wait_time)

            self._timestamps.append(time.monotonic())


class LLMClient:
    """Async client for vLLM-compatible OpenAI chat completions."""

    def __init__(self, settings: Settings | None = None) -> None:
        cfg = settings or get_settings()
        self._url = cfg.vllm_url
        self._model = cfg.vllm_model_name
        self._api_key = cfg.vllm_api_key
        self._semaphore = asyncio.Semaphore(cfg.llm_max_concurrency)
        self._rate_limiter = RateLimiter(cfg.llm_rate_limit_rpm)

    def _headers(self) -> dict[str, str]:
        h: dict[str, str] = {"Content-Type": "application/json"}
        if self._api_key:
            h["Authorization"] = f"Bearer {self._api_key}"
        return h

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=4, max=60),
        reraise=True,
    )
    async def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                self._url,
                json=payload,
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json()

    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> str:
        """Send chat completion request, return assistant message content."""
        await self._rate_limiter.acquire()

        async with self._semaphore:
            payload = {
                "model": self._model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            data = await self._post(payload)

        choices = data.get("choices", [])
        if not choices:
            raise ValueError("LLM returned no choices")
        return choices[0]["message"]["content"]

    async def chat_json(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> dict[str, Any]:
        """Send chat request and parse JSON from response."""
        raw = await self.chat(messages, temperature=temperature, max_tokens=max_tokens)
        return _extract_json(raw)

    async def check_health(self) -> bool:
        """Quick health check against the LLM endpoint."""
        try:
            result = await self.chat(
                [{"role": "user", "content": "Reply with exactly: ok"}],
                temperature=0,
                max_tokens=10,
            )
            return bool(result.strip())
        except Exception:
            logger.exception("LLM health check failed")
            return False


def _extract_json(text: str) -> dict[str, Any]:
    """Extract JSON from LLM response, handling markdown fences."""
    text = text.strip()
    # Strip markdown code fences
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first and last fence lines
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find JSON object in text
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Failed to extract JSON from LLM response: {text[:200]}")
