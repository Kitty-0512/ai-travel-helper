"""Rate limiter unit tests."""

from __future__ import annotations

from app.core.limiter import _parse_rate


def test_parse_rate_minute():
    assert _parse_rate("10/minute") == (10, 60)


def test_parse_rate_hour():
    assert _parse_rate("100/hour") == (100, 3600)
