# Travel Planner

基于 AI Agent 的智能旅行规划工具——输入目的地、天数和偏好，Agent 自动调用天气、景点、路线等工具，流式生成完整行程，高德地图可视化标注。

> 在线演示环境可能因云厂商免费额度暂停；推荐 **GitHub 本页截图 + 本地运行** 演示。

---

## 界面演示

左侧在「生成行程」按钮上方展示 **Agent 执行流程** 四步豆豆：`理解需求 → 调用工具 → 生成行程 → 完成`，随 SSE 状态点亮。

### 1. 初始空状态

填写前的工作台：左侧表单 + 流程豆豆（未开始）+ 右侧空态提示与地图底图。

![01 初始空状态](docs/screenshots/01-empty.png)

### 2. 填写需求，准备生成

输入目的地「杭州」、天数「3」，勾选旅行风格；底部流程豆豆仍待命，主按钮可点「生成行程」。

![02 填写表单](docs/screenshots/02-form-ready.png)

### 3. 启动 Agent（豆豆进入第 1 步）

点击生成后，豆豆高亮「理解需求」，按钮变为「生成中…」，右侧出现执行状态条。

![03 生成中-理解需求](docs/screenshots/03-generating-flow.png)

### 4. 工具调用与撰写行程（豆豆推进）

Agent 完成工具调用后进入「生成行程」；右侧可见「工具调用 (N)」折叠区与流式 Markdown 行程文案（如「杭州 · 3 天行程」）。

![04 工具与文案生成](docs/screenshots/05-result.png)

### 5. 行程 + 地图工作台

同一屏展示：左侧流程进度、右侧行程正文与「地图与路线规划」（驾车/步行/骑行/最短路径等）。

![05 行程与地图](docs/screenshots/06-map.png)

更多截图说明见 [`docs/screenshots/README.md`](docs/screenshots/README.md)。

---

## 功能概览

- **旅行规划**：输入目的地、天数、旅行风格，Agent 自动编排工具调用链
- **流程可视化**：生成按钮上方四步豆豆，同步 SSE 执行阶段
- **流式生成**：SSE 实时推送执行状态与行程文案
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
| 部署 | Docker · Render（可选） |

---

## 快速开始

### 本地开发

```bash
# 后端（默认 8000；若端口被占用可改 --port 8001，并同步改 vite.config.ts 代理）
cd backend
cp .env.example .env        # 填入 DEEPSEEK_API_KEY、AMAP_API_KEY
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# 前端（新终端）
npm install
npm run dev
```

前端 `http://localhost:5174`（`VITE_API_BASE_URL` 留空时，Vite 把 `/api` 代理到后端）。

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

Docker 单镜像可部署到 Render / Railway 等。免费额度用尽后线上会暂停，可用本仓库截图与本地运行做演示。
