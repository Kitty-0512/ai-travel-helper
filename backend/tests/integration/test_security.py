"""Security and auth integration tests."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_generate_requires_api_key():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/agent/generate",
            json={"destination": "杭州", "days": 2, "styles": []},
        )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_memory_requires_user_id():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/memory",
            headers={"X-API-Key": "test-secret-key-for-pytest"},
        )
    assert response.status_code in {400, 422}
