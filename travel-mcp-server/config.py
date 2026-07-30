"""Travel MCP Server configuration."""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load backend .env first, then local override
_root = Path(__file__).resolve().parent
load_dotenv(_root.parent / "backend" / ".env")
load_dotenv(_root / ".env")

AMAP_API_KEY = os.getenv("AMAP_API_KEY", "")
AMAP_BASE_URL = os.getenv("AMAP_BASE_URL", "https://restapi.amap.com/v3")
