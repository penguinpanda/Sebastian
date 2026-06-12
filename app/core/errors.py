class SebastianError(Exception):
    """Base error for Sebastian domain failures."""


class NotFoundError(SebastianError):
    """Raised when a requested resource is missing."""


class ValidationError(SebastianError):
    """Raised when input data is not valid for a domain action."""


class LLMError(SebastianError):
    """Raised when an LLM API call fails or returns unexpected output."""
