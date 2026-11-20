"""Provider-neutral errors of a language model call."""


class LLMError(RuntimeError):
    """Base class: the model could not produce a response."""


class LLMUnavailableError(LLMError):
    """The provider is unreachable, timed out or returned a server error."""


class LLMRateLimitError(LLMError):
    """The provider rejected the call because of a quota or rate limit (HTTP 429)."""
