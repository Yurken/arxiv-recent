"""Tests for the summarizer."""

from __future__ import annotations

from arxiv_recent.summarizer import _validate_summary


def test_validate_summary_full():
    data = {
        "title_zh": "测试",
        "tldr_zh": "TL;DR",
        "contributions_zh": ["c1"],
        "method_zh": "m",
        "experiments_zh": "e",
        "results_zh": "r",
        "limitations_zh": "l",
        "who_should_read_zh": "w",
        "links": {"abs": "url1", "pdf": "url2"},
    }
    result = _validate_summary(data)
    assert result["title_zh"] == "测试"
    assert result["contributions_zh"] == ["c1"]


def test_validate_summary_missing_fields():
    data: dict = {}
    result = _validate_summary(data)
    assert result["title_zh"] == "unknown"
    assert result["tldr_zh"] == "unknown"
    assert isinstance(result["contributions_zh"], list)
    assert result["links"] == {"abs": "", "pdf": ""}


def test_validate_summary_wrong_contributions_type():
    data = {
        "title_zh": "t",
        "contributions_zh": "single string instead of list",
    }
    result = _validate_summary(data)
    assert isinstance(result["contributions_zh"], list)
    assert "single string instead of list" in result["contributions_zh"]


def test_validate_summary_wrong_links_type():
    data = {"links": "not a dict"}
    result = _validate_summary(data)
    assert isinstance(result["links"], dict)
    assert "abs" in result["links"]
