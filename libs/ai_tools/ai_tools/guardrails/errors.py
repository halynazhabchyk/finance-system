"""A guardrail stopped a request before it reached the model or the API."""


class GuardrailViolation(Exception):
    """``code`` is machine readable (logged, returned to clients); ``user_message`` is shown to the user."""

    def __init__(self, code: str, user_message: str) -> None:
        super().__init__(user_message)
        self.code = code
        self.user_message = user_message
