"""Render paper digests to Markdown and plain text."""

from __future__ import annotations

import json
from datetime import date
from typing import Any


def render_markdown(papers: list[dict[str, Any]], run_date: str | None = None) -> str:
    """Render a Markdown digest of summarized papers."""
    date_str = run_date or date.today().isoformat()
    lines: list[str] = [
        f"# arXiv Daily Digest - {date_str}",
        "",
        f"**{len(papers)} papers**",
        "",
        "---",
        "",
    ]

    for i, p in enumerate(papers, 1):
        summary = p.get("summary")
        if isinstance(summary, str):
            try:
                summary = json.loads(summary)
            except (json.JSONDecodeError, TypeError):
                summary = None

        title = p.get("title", "Untitled")
        arxiv_id = p.get("arxiv_id", "")
        abs_url = p.get("abs_url", "")
        pdf_url = p.get("pdf_url", "")
        authors = p.get("authors", "")
        category = p.get("category", "")

        lines.append(f"## {i}. {title}")
        lines.append("")
        lines.append(f"**arXiv:** [{arxiv_id}]({abs_url}) | [PDF]({pdf_url})")
        lines.append(f"**Authors:** {authors}")
        lines.append(f"**Category:** {category}")
        lines.append("")

        if summary and isinstance(summary, dict):
            title_zh = summary.get("title_zh", "")
            if title_zh and title_zh != "unknown":
                lines.append(f"**中文标题:** {title_zh}")
                lines.append("")

            tldr = summary.get("tldr_zh", "")
            if tldr and tldr != "unknown":
                lines.append(f"**TL;DR:** {tldr}")
                lines.append("")

            contribs = summary.get("contributions_zh", [])
            if contribs and contribs != ["unknown"]:
                lines.append("**主要贡献:**")
                for c in contribs:
                    lines.append(f"- {c}")
                lines.append("")

            for field, label in [
                ("method_zh", "方法"),
                ("experiments_zh", "实验"),
                ("results_zh", "结果"),
                ("limitations_zh", "局限性"),
                ("who_should_read_zh", "推荐阅读"),
            ]:
                val = summary.get(field, "")
                if val and val != "unknown":
                    lines.append(f"**{label}:** {val}")
                    lines.append("")
        else:
            abstract = p.get("abstract", "")
            if abstract:
                lines.append(f"**Abstract:** {abstract[:500]}")
                lines.append("")

        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def render_plaintext(papers: list[dict[str, Any]], run_date: str | None = None) -> str:
    """Render a plain text digest of summarized papers."""
    date_str = run_date or date.today().isoformat()
    lines: list[str] = [
        f"arXiv Daily Digest - {date_str}",
        f"{len(papers)} papers",
        "=" * 60,
        "",
    ]

    for i, p in enumerate(papers, 1):
        summary = p.get("summary")
        if isinstance(summary, str):
            try:
                summary = json.loads(summary)
            except (json.JSONDecodeError, TypeError):
                summary = None

        title = p.get("title", "Untitled")
        arxiv_id = p.get("arxiv_id", "")
        abs_url = p.get("abs_url", "")
        authors = p.get("authors", "")

        lines.append(f"{i}. {title}")
        lines.append(f"   arXiv: {arxiv_id} | {abs_url}")
        lines.append(f"   Authors: {authors}")

        if summary and isinstance(summary, dict):
            tldr = summary.get("tldr_zh", "")
            if tldr and tldr != "unknown":
                lines.append(f"   TL;DR: {tldr}")
        else:
            abstract = p.get("abstract", "")
            if abstract:
                lines.append(f"   Abstract: {abstract[:300]}")

        lines.append("")

    return "\n".join(lines)
