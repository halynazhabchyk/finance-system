"""Login through User Service (the same JWT every component uses).

The password is sent only to User Service and is never printed or logged;
the token lives only in the memory of the running client.
"""

from __future__ import annotations

import httpx

LOGIN_PATH = "/api/users/auth/login"

# User Service maps AuthenticationError -> 401 and PermissionDeniedError -> 403 (shared/web/errors.py).
_STATUS_MESSAGES: dict[int, str] = {
    401: "Невірний email або пароль.",
    403: "Обліковий запис заблоковано.",
    404: "Gateway не знайшов маршрут входу: User Service ще не зареєстрований у Consul. Зачекайте й повторіть.",
    422: "Вкажіть email і пароль.",
}


class LoginFailed(Exception):
    """The user could not log in; the message is safe to show to the user."""


async def login(
    gateway_url: str,
    email: str,
    password: str,
    *,
    timeout_seconds: float = 10.0,
    transport: httpx.AsyncBaseTransport | None = None,
) -> str:
    """Return the access token of the user.

    Raises ``LoginFailed`` with a user-facing message for empty credentials, wrong
    credentials, a blocked account, an unreachable gateway or an unexpected reply.
    """
    if not email.strip() or not password:
        raise LoginFailed(_STATUS_MESSAGES[422])

    try:
        async with httpx.AsyncClient(base_url=gateway_url, timeout=timeout_seconds, transport=transport) as http:
            response = await http.post(LOGIN_PATH, data={"username": email.strip(), "password": password})
    except httpx.TimeoutException as error:
        raise LoginFailed(f"Gateway {gateway_url} не відповів за {timeout_seconds:.0f} с.") from error
    except httpx.HTTPError as error:
        raise LoginFailed(f"Gateway {gateway_url} недоступний ({type(error).__name__}). Чи запущено docker compose?") from error

    if response.status_code in _STATUS_MESSAGES:
        raise LoginFailed(_STATUS_MESSAGES[response.status_code])
    if response.status_code >= 500:
        raise LoginFailed(f"User Service тимчасово недоступний (HTTP {response.status_code}). Спробуйте пізніше.")
    if response.status_code != 200:
        raise LoginFailed(f"User Service відповів HTTP {response.status_code}.")

    try:
        token = response.json().get("access_token")
    except (ValueError, AttributeError) as error:
        raise LoginFailed("User Service повернув відповідь не у форматі JSON.") from error
    if not isinstance(token, str) or not token:
        raise LoginFailed("User Service не повернув access_token.")
    return token
