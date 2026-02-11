"""Tests for the renderer."""

from __future__ import annotations

from arxiv_recent.renderer import render_markdown, render_plaintext


def _make_papers(summary: dict | None = None) -> list[dict]:
    return [
        {
            "arxiv_id": "2401.00001",
            "title": "Test Paper",
            "authors": "Alice, Bob",
            "category": "cs.CL",
            "abs_url": "https://arxiv.org/abs/2401.00001",
            "pdf_url": "https://arxiv.org/pdf/2401.00001",
            "abstract": "A test abstract.",
            "summary": summary,
        }
    ]


def test_markdown_with_summary():
    summary = {
        "title_zh": "测试论文",
        "tldr_zh": "这是一篇测试论文",
        "contributions_zh": ["贡献一"],
        "method_zh": "方法描述",
        "experiments_zh": "实验描述",
        "results_zh": "结果描述",
        "limitations_zh": "局限性",
        "who_should_read_zh": "研究者",
        "links": {
            "abs": "https://arxiv.org/abs/2401.00001",
            "pdf": "https://arxiv.org/pdf/2401.00001",
        },
    }
    md = render_markdown(_make_papers(summary), "2024-01-15")
    assert "# arXiv Daily Digest - 2024-01-15" in md
    assert "测试论文" in md
    assert "贡献一" in md
    assert "2401.00001" in md


def test_markdown_without_summary():
    md = render_markdown(_make_papers(None), "2024-01-15")
    assert "Test Paper" in md
    assert "A test abstract" in md


def test_plaintext_with_summary():
    summary = {
        "title_zh": "测试论文",
        "tldr_zh": "这是一篇测试论文",
        "contributions_zh": [],
        "method_zh": "",
        "experiments_zh": "",
        "results_zh": "",
        "limitations_zh": "",
        "who_should_read_zh": "",
        "links": {},
    }
    txt = render_plaintext(_make_papers(summary), "2024-01-15")
    assert "arXiv Daily Digest" in txt
    assert "这是一篇测试论文" in txt


def test_plaintext_without_summary():
    txt = render_plaintext(_make_papers(None), "2024-01-15")
    assert "A test abstract" in txt


def test_markdown_paper_count():
    papers = _make_papers() + [
        {
            **_make_papers()[0],
            "arxiv_id": "2401.00002",
            "title": "Second Paper",
        }
    ]
    md = render_markdown(papers, "2024-01-15")
    assert "**2 papers**" in md


def test_summary_as_json_string():
    """Summary stored as JSON string should be parsed."""
    import json

    summary = {
        "title_zh": "字符串摘要",
        "tldr_zh": "TL;DR",
        "contributions_zh": [],
        "method_zh": "",
        "experiments_zh": "",
        "results_zh": "",
        "limitations_zh": "",
        "who_should_read_zh": "",
        "links": {},
    }
    papers = [
        {
            "arxiv_id": "2401.00001",
            "title": "Test",
            "authors": "A",
            "category": "cs.CL",
            "abs_url": "https://arxiv.org/abs/2401.00001",
            "pdf_url": "https://arxiv.org/pdf/2401.00001",
            "abstract": "abs",
            "summary": json.dumps(summary, ensure_ascii=False),
        }
    ]
    md = render_markdown(papers, "2024-01-15")
    assert "字符串摘要" in md
