FROM python:3.12-slim

WORKDIR /app

COPY ai_assistant/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ai_assistant/ .
COPY shared/ ./shared/

EXPOSE 8020

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8020"]
