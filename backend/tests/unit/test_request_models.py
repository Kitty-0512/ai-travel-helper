from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models.request import GenerateRequest


def test_generate_request_rejects_unsupported_style():
    with pytest.raises(ValidationError):
        GenerateRequest(destination="杭州", days=2, styles=["不存在的风格"])


def test_generate_request_trims_destination():
    req = GenerateRequest(destination="  杭州  ", days=2, styles=[])
    assert req.destination == "杭州"
