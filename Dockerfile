# ── 阶段一：构建前端 ──
FROM node:20-alpine AS frontend-build

WORKDIR /build

# 安装 pnpm（比 corepack enable 更稳）
RUN npm install -g pnpm
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --no-frozen-lockfile
COPY . .

# 空 = 同源请求，部署后前端通过 FastAPI 直接访问 /api
# 高德 JS Key 仅通过构建参数注入，不要写进仓库
ARG VITE_API_BASE_URL=
ARG VITE_API_SECRET_KEY=kitty-travel
ARG VITE_AMAP_KEY=
ARG VITE_AMAP_SECURITY_CODE=
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL \
    VITE_API_SECRET_KEY=$VITE_API_SECRET_KEY \
    VITE_AMAP_KEY=$VITE_AMAP_KEY \
    VITE_AMAP_SECURITY_CODE=$VITE_AMAP_SECURITY_CODE

RUN pnpm build

# ── 阶段二：运行后端 + MCP + 托管前端 ──
FROM python:3.12-slim

WORKDIR /app/backend

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/backend

# 安装 Python 依赖
COPY backend/requirements.txt ./requirements.txt
COPY travel-mcp-server/requirements.txt /tmp/mcp-requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir \
        -r requirements.txt \
        -r /tmp/mcp-requirements.txt

# 复制后端 + MCP Server
COPY backend/ ./
COPY travel-mcp-server/ ../travel-mcp-server/

# 复制前端产物
COPY --from=frontend-build /build/dist ../static

# 开发模式 → 允许进程内 fallback，无需 Redis/PostgreSQL
ENV ENV=development \
    MCP_SERVER_SCRIPT=../travel-mcp-server/server.py \
    STATIC_DIR=../static

EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
