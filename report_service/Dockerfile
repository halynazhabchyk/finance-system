FROM python:3.12-slim

WORKDIR /app

COPY report_service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY report_service/ .
COPY shared/ ./shared/

EXPOSE 8003

CMD ["sh", "-c", "alembic -c alembic.ini upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8003"]