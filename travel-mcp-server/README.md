# Travel MCP Server

高德旅行工具 MCP Server（stdio），供 AI Travel Helper Agent 通过 MCP Client 调用。
当前天气、POI、路线均通过统一 Provider 层访问真实 API，而不是让 Agent 直接依赖第三方接口。

## 架构

```text
Agent Backend (MCP Client)
        | stdio JSON-RPC
        v
travel-mcp-server (FastMCP)
        |
        +-- search_place
        +-- get_weather
        +-- calculate_route
                |
                v
         backend/app/providers/*
                |
                v
         backend/app/clients/amap_client.py
                |
                v
            Amap Web API
```

## 工具列表

| MCP Tool | 输入 | 返回 |
|----------|------|------|
| `search_place` | `location`, `keyword?`, `category?` | 景点列表 `pois` |
| `get_weather` | `city`, `days?` | 天气预报 `forecasts` |
| `calculate_route` | `start`, `end`, `city`, `mode?` | 距离/时间 |

返回结果会额外带上：
- `source`: `amap` 或 `fallback`
- `is_fallback`: 是否启用了备用结果
- `warnings`: 备用数据说明（如果有）

## 启动

```bash
cd travel-mcp-server
pip install -r requirements.txt

# 配置高德 Key（可复用 backend/.env）
# AMAP_API_KEY=your-key
# AMAP_BASE_URL=https://restapi.amap.com/v3
# MAP_PROVIDER=amap
# WEATHER_PROVIDER=amap
# PROVIDER_TIMEOUT_SECONDS=10
# PROVIDER_MAX_RETRIES=1
# PROVIDER_ENABLE_FALLBACK=true
# PROVIDER_CACHE_TTL_SECONDS=1800

# 单独运行（stdio，供 Inspector / Client 连接）
set PYTHONPATH=../backend   # Windows
export PYTHONPATH=../backend  # Linux/macOS
python server.py
```

Agent Backend 启动时会自动 spawn 本子进程，一般无需手动启动。

## 调试

### MCP Inspector

```bash
npx @modelcontextprotocol/inspector python server.py
```

（需在 `travel-mcp-server` 目录，并设置 `PYTHONPATH=../backend`）

### Python Client 脚本

```bash
cd backend
python scripts/verify_providers.py
python scripts/verify_mcp_client.py
python scripts/verify_planner_executor.py
```

### 工具调用日志

Backend 会将每次工具调用写入 stdout 和 `logs/tool_calls.jsonl`（可配置 `MCP_TOOL_LOG_PATH`）。

## Fallback 行为

- 天气：优先返回最近成功缓存，否则返回结构化备用天气
- POI：优先返回最近成功缓存，否则返回热门城市种子景点
- 路线：优先返回最近成功缓存，否则基于已缓存坐标给出估算距离；再不行返回降级占位结果

## 示例调用

```python
await client.call_tool("search_place", {"location": "杭州"})
await client.call_tool("get_weather", {"city": "杭州", "days": 2})
await client.call_tool("calculate_route", {
    "start": "西湖",
    "end": "灵隐寺",
    "city": "杭州",
})
```
