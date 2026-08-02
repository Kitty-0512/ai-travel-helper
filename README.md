# Travel Planner

基于 AI Agent 的智能旅行规划工具。输入目的地，Agent 自动调用天气、POI、路线等工具，流式生成完整行程，高德地图可视化标注景点与路线。

**在线访问**：[https://ai-travel-helper.onrender.com](https://ai-travel-helper.onrender.com)

**技术栈**：Vue 3 · TypeScript · FastAPI · DeepSeek · MCP · 高德地图 · Tailwind CSS

---

## 功能概览

### 旅行规划
- 输入目的地、天数、旅行风格（美食 / 历史文化 / 自然风光 / 购物 / 艺术 / 冒险）
- Agent Planner-Executor 自动编排工具调用链：天气查询 → POI 搜索 → 路线规划
- SSE 流式推送执行状态与行程文案，前端实时展示

### 地图可视化
- 高德地图 JS API 2.0，景点标注、分日路线渲染
- 驾车 / 步行 / 骑行 / 直线四种路线模式
- 贪心最近邻路径优化

### Agent 能力
- Planner → Executor → Finalize 全链路
- ReAct 多轮对话，支持行程追问与修改
- MCP 工具协议，支持自定义工具扩展
- Agent Trace：完整记录工具调用与执行步骤

### 用户记忆
- Redis + PostgreSQL (pgvector) 长期偏好存储
- 本地开发自动降级到内存模式

### 导出
- 行程 PDF 一键导出

---

## 目录结构

```
ai-travel-helper/
├── src/                         Vue 3 前端
│   ├── components/
│   │   ├── AgentPanel.vue       Agent 输出面板
│   │   └── Map.vue              高德地图组件
│   ├── composables/
│   │   ├── useAgent.ts          Agent SSE 生命周期管理
│   │   ├── useItinerary.ts      行程数据解析
│   │   └── useMapData.ts        路线优化
│   ├── api/
│   │   ├── agent.ts             SSE 流式客户端
│   │   ├── sessions.ts          会话历史 API
│   │   └── memory.ts            用户记忆 API
│   └── utils/
├── backend/                     FastAPI 后端
│   └── app/
│       ├── agents/              Agent 主循环 (Planner-Executor)
│       ├── agent/               Agent 状态与任务模型
│       ├── routers/             API 路由
│       ├── providers/           天气/POI/路线 Provider（含 fallback）
│       ├── mcp/                 MCP 客户端与工具注册
│       ├── memory/              长期用户记忆
│       ├── trace/               Agent 执行追踪
│       ├── session/             会话持久化
│       ├── llm/                 DeepSeek LLM 封装
│       └── core/                配置、安全、限流
├── travel-mcp-server/           MCP 工具服务（POI / 天气 / 路线）
├── sql/                         PostgreSQL 迁移脚本
├── Dockerfile                   统一构建（前端 + 后端 + MCP）
└── docker-compose.yml           本地全栈编排（Redis + PG + 后端 + 前端）
```

---

## 快速开始

### Docker Compose（全栈）

```bash
cp backend/.env.example backend/.env
# 编辑 backend/.env，填入 DEEPSEEK_API_KEY、AMAP_API_KEY、API_SECRET_KEY
docker compose up --build
```

前端 `http://localhost:5173`，后端 `http://localhost:8000/docs`

### 本地开发

**需要**：Node.js 18+、Python 3.11+

```bash
# 后端
cd backend
cp .env.example .env
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# 前端（新终端）
cd ..
npm install
npm run dev
```

前端启动在 `http://localhost:5174`，Vite 代理自动转发 `/api` 到后端。

---

## 环境变量

### 前端

| 变量 | 说明 |
|------|------|
| `VITE_API_BASE_URL` | 后端地址（开发留空走代理） |
| `VITE_API_SECRET_KEY` | 与后端 `API_SECRET_KEY` 一致 |
| `VITE_AMAP_KEY` | 高德 JS API Key（地图渲染） |
| `VITE_AMAP_SECURITY_CODE` | 高德 JS 安全密钥 |

### 后端

| 变量 | 说明 |
|------|------|
| `DEEPSEEK_API_KEY` | DeepSeek API Key |
| `AMAP_API_KEY` | 高德 Web 服务 Key |
| `API_SECRET_KEY` | 前后端鉴权 |
| `REDIS_URL` | Redis 连接串（可选，开发用内存模式） |
| `DATABASE_URL` | PostgreSQL 连接串（可选，开发用 JSON 文件） |
| `ENV` | `development` / `production` |

---

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/agent/generate` | SSE 流式生成行程 |
| POST | `/api/agent/chat` | SSE 多轮对话修改 |
| GET | `/api/sessions` | 历史会话列表 |
| GET | `/api/sessions/{id}` | 会话详情 |
| DELETE | `/api/sessions/{id}` | 删除会话 |
| GET | `/api/memory` | 用户偏好记忆 |
| GET | `/api/trace/{request_id}` | Agent 执行轨迹 |
| GET | `/api/health/live` | 存活探针 |

请求头：`X-API-Key`（鉴权）、`X-User-Id`（用户标识）

---

## 部署

项目部署在 Render，使用根目录 `Dockerfile` 统一构建前端 + 后端 + MCP Server，端口 `8000`。

环境变量通过 Render Dashboard 配置（`DEEPSEEK_API_KEY`、`AMAP_API_KEY`、`API_SECRET_KEY`、`VITE_API_SECRET_KEY`、`VITE_AMAP_KEY`）。

---

## 许可证

MIT License
