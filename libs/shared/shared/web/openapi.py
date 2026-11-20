"""Shared helpers for public gateway OpenAPI documents."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi


def install_public_openapi(
    app: FastAPI,
    *,
    path_mappings: Mapping[str, str],
) -> None:
    """Expose only gateway paths in the service OpenAPI document."""

    def custom_openapi() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema

        schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
        )
        public_paths: dict[str, Any] = {}
        for path, operation in schema["paths"].items():
            for internal_prefix, public_prefix in path_mappings.items():
                if path == internal_prefix or path.startswith(f"{internal_prefix}/"):
                    suffix = path.removeprefix(internal_prefix)
                    public_paths[f"{public_prefix}{suffix}"] = operation
                    break

        schema["paths"] = public_paths
        schema["servers"] = [{"url": ""}]
        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi
