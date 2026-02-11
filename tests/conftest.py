"""Shared fixtures for tests."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

# Ensure tests don't read real .env
os.environ["ENV_FILE"] = "/dev/null"

from arxiv_recent.config import reset_settings


@pytest.fixture(autouse=True)
def _clean_settings():
    """Reset cached settings between tests."""
    reset_settings()
    yield
    reset_settings()


@pytest.fixture
def tmp_db(tmp_path: Path):
    """Return a Database instance backed by a temp file."""
    from arxiv_recent.db import Database

    db_path = tmp_path / "test.db"
    db = Database(db_path)
    yield db
    db.close()


@pytest.fixture
def sample_paper() -> dict:
    return {
        "arxiv_id": "2401.00001",
        "title": "Test Paper on Large Language Models",
        "authors": "Alice, Bob",
        "category": "cs.CL",
        "published_at": "2024-01-15T00:00:00Z",
        "updated_at": "2024-01-15T00:00:00Z",
        "abs_url": "https://arxiv.org/abs/2401.00001",
        "pdf_url": "https://arxiv.org/pdf/2401.00001",
        "abstract": "We present a novel approach to training large language models.",
    }


@pytest.fixture
def sample_summary() -> dict:
    return {
        "title_zh": "关于大语言模型的测试论文",
        "tldr_zh": "提出了一种训练大语言模型的新方法",
        "contributions_zh": ["贡献1", "贡献2"],
        "method_zh": "使用了新的训练策略",
        "experiments_zh": "在多个基准上进行了测试",
        "results_zh": "取得了SOTA结果",
        "limitations_zh": "计算成本较高",
        "who_should_read_zh": "NLP研究者",
        "links": {
            "abs": "https://arxiv.org/abs/2401.00001",
            "pdf": "https://arxiv.org/pdf/2401.00001",
        },
    }


SAMPLE_ATOM_RESPONSE = """\
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:arxiv="http://arxiv.org/schemas/atom">
  <title>ArXiv Query</title>
  <entry>
    <id>http://arxiv.org/abs/2401.00001v1</id>
    <title>Test Paper on Large Language Models</title>
    <summary>We present a novel approach to training large language models.</summary>
    <published>2024-01-15T00:00:00Z</published>
    <updated>2024-01-15T00:00:00Z</updated>
    <author><name>Alice</name></author>
    <author><name>Bob</name></author>
    <link href="http://arxiv.org/abs/2401.00001v1" rel="alternate" type="text/html"/>
    <link href="http://arxiv.org/pdf/2401.00001v1" title="pdf" type="application/pdf"/>
    <arxiv:primary_category term="cs.CL"/>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2401.00002v1</id>
    <title>Another Paper on Attention Mechanisms</title>
    <summary>We study efficient attention mechanisms for transformers.</summary>
    <published>2024-01-14T00:00:00Z</published>
    <updated>2024-01-14T00:00:00Z</updated>
    <author><name>Charlie</name></author>
    <link href="http://arxiv.org/abs/2401.00002v1" rel="alternate" type="text/html"/>
    <link href="http://arxiv.org/pdf/2401.00002v1" title="pdf" type="application/pdf"/>
    <arxiv:primary_category term="cs.AI"/>
  </entry>
</feed>
"""
