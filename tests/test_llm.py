"""Tests for the LLM client utilities."""

from __future__ import annotations

import pytest

from arxiv_recent.llm import _extract_json


def test_extract_json_plain():
    text = '{"key": "value"}'
    assert _extract_json(text) == {"key": "value"}


def test_extract_json_with_fences():
    text = '```json\n{"key": "value"}\n```'
    assert _extract_json(text) == {"key": "value"}


def test_extract_json_with_surrounding_text():
    text = 'Here is the result:\n{"key": "value"}\nDone.'
    assert _extract_json(text) == {"key": "value"}


def test_extract_json_nested():
    text = '{"a": {"b": 1}, "c": [1, 2]}'
    result = _extract_json(text)
    assert result["a"]["b"] == 1
    assert result["c"] == [1, 2]


def test_extract_json_failure():
    with pytest.raises(ValueError, match="Failed to extract JSON"):
        _extract_json("this is not json at all")


def test_extract_json_code_fence_no_lang():
    text = '```\n{"x": 1}\n```'
    assert _extract_json(text) == {"x": 1}
