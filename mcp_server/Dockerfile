FROM python:3.12-slim

WORKDIR /app

COPY mcp_server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY pyproject.toml /tmp/shared-pkg/
COPY shared/ /tmp/shared-pkg/shared/
COPY libs/ai_tools/ /tmp/ai-tools-pkg/
RUN pip install --no-cache-dir /tmp/shared-pkg /tmp/ai-tools-pkg && rm -rf /tmp/shared-pkg /tmp/ai-tools-pkg

COPY mcp_server/ .

ENV MCP_TRANSPORT=streamable-http
EXPOSE 8030

CMD ["python", "-m", "app.main"]
