FROM python:3.12-slim

WORKDIR /app

COPY mcp_server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY mcp_server/ .
COPY shared/ ./shared/

ENV MCP_TRANSPORT=streamable-http
EXPOSE 8030

CMD ["python", "-m", "app.main"]
