"""Tests for QQ push channel utilities."""

from __future__ import annotations

from arxiv_recent.push.qq import _split_digest


def test_split_short_message():
    text = "arXiv Daily\n1. Paper One\nTL;DR: short"
    chunks = _split_digest(text)
    assert len(chunks) == 1
    assert "Paper One" in chunks[0]


def test_split_long_message():
    # Build a message that exceeds MAX_MSG_LENGTH
    papers = []
    for i in range(1, 20):
        papers.append(f"{i}. Paper Title {i}\n   arXiv: 2401.{i:05d}\n   TL;DR: {'x' * 200}\n")
    text = "arXiv Daily\n=====\n\n" + "\n".join(papers)
    chunks = _split_digest(text)
    assert len(chunks) > 1
    # All content should be preserved
    combined = "\n".join(chunks)
    assert "Paper Title 1" in combined
    assert "Paper Title 19" in combined


def test_split_respects_max_length():
    papers = []
    for i in range(1, 30):
        papers.append(f"{i}. Paper {i}\n   {'content ' * 50}\n")
    text = "\n".join(papers)
    chunks = _split_digest(text)
    for chunk in chunks:
        assert len(chunk) <= 4000  # some margin over MAX_MSG_LENGTH
