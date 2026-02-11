"""Fetch papers from the arXiv Atom API."""

from __future__ import annotations

import logging
import re
import time
import xml.etree.ElementTree as ET
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from arxiv_recent.config import Settings, get_settings

logger = logging.getLogger(__name__)

ARXIV_API_URL = "https://export.arxiv.org/api/query"
ATOM_NS = "{http://www.w3.org/2005/Atom}"
ARXIV_NS = "{http://arxiv.org/schemas/atom}"


def _build_query(categories: list[str]) -> str:
    parts = [f"cat:{cat}" for cat in categories]
    return " OR ".join(parts)


def _text(el: ET.Element | None) -> str:
    if el is None:
        return ""
    return (el.text or "").strip()


def _clean_whitespace(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _parse_entry(entry: ET.Element) -> dict[str, Any]:
    arxiv_id_raw = _text(entry.find(f"{ATOM_NS}id"))
    arxiv_id = arxiv_id_raw.split("/abs/")[-1] if "/abs/" in arxiv_id_raw else arxiv_id_raw
    # Strip version suffix for dedup
    arxiv_id = re.sub(r"v\d+$", "", arxiv_id)

    title = _clean_whitespace(_text(entry.find(f"{ATOM_NS}title")))
    abstract = _clean_whitespace(_text(entry.find(f"{ATOM_NS}summary")))
    published = _text(entry.find(f"{ATOM_NS}published"))
    updated = _text(entry.find(f"{ATOM_NS}updated"))

    authors: list[str] = []
    for author_el in entry.findall(f"{ATOM_NS}author"):
        name = _text(author_el.find(f"{ATOM_NS}name"))
        if name:
            authors.append(name)

    # Primary category
    primary_cat_el = entry.find(f"{ARXIV_NS}primary_category")
    category = primary_cat_el.get("term", "") if primary_cat_el is not None else ""

    # Links
    abs_url = ""
    pdf_url = ""
    for link in entry.findall(f"{ATOM_NS}link"):
        href = link.get("href", "")
        link_type = link.get("type", "")
        link_title = link.get("title", "")
        if link_title == "pdf" or link_type == "application/pdf":
            pdf_url = href
        elif link.get("rel") == "alternate":
            abs_url = href

    if not abs_url:
        abs_url = f"https://arxiv.org/abs/{arxiv_id}"
    if not pdf_url:
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}"

    return {
        "arxiv_id": arxiv_id,
        "title": title,
        "authors": ", ".join(authors),
        "category": category,
        "published_at": published,
        "updated_at": updated,
        "abs_url": abs_url,
        "pdf_url": pdf_url,
        "abstract": abstract,
    }


def _apply_keyword_filter(
    papers: list[dict[str, Any]],
    include: list[str],
    exclude: list[str],
) -> list[dict[str, Any]]:
    result = []
    for p in papers:
        text = f"{p['title']} {p['abstract']}".lower()
        if exclude and any(kw.lower() in text for kw in exclude):
            continue
        if include and not any(kw.lower() in text for kw in include):
            continue
        result.append(p)
    return result


def _apply_time_filter(papers: list[dict[str, Any]], hours: int) -> list[dict[str, Any]]:
    cutoff = datetime.now(UTC) - timedelta(hours=hours)
    result = []
    for p in papers:
        try:
            pub = datetime.fromisoformat(p["published_at"].replace("Z", "+00:00"))
            if pub >= cutoff:
                result.append(p)
        except (ValueError, TypeError):
            result.append(p)
    return result


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=3, min=10, max=120),
    reraise=True,
)
def _fetch_arxiv_page(
    client: httpx.Client,
    query: str,
    start: int,
    max_results: int,
) -> list[dict[str, Any]]:
    params = {
        "search_query": query,
        "start": str(start),
        "max_results": str(max_results),
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    resp = client.get(ARXIV_API_URL, params=params, timeout=30.0)
    resp.raise_for_status()

    root = ET.fromstring(resp.text)
    entries = root.findall(f"{ATOM_NS}entry")
    return [_parse_entry(e) for e in entries]


def fetch_papers(settings: Settings | None = None) -> list[dict[str, Any]]:
    """Fetch papers from arXiv API, apply filters, return list of dicts."""
    cfg = settings or get_settings()
    if not cfg.arxiv_categories:
        logger.warning("No arXiv categories configured")
        return []

    query = _build_query(cfg.arxiv_categories)
    # Fetch more than needed to allow filtering
    fetch_limit = min(cfg.max_papers_per_day * 3, 300)
    page_size = 100

    all_papers: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    headers = {"User-Agent": "arxiv-recent/0.1.0 (https://github.com)"}
    with httpx.Client(headers=headers) as client:
        for page_idx, start in enumerate(range(0, fetch_limit, page_size)):
            # arXiv requires >= 3s between requests
            if page_idx > 0:
                time.sleep(4)
            batch_size = min(page_size, fetch_limit - start)
            try:
                batch = _fetch_arxiv_page(client, query, start, batch_size)
            except Exception:
                logger.exception("Failed to fetch arXiv page start=%d", start)
                break

            if not batch:
                break

            for p in batch:
                if p["arxiv_id"] not in seen_ids:
                    seen_ids.add(p["arxiv_id"])
                    all_papers.append(p)

            if len(batch) < batch_size:
                break

    logger.info("Fetched %d raw papers from arXiv", len(all_papers))

    papers = _apply_time_filter(all_papers, cfg.time_window_hours)
    logger.info("%d papers within time window (%dh)", len(papers), cfg.time_window_hours)

    papers = _apply_keyword_filter(papers, cfg.arxiv_include_keywords, cfg.arxiv_exclude_keywords)
    logger.info("%d papers after keyword filter", len(papers))

    papers = papers[: cfg.max_papers_per_day]
    logger.info("Returning %d papers (max %d)", len(papers), cfg.max_papers_per_day)

    return papers
