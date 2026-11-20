FROM python:3.12-slim

WORKDIR /app

COPY services/budget_service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY libs/shared/ /tmp/shared-pkg/
RUN pip install --no-cache-dir /tmp/shared-pkg && rm -rf /tmp/shared-pkg

COPY services/budget_service/ .

EXPOSE 8002

CMD ["sh", "-c", "alembic -c alembic.ini upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8002"]
