FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/backend

COPY backend/requirements.txt ./backend/requirements.txt
COPY travel-mcp-server/requirements.txt ./travel-mcp-server/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt -r travel-mcp-server/requirements.txt

COPY backend/ ./backend/
COPY travel-mcp-server/ ./travel-mcp-server/

WORKDIR /app/backend

ENV MCP_SERVER_SCRIPT=../travel-mcp-server/server.py

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health/live')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
