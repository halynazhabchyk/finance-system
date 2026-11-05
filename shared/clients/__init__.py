"""Shared clients for synchronous service-to-service communication."""

from .user_service import validate_user_token

__all__ = ["validate_user_token"]
