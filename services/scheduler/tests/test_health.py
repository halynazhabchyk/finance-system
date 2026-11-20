"""Health check: 503 until RabbitMQ and the jobs are ready."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routers.system import create_router
from app.core.readiness import Readiness


def client(readiness: Readiness) -> TestClient:
    app = FastAPI()
    app.include_router(create_router(readiness))
    return TestClient(app)


def test_not_ready_is_503():
    response = client(Readiness(rabbitmq_available=True, scheduler_running=False)).get("/internal/health")

    assert response.status_code == 503


def test_ready_is_200():
    response = client(Readiness(rabbitmq_available=True, scheduler_running=True)).get("/internal/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "scheduler"}
