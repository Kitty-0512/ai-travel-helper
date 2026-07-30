"""Shared pytest configuration."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Minimal env so Settings() can initialize during tests.
os.environ.setdefault("DEEPSEEK_API_KEY", "sk-test-key")
os.environ.setdefault("AMAP_API_KEY", "test-amap-key")
os.environ.setdefault("API_SECRET_KEY", "test-secret-key-for-pytest")
os.environ.setdefault("ENV", "development")
os.environ.setdefault("MEMORY_FALLBACK_INPROCESS", "true")
os.environ.setdefault("TRACE_FALLBACK_INPROCESS", "true")
os.environ.setdefault("MCP_ENABLED", "false")

pytest_plugins = ["pytest_asyncio"]


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"
