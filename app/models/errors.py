from typing import Literal
from pydantic import BaseModel


class ErrorDetail(BaseModel):
    type: str
    message: str


class AnthropicError(BaseModel):
    type: Literal["error"] = "error"
    error: ErrorDetail


class InvalidRequestError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class AuthenticationError(Exception):
    def __init__(self, message: str = "Invalid API key"):
        self.message = message
        super().__init__(message)


class RateLimitError(Exception):
    def __init__(self, message: str = "Rate limit exceeded"):
        self.message = message
        super().__init__(message)


class OverloadedError(Exception):
    def __init__(self, message: str = "Service temporarily overloaded"):
        self.message = message
        super().__init__(message)


class APIError(Exception):
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class ContextLengthError(Exception):
    """Raised when request exceeds model's context length limit."""
    def __init__(self, current_length: int, max_length: int, message: str = None):
        self.current_length = current_length
        self.max_length = max_length
        self.message = message or (
            f"Context length exceeded: {current_length:,} tokens used, "
            f"but model limit is {max_length:,} tokens. "
            f"Try starting a new conversation or enable truncation with "
            f"TRUNCATION_ENABLED=true and MAX_TOOL_RESULT_CHARS=50000"
        )
        super().__init__(self.message)
