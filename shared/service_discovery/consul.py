"""Consul registration and discovery shared by all HTTP services."""

from __future__ import annotations

import json
import os
import random
import socket
from contextlib import contextmanager
from dataclasses import dataclass
from urllib.error import URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


class ConsulError(RuntimeError):
    """Base error for Consul operations."""


class ConsulUnavailableError(ConsulError):
    """Consul could not be reached or returned an invalid response."""


class NoHealthyServiceError(ConsulError):
    """No passing instance was found for a service."""


@dataclass(frozen=True)
class ServiceConfig:
    """Runtime registration settings for one service instance."""

    name: str
    port: int
    address: str
    health_path: str
    service_id: str
    consul_host: str
    consul_port: int
    request_timeout: float
    health_interval: str
    health_timeout: str
    deregister_after: str
    tags: tuple[str, ...]

    @classmethod
    def from_env(cls, default_name: str, default_port: int) -> ServiceConfig:
        name = os.getenv("SERVICE_NAME", default_name)
        configured_id = os.getenv("SERVICE_ID")
        prefix = os.getenv("SERVICE_ID_PREFIX", name)
        hostname = socket.gethostname()
        service_id = configured_id or f"{prefix}-{hostname}"
        tags = tuple(
            tag.strip()
            for tag in os.getenv(
                "CONSUL_TAGS",
                ";".join(default_traefik_tags(name)),
            ).split(";")
            if tag.strip()
        )
        return cls(
            name=name,
            port=int(os.getenv("SERVICE_PORT", str(default_port))),
            address=os.getenv("SERVICE_ADDRESS") or hostname,
            health_path=os.getenv("SERVICE_HEALTH_PATH", "/internal/health"),
            service_id=service_id,
            consul_host=os.getenv("CONSUL_HOST", "localhost"),
            consul_port=int(os.getenv("CONSUL_PORT", "8500")),
            request_timeout=float(os.getenv("CONSUL_REQUEST_TIMEOUT", "5")),
            health_interval=os.getenv("CONSUL_HEALTH_INTERVAL", "10s"),
            health_timeout=os.getenv("CONSUL_HEALTH_TIMEOUT", "3s"),
            deregister_after=os.getenv("CONSUL_DEREGISTER_AFTER", "1m"),
            tags=tags,
        )


class ConsulClient:
    """Small dependency-free client for the Consul HTTP API."""

    def __init__(self, config: ServiceConfig):
        self.config = config

    def _url(self, path: str) -> str:
        return f"http://{self.config.consul_host}:{self.config.consul_port}{path}"

    def register(self) -> None:
        payload = {
            "ID": self.config.service_id,
            "Name": self.config.name,
            "Address": self.config.address,
            "Port": self.config.port,
            "Tags": list(self.config.tags),
            "Check": {
                "HTTP": (
                    f"http://{self.config.address}:{self.config.port}"
                    f"{self.config.health_path}"
                ),
                "Interval": self.config.health_interval,
                "Timeout": self.config.health_timeout,
                "DeregisterCriticalServiceAfter": self.config.deregister_after,
            },
        }
        request = Request(
            self._url("/v1/agent/service/register"),
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="PUT",
        )
        try:
            with urlopen(request, timeout=self.config.request_timeout):
                return
        except (OSError, URLError) as error:
            raise ConsulUnavailableError(
                f"Could not register {self.config.name} in Consul."
            ) from error

    def deregister(self) -> None:
        request = Request(
            self._url(
                f"/v1/agent/service/deregister/"
                f"{quote(self.config.service_id, safe='')}"
            ),
            method="PUT",
        )
        try:
            with urlopen(request, timeout=self.config.request_timeout):
                return
        except (OSError, URLError):
            return

    def discover(self, service_name: str) -> str:
        request = Request(
            self._url(
                f"/v1/health/service/{quote(service_name, safe='')}"
                "?passing=true"
            ),
            method="GET",
        )
        try:
            with urlopen(request, timeout=self.config.request_timeout) as response:
                instances = json.loads(response.read())
        except (OSError, URLError, ValueError) as error:
            raise ConsulUnavailableError(
                f"Could not discover {service_name} through Consul."
            ) from error

        if not isinstance(instances, list) or not instances:
            raise NoHealthyServiceError(
                f"No healthy {service_name} instance is registered in Consul."
            )

        instance = random.choice(instances)
        service = instance.get("Service") or {}
        address = service.get("Address") or (instance.get("Node") or {}).get("Address")
        port = service.get("Port")
        if not address or not port:
            raise ConsulUnavailableError(
                f"Consul returned an incomplete {service_name} instance."
            )
        return f"http://{address}:{port}"


