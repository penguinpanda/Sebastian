class SebastianError(Exception):
    """Base error for Sebastian domain failures."""


class NotFoundError(SebastianError):
    """Raised when a requested resource is missing."""


class ValidationError(SebastianError):
    """Raised when input data is not valid for a domain action."""


class LLMError(SebastianError):
    """Raised when an LLM API call fails or returns unexpected output."""


_LLM_UNAVAILABLE_MESSAGE = "无法使用LLM服务，请检查LLM配置或服务状态。"


class LLMUnavailableError(SebastianError):
    """Raised when LLM is not configured, not reachable, or disabled.

    All agents MUST raise this error instead of returning template/mock/fallback content.
    """

    def __init__(self, detail: str = "") -> None:
        message = _LLM_UNAVAILABLE_MESSAGE
        if detail:
            message = f"{message} 详情: {detail}"
        super().__init__(message)


def llm_unavailable_message() -> str:
    """Return the canonical LLM-unavailable message used across all agents."""
    return _LLM_UNAVAILABLE_MESSAGE
