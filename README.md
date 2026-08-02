# Travel Planner

基于 AI Agent 的智能旅行规划工具——输入目的地、天数和偏好，Agent 自动调用天气、景点、路线等工具，流式生成完整行程，高德地图可视化标注。

**在线访问**：[ai-travel-helper.onrender.com](https://ai-travel-helper.onrender.com)

---

## 功能概览

- **旅行规划**：输入目的地、天数、旅行风格，Agent 自动编排工具调用链
- **流式生成**：SSE 实时推送执行状态与行程文案，前端展示完整分析流程
- **地图可视化**：高德地图 JS API 2.0，景点标注 + 分日路线 + 路径优化
- **多轮修改**：支持对已生成行程的追问和调整
- **用户记忆**：Redis + pgvector 长期偏好，开发环境自动降级内存模式
- **PDF 导出**：一键导出行程

---

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Vue 3 · TypeScript · Vite · Tailwind CSS · 高德 JS API 2.0 |
| 后端 | FastAPI · httpx · SSE · Redis · PostgreSQL |
| Agent | DeepSeek · MCP · Planner-Executor · ReAct |
| 部署 | Docker · Render |

---

## 快速开始

### 本地开发

```bash
# 后端
cd backend
cp .env.example .env        # 填入 DEEPSEEK_API_KEY、AMAP_API_KEY
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# 前端（新终端）
npm install
npm run dev
```

前端 `http://localhost:5174`（Vite 代理自动转发 `/api` 到后端）。

### Docker Compose

```bash
cp backend/.env.example backend/.env
docker compose up --build
```

---

## 环境变量

**前端**（`.env.development`）

| 变量 | 说明 |
|------|------|
| `VITE_API_BASE_URL` | 后端地址（开发留空走代理） |
| `VITE_API_SECRET_KEY` | 与后端 `API_SECRET_KEY` 一致 |
| `VITE_AMAP_KEY` | 高德 JS API Key |
| `VITE_AMAP_SECURITY_CODE` | 高德 JS 安全密钥 |

**后端**（`backend/.env`）

| 变量 | 说明 |
|------|------|
| `DEEPSEEK_API_KEY` | DeepSeek API Key |
| `AMAP_API_KEY` | 高德 Web 服务 Key |
| `API_SECRET_KEY` | 前后端鉴权 |
| `REDIS_URL` | Redis（可选，开发用内存模式） |
| `DATABASE_URL` | PostgreSQL（可选，开发用 JSON 文件落地） |

---

## API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/agent/generate` | SSE 流式生成行程 |
| POST | `/api/agent/chat` | SSE 多轮修改 |
| GET | `/api/sessions` | 历史会话 |
| GET/DELETE | `/api/sessions/{id}` | 会话详情 / 删除 |
| GET | `/api/memory` | 用户偏好 |
| GET | `/api/trace/{request_id}` | Agent 执行轨迹 |
| GET | `/api/health/live` | 存活探针 |
| GET | `/api/health/ready` | 就绪探针 |

鉴权：`X-API-Key` + `X-User-Id`

---

## 部署

Docker 单镜像部署，Render 自动构建。环境变量通过 Render Dashboard 配置。

GitHub Actions 每 5 分钟 ping 存活探针，防止免费实例休眠。
