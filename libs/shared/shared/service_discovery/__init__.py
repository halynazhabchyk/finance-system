"""Service discovery integrations shared by the microservices."""

from .consul import (
    ConsulClient,
    ConsulError,
    ConsulUnavailableError,
    NoHealthyServiceError,
    ServiceConfig,
    consul_enabled,
    deregister_service,
    discover_service,
    register_service,
    service_registration,
)

__all__ = [
    "ConsulClient",
    "ConsulError",
    "ConsulUnavailableError",
    "NoHealthyServiceError",
    "ServiceConfig",
    "consul_enabled",
    "deregister_service",
    "discover_service",
    "register_service",
    "service_registration",
]
