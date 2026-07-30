# ── 阶段一：构建前端 ──
FROM node:20-alpine AS frontend-build

WORKDIR /build
RUN corepack enable
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY . .

# 空 = 同源请求，部署后前端通过 FastAPI 直接访问 /api
ARG VITE_API_BASE_URL=
ARG VITE_API_SECRET_KEY=change-me-to-a-random-string
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
ENV VITE_API_SECRET_KEY=$VITE_API_SECRET_KEY

RUN pnpm build

# ── 阶段二：运行后端 + MCP + 托管前端 ──
FROM python:3.12-slim

WORKDIR /app/backend

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/backend

# 安装依赖
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
