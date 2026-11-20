FROM python:3.12-slim

WORKDIR /app

COPY report_agent/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY pyproject.toml /tmp/shared-pkg/
COPY shared/ /tmp/shared-pkg/shared/
RUN pip install --no-cache-dir /tmp/shared-pkg && rm -rf /tmp/shared-pkg

COPY report_agent/ .

EXPOSE 8042

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8042"]
