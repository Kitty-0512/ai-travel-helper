"""Executor retry classification tests."""

from __future__ import annotations

from app.agents.executor import _is_retryable_error


def test_unknown_tool_is_not_retryable():
    assert _is_retryable_error({"error": "未知工具: foo"}) is False


def test_timeout_is_retryable():
    assert _is_retryable_error({"error": "工具 search_place 超时（15s）"}) is True
