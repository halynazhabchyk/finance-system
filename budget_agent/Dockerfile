FROM python:3.12-slim

WORKDIR /app

COPY budget_agent/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY pyproject.toml /tmp/shared-pkg/
COPY shared/ /tmp/shared-pkg/shared/
RUN pip install --no-cache-dir /tmp/shared-pkg && rm -rf /tmp/shared-pkg

COPY budget_agent/ .

EXPOSE 8041

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8041"]
