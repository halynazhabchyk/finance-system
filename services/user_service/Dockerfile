FROM python:3.12-slim

WORKDIR /app

COPY services/user_service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY libs/shared/ /tmp/shared-pkg/
RUN pip install --no-cache-dir /tmp/shared-pkg && rm -rf /tmp/shared-pkg

COPY services/user_service/ .


EXPOSE 8001

CMD ["sh", "-c", "alembic -c alembic.ini upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8001"]