def register_service(config: ServiceConfig) -> None:
    ConsulClient(config).register()


def deregister_service(config: ServiceConfig) -> None:
    ConsulClient(config).deregister()


def consul_enabled() -> bool:
    return os.getenv("CONSUL_ENABLED", "true").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


@contextmanager
def service_registration(config: ServiceConfig):
    """Register one instance and deregister it on graceful shutdown."""
    registered = False
    if consul_enabled():
        register_service(config)
        registered = True
    try:
        yield
    finally:
        if registered:
            deregister_service(config)


def discover_service(
    service_name: str,
    *,
    consul_host: str | None = None,
    consul_port: int | None = None,
    request_timeout: float | None = None,
) -> str:
    config = ServiceConfig(
        name="discovery-client",
        port=0,
        address="",
        health_path="/",
        service_id="discovery-client",
        consul_host=consul_host or os.getenv("CONSUL_HOST", "localhost"),
        consul_port=consul_port or int(os.getenv("CONSUL_PORT", "8500")),
        request_timeout=request_timeout
        if request_timeout is not None
        else float(os.getenv("CONSUL_REQUEST_TIMEOUT", "5")),
        health_interval="",
        health_timeout="",
        deregister_after="",
        tags=(),
    )
    return ConsulClient(config).discover(service_name)


def default_traefik_tags(service_name: str) -> list[str]:
    """Return Catalog Provider tags for the public API route of a service."""
    routes = {
        "user-service": (
            "/api/users",
            "/internal/users",
        ),
        "budget-service": (
            "/api/budgets",
            "/internal/budgets",
        ),
        "report-service": (
            "/api/reports",
            "/internal/reports",
        ),
    }
    route = routes.get(service_name)
    if route is None:
        return []

    public_prefix, internal_prefix = route
    router = service_name
    strip_middleware = f"{service_name}-strip"
    add_middleware = f"{service_name}-internal"
    tags = [
        "traefik.enable=true",
        f"traefik.http.routers.{router}.rule=PathPrefix(`{public_prefix}`)",
        f"traefik.http.routers.{router}.entrypoints=web",
        f"traefik.http.routers.{router}.service={service_name}",
        f"traefik.http.routers.{router}.middlewares={strip_middleware},{add_middleware}",
        f"traefik.http.middlewares.{strip_middleware}.stripprefix.prefixes={public_prefix}",
        f"traefik.http.middlewares.{add_middleware}.addprefix.prefix={internal_prefix}",
    ]
    if service_name == "user-service":
        tags.extend(
            [
                "traefik.http.routers.user-auth.rule=PathPrefix(`/api/users/auth`)",
                "traefik.http.routers.user-auth.priority=100",
                "traefik.http.routers.user-auth.entrypoints=web",
                "traefik.http.routers.user-auth.service=user-service",
                "traefik.http.routers.user-auth.middlewares=user-auth-strip,user-auth-internal",
                "traefik.http.middlewares.user-auth-strip.stripprefix.prefixes=/api/users/auth",
                "traefik.http.middlewares.user-auth-internal.addprefix.prefix=/internal/auth",
            ]
        )
    tags.extend(
        [
            f"traefik.http.routers.{service_name}-docs.rule=PathPrefix(`{public_prefix}/docs`)",
            f"traefik.http.routers.{service_name}-docs.priority=200",
            f"traefik.http.routers.{service_name}-docs.entrypoints=web",
            f"traefik.http.routers.{service_name}-docs.service={service_name}",
            f"traefik.http.routers.{service_name}-docs.middlewares={service_name}-docs-strip",
            f"traefik.http.middlewares.{service_name}-docs-strip.stripprefix.prefixes={public_prefix}",
            f"traefik.http.routers.{service_name}-openapi.rule=Path(`{public_prefix}/openapi.json`)",
            f"traefik.http.routers.{service_name}-openapi.priority=200",
            f"traefik.http.routers.{service_name}-openapi.entrypoints=web",
            f"traefik.http.routers.{service_name}-openapi.service={service_name}",
            f"traefik.http.routers.{service_name}-openapi.middlewares={service_name}-openapi-strip",
            f"traefik.http.middlewares.{service_name}-openapi-strip.stripprefix.prefixes={public_prefix}",
        ]
    )
    return tags
