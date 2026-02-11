"""Summarize arXiv papers using LLM."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from arxiv_recent.config import get_settings
from arxiv_recent.db import Database
from arxiv_recent.llm import LLMClient

logger = logging.getLogger(__name__)

SUMMARY_SCHEMA = {
    "title_zh": "Chinese translation of the paper title",
    "tldr_zh": "One-sentence TL;DR in Chinese",
    "contributions_zh": ["List of key contributions in Chinese"],
    "method_zh": "Methodology description in Chinese",
    "experiments_zh": "Experiments description in Chinese",
    "results_zh": "Key results in Chinese",
    "limitations_zh": "Limitations in Chinese",
    "who_should_read_zh": "Who should read this paper, in Chinese",
    "links": {"abs": "arXiv abstract URL", "pdf": "arXiv PDF URL"},
}

SUMMARIZE_PROMPT = """\
You are an expert AI research assistant. Given the following arXiv paper metadata, \
produce a structured summary in Chinese (Simplified).

**Paper:**
- Title: {title}
- Authors: {authors}
- Category: {category}
- Abstract: {abstract}
- arXiv URL: {abs_url}
- PDF URL: {pdf_url}

**Instructions:**
1. Output ONLY valid JSON matching this exact schema (no extra text before/after):
{schema}

2. All text fields must be in Simplified Chinese.
3. If any information is not available from the abstract, use "unknown" for that field.
4. The "contributions_zh" field must be a JSON array of strings.
5. The "links" field must contain "abs" and "pdf" keys with the URLs provided above.
6. Do NOT hallucinate any details not present in the abstract.
7. Be concise but informative.

Output the JSON now:\
"""

REPAIR_PROMPT = """\
The following text was supposed to be valid JSON matching this schema:
{schema}

But it failed to parse. Please fix it and return ONLY valid JSON.
Do not add any explanation, just output the corrected JSON.

Broken text:
{broken_text}\
"""


def _build_messages(paper: dict[str, Any]) -> list[dict[str, str]]:
    user_msg = SUMMARIZE_PROMPT.format(
        title=paper["title"],
        authors=paper["authors"],
        category=paper["category"],
        abstract=paper["abstract"],
        abs_url=paper["abs_url"],
        pdf_url=paper["pdf_url"],
        schema=json.dumps(SUMMARY_SCHEMA, indent=2, ensure_ascii=False),
    )
    return [{"role": "user", "content": user_msg}]


def _build_repair_messages(broken_text: str) -> list[dict[str, str]]:
    user_msg = REPAIR_PROMPT.format(
        schema=json.dumps(SUMMARY_SCHEMA, indent=2, ensure_ascii=False),
        broken_text=broken_text[:3000],
    )
    return [{"role": "user", "content": user_msg}]


def _validate_summary(data: dict[str, Any]) -> dict[str, Any]:
    """Ensure summary has all required fields, fill with 'unknown' if missing."""
    defaults: dict[str, Any] = {
        "title_zh": "unknown",
        "tldr_zh": "unknown",
        "contributions_zh": ["unknown"],
        "method_zh": "unknown",
        "experiments_zh": "unknown",
        "results_zh": "unknown",
        "limitations_zh": "unknown",
        "who_should_read_zh": "unknown",
        "links": {"abs": "", "pdf": ""},
    }
    for key, default in defaults.items():
        if key not in data or not data[key]:
            data[key] = default
    if not isinstance(data.get("contributions_zh"), list):
        data["contributions_zh"] = [str(data.get("contributions_zh", "unknown"))]
    if not isinstance(data.get("links"), dict):
        data["links"] = defaults["links"]
    return data


async def summarize_one(
    client: LLMClient,
    paper: dict[str, Any],
) -> dict[str, Any]:
    """Summarize a single paper, with JSON repair fallback."""
    messages = _build_messages(paper)

    try:
        result = await client.chat_json(messages)
        return _validate_summary(result)
    except ValueError:
        logger.warning("JSON parse failed for %s, attempting repair", paper["arxiv_id"])

    # Repair attempt: get raw text and ask LLM to fix it
    try:
        raw = await client.chat(messages)
        repair_msgs = _build_repair_messages(raw)
        result = await client.chat_json(repair_msgs)
        return _validate_summary(result)
    except Exception:
        logger.exception("Repair also failed for %s", paper["arxiv_id"])
        # Return a minimal valid summary
        return _validate_summary(
            {
                "title_zh": paper.get("title", "unknown"),
                "links": {
                    "abs": paper.get("abs_url", ""),
                    "pdf": paper.get("pdf_url", ""),
                },
            }
        )


async def summarize_papers(
    papers: list[dict[str, Any]],
    db: Database,
    settings: Any | None = None,
) -> list[dict[str, Any]]:
    """Summarize multiple papers concurrently, skipping cached ones."""
    cfg = settings or get_settings()
    client = LLMClient(cfg)

    to_summarize = [p for p in papers if not db.has_summary(p["arxiv_id"])]
    logger.info(
        "%d papers to summarize (%d already cached)",
        len(to_summarize),
        len(papers) - len(to_summarize),
    )

    async def _do_one(paper: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        arxiv_id = paper["arxiv_id"]
        try:
            summary = await summarize_one(client, paper)
            # Ensure links are populated
            summary.setdefault("links", {})
            summary["links"]["abs"] = paper["abs_url"]
            summary["links"]["pdf"] = paper["pdf_url"]
            db.save_summary(arxiv_id, summary)
            logger.info("Summarized: %s", arxiv_id)
        except Exception:
            logger.exception("Failed to summarize %s", arxiv_id)
            summary = _validate_summary(
                {
                    "title_zh": paper.get("title", "unknown"),
                    "links": {
                        "abs": paper.get("abs_url", ""),
                        "pdf": paper.get("pdf_url", ""),
                    },
                }
            )
        return arxiv_id, summary

    tasks = [_do_one(p) for p in to_summarize]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Collect all summaries (cached + new)
    all_summaries: list[dict[str, Any]] = []
    for p in papers:
        s = db.get_summary(p["arxiv_id"])
        if s:
            all_summaries.append({**p, "summary": s})
        else:
            all_summaries.append({**p, "summary": None})

    # Log any exceptions from gather
    for r in results:
        if isinstance(r, Exception):
            logger.error("Summarization task exception: %s", r)

    return all_summaries
