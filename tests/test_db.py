"""Tests for the database layer."""

from __future__ import annotations

from arxiv_recent.db import Database


def test_upsert_paper(tmp_db: Database, sample_paper: dict):
    assert tmp_db.upsert_paper(sample_paper) is True
    # Duplicate insert should return False
    assert tmp_db.upsert_paper(sample_paper) is False


def test_upsert_papers_bulk(tmp_db: Database, sample_paper: dict):
    paper2 = {**sample_paper, "arxiv_id": "2401.00002", "title": "Paper 2"}
    count = tmp_db.upsert_papers([sample_paper, paper2, sample_paper])
    assert count == 2


def test_papers_without_summary(tmp_db: Database, sample_paper: dict):
    tmp_db.upsert_paper(sample_paper)
    unsummarized = tmp_db.get_papers_without_summary()
    assert len(unsummarized) == 1
    assert unsummarized[0]["arxiv_id"] == "2401.00001"


def test_save_and_get_summary(tmp_db: Database, sample_paper: dict, sample_summary: dict):
    tmp_db.upsert_paper(sample_paper)
    tmp_db.save_summary("2401.00001", sample_summary)

    assert tmp_db.has_summary("2401.00001") is True
    assert tmp_db.has_summary("2401.99999") is False

    retrieved = tmp_db.get_summary("2401.00001")
    assert retrieved is not None
    assert retrieved["title_zh"] == "关于大语言模型的测试论文"


def test_no_unsummarized_after_save(tmp_db: Database, sample_paper: dict, sample_summary: dict):
    tmp_db.upsert_paper(sample_paper)
    tmp_db.save_summary("2401.00001", sample_summary)
    assert tmp_db.get_papers_without_summary() == []


def test_run_tracking(tmp_db: Database):
    assert tmp_db.get_run("2024-01-15") is None

    tmp_db.upsert_run("2024-01-15", "pending")
    run = tmp_db.get_run("2024-01-15")
    assert run is not None
    assert run["status"] == "pending"

    tmp_db.upsert_run("2024-01-15", "sent", "email")
    run = tmp_db.get_run("2024-01-15")
    assert run["status"] == "sent"
    assert run["sent_channels"] == "email"


def test_was_sent_and_mark(tmp_db: Database):
    assert tmp_db.was_sent("2024-01-15", "email") is False

    tmp_db.mark_sent("2024-01-15", "email")
    assert tmp_db.was_sent("2024-01-15", "email") is True
    assert tmp_db.was_sent("2024-01-15", "telegram") is False

    tmp_db.mark_sent("2024-01-15", "telegram")
    assert tmp_db.was_sent("2024-01-15", "telegram") is True
    assert tmp_db.was_sent("2024-01-15", "email") is True
