FROM python:3.12-slim

WORKDIR /app

COPY mcp_server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY pyproject.toml /tmp/shared-pkg/
COPY shared/ /tmp/shared-pkg/shared/
RUN pip install --no-cache-dir /tmp/shared-pkg && rm -rf /tmp/shared-pkg

COPY mcp_server/ .

ENV MCP_TRANSPORT=streamable-http
EXPOSE 8030

CMD ["python", "-m", "app.main"]
