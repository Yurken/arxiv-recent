"""Tests for the arXiv fetcher."""

from __future__ import annotations

import xml.etree.ElementTree as ET

from arxiv_recent.fetcher import (
    ATOM_NS,
    _apply_keyword_filter,
    _parse_entry,
)
from tests.conftest import SAMPLE_ATOM_RESPONSE


def test_parse_entry():
    root = ET.fromstring(SAMPLE_ATOM_RESPONSE)
    entries = root.findall(f"{ATOM_NS}entry")
    assert len(entries) == 2

    paper = _parse_entry(entries[0])
    assert paper["arxiv_id"] == "2401.00001"
    assert paper["title"] == "Test Paper on Large Language Models"
    assert "Alice" in paper["authors"]
    assert "Bob" in paper["authors"]
    assert paper["category"] == "cs.CL"
    assert paper["abs_url"] == "http://arxiv.org/abs/2401.00001v1"
    assert paper["pdf_url"] == "http://arxiv.org/pdf/2401.00001v1"
    assert "novel approach" in paper["abstract"]


def test_parse_entry_second():
    root = ET.fromstring(SAMPLE_ATOM_RESPONSE)
    entries = root.findall(f"{ATOM_NS}entry")

    paper = _parse_entry(entries[1])
    assert paper["arxiv_id"] == "2401.00002"
    assert paper["category"] == "cs.AI"


def test_keyword_include_filter():
    papers = [
        {"title": "LLM Paper", "abstract": "About large language models"},
        {"title": "Vision Paper", "abstract": "About computer vision"},
    ]
    result = _apply_keyword_filter(papers, include=["language"], exclude=[])
    assert len(result) == 1
    assert result[0]["title"] == "LLM Paper"


def test_keyword_exclude_filter():
    papers = [
        {"title": "LLM Paper", "abstract": "About large language models"},
        {"title": "Vision Paper", "abstract": "About computer vision"},
    ]
    result = _apply_keyword_filter(papers, include=[], exclude=["vision"])
    assert len(result) == 1
    assert result[0]["title"] == "LLM Paper"


def test_keyword_both_filters():
    papers = [
        {"title": "Good LLM", "abstract": "language models efficient"},
        {"title": "Bad LLM", "abstract": "language models deprecated method"},
        {"title": "Vision", "abstract": "computer vision"},
    ]
    result = _apply_keyword_filter(papers, include=["language"], exclude=["deprecated"])
    assert len(result) == 1
    assert result[0]["title"] == "Good LLM"


def test_keyword_empty_filters():
    papers = [{"title": "A", "abstract": "x"}, {"title": "B", "abstract": "y"}]
    result = _apply_keyword_filter(papers, include=[], exclude=[])
    assert len(result) == 2
