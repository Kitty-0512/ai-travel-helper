"""应用配置 —— pydantic-settings 自动从 .env / 环境变量加载"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings

# Compute absolute .env path so MCP subprocess can load config regardless of cwd
_ENV_FILE = str(Path(__file__).resolve().parent.parent.parent / ".env")


class Settings(BaseSettings):
    # ── DeepSeek ──
    deepseek_api_key: str
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    deepseek_max_tokens: int = 4000
    deepseek_timeout: int = 60  # 秒
    deepseek_max_retries: int = 2
    deepseek_retry_backoff_seconds: float = 1.0
    deepseek_message_char_budget: int = 24000

    # ── 高德地图 ──
    amap_api_key: str
    amap_base_url: str = "https://restapi.amap.com/v3"
    map_provider: str = "amap"
    weather_provider: str = "amap"
    provider_timeout_seconds: int = 10
    provider_max_retries: int = 1
    provider_enable_fallback: bool = True
    provider_cache_ttl_seconds: int = 1800

    # ── 本后端安全 ──
    api_secret_key: str = "change-me-to-a-random-string"
    cors_allow_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://localhost:5174",
            "http://localhost:5175",
            "http://localhost:5176",
            "http://localhost:5177",
            "http://localhost:4173",
        ]
    )

    # ── Agent ──
    agent_max_steps: int = 8
    tool_timeout: int = 15  # 秒
    tool_max_retries: int = 1
    planner_timeout: int = 45
    executor_timeout: int = 120
    finalize_timeout: int = 45
    sse_idle_timeout: int = 300

    # ── Agent Memory ──
    memory_enabled: bool = True
    redis_url: str = "redis://localhost:6379/0"
    database_url: str = "postgresql://travel:travel@localhost:5432/travel_helper"
    memory_redis_ttl_seconds: int = 604800  # 7 days
    memory_top_k: int = 8
    embedding_dim: int = 1536
    # Optional OpenAI-compatible embedding endpoint; empty → local hash embedding
    embedding_api_key: str = ""
    embedding_base_url: str = ""
    embedding_model: str = "text-embedding-3-small"
    # When Redis/PG unavailable, use in-process store so Memory API still works locally
    memory_fallback_inprocess: bool = True

    # ── Agent Trace ──
    trace_enabled: bool = True
    trace_fallback_inprocess: bool = True

    # ── 限流 ──
    rate_limit_enabled: bool = True
    rate_limit_backend: str = "redis"
    rate_limit_generate: str = "10/minute"
    rate_limit_chat: str = "15/minute"
    rate_limit_default: str = "30/minute"

    # ── MCP (Travel MCP Server) ──
    mcp_enabled: bool = True
    mcp_server_command: str = "python"
    mcp_server_script: str = "../travel-mcp-server/server.py"
    mcp_timeout: int = 20
    mcp_tool_log_path: str = "logs/tool_calls.jsonl"

    # ── 服务 ──
    port: int = 8000
    env: str = "development"
    static_dir: str = "static"

    model_config = {
        "env_file": _ENV_FILE,
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    @property
    def is_production(self) -> bool:
        return self.env.lower() == "production"

    @model_validator(mode="after")
    def validate_production_safety(self) -> "Settings":
        if self.is_production:
            if self.api_secret_key == "change-me-to-a-random-string" or len(self.api_secret_key) < 16:
                raise ValueError("生产环境必须设置强随机 API_SECRET_KEY")
            if self.memory_fallback_inprocess:
                raise ValueError("生产环境禁止 MEMORY_FALLBACK_INPROCESS=true")
            if self.trace_fallback_inprocess:
                raise ValueError("生产环境禁止 TRACE_FALLBACK_INPROCESS=true")
            if not self.cors_allow_origins:
                raise ValueError("生产环境必须配置 CORS_ALLOW_ORIGINS")
        return self


settings = Settings()
