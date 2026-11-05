FROM python:3.12-slim

WORKDIR /app

COPY budget_service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY budget_service/ .
COPY shared/ ./shared/

EXPOSE 8002

CMD ["sh", "-c", "alembic -c alembic.ini upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8002"]
