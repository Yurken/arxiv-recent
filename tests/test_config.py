"""Tests for configuration."""

from __future__ import annotations

from arxiv_recent.config import Settings


def test_defaults():
    s = Settings()
    assert "cs.CL" in s.arxiv_categories
    assert s.max_papers_per_day == 50
    assert s.llm_max_concurrency == 4


def test_comma_split():
    s = Settings(arxiv_categories_str="cs.CL,cs.AI,cs.LG")
    assert s.arxiv_categories == ["cs.CL", "cs.AI", "cs.LG"]


def test_empty_comma_split():
    s = Settings(arxiv_categories_str="")
    assert s.arxiv_categories == []


def test_email_configured():
    s = Settings(smtp_host="smtp.example.com", email_from="a@b.com", email_to="c@d.com")
    assert s.email_configured is True


def test_email_not_configured():
    s = Settings()
    assert s.email_configured is False


def test_telegram_configured():
    s = Settings(telegram_bot_token="123:ABC", telegram_chat_id="456")
    assert s.telegram_configured is True


def test_telegram_not_configured():
    s = Settings()
    assert s.telegram_configured is False
