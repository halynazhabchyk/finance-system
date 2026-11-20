FROM python:3.12-slim

WORKDIR /app

COPY services/budget_agent/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY libs/shared/ /tmp/shared-pkg/
COPY libs/ai_tools/ /tmp/ai-tools-pkg/
RUN pip install --no-cache-dir /tmp/shared-pkg /tmp/ai-tools-pkg && rm -rf /tmp/shared-pkg /tmp/ai-tools-pkg

COPY services/budget_agent/ .

EXPOSE 8041

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8041"]
