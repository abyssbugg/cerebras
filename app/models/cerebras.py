from typing import List, Optional, Literal, Union
from pydantic import BaseModel, Field


class CerebrasToolCall(BaseModel):
    """Tool call in response."""
    id: str
    type: Literal["function"] = "function"
    function: dict  # Contains name and arguments


class CerebrasMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]  # Added "tool" role for tool results
    content: Optional[str] = None
    reasoning: Optional[str] = None  # zai-glm-4.7 uses reasoning instead of content
    tool_calls: Optional[List[CerebrasToolCall]] = None  # Tool calls in response
    tool_call_id: Optional[str] = None  # For tool result messages (role="tool")
    
    @property
    def text(self) -> str:
        """Get the actual text content (supports both content and reasoning fields)."""
        return self.content or self.reasoning or ""


class CerebrasTool(BaseModel):
    """Tool definition for function calling."""
    type: Literal["function"] = "function"
    function: dict  # Contains name, description, parameters


class CerebrasToolChoice(BaseModel):
    """Tool choice configuration."""
    type: Literal["auto", "none", "required"] = "auto"


class CerebrasChatRequest(BaseModel):
    model: str
    messages: List[CerebrasMessage]
    max_tokens: Optional[int] = None
    temperature: Optional[float] = Field(default=1.0, ge=0.0, le=2.0)
    top_p: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    stop: Optional[Union[str, List[str]]] = None
    stream: bool = False
    # Tool calling support (OpenAI-compatible format)
    tools: Optional[List[CerebrasTool]] = None
    tool_choice: Optional[Union[str, CerebrasToolChoice]] = None


class CerebrasChoice(BaseModel):
    index: int
    message: CerebrasMessage
    finish_reason: Optional[Literal["stop", "length", "tool_calls"]] = None


class CerebrasUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class CerebrasChatResponse(BaseModel):
    id: str
    object: Literal["chat.completion"] = "chat.completion"
    created: int
    model: str
    choices: List[CerebrasChoice]
    usage: CerebrasUsage


class CerebrasStreamToolCallDelta(BaseModel):
    """Tool call delta in streaming response."""
    index: int
    id: Optional[str] = None
    type: Optional[str] = None
    function: Optional[dict] = None  # Contains name and arguments fragments


class CerebrasStreamDelta(BaseModel):
    role: Optional[str] = None
    content: Optional[str] = None
    reasoning: Optional[str] = None  # zai-glm-4.7 uses reasoning
    tool_calls: Optional[List[CerebrasStreamToolCallDelta]] = None  # Tool calls in streaming
    
    @property
    def text(self) -> str:
        """Get the actual text content."""
        return self.content or self.reasoning or ""


class CerebrasStreamChoice(BaseModel):
    index: int
    delta: CerebrasStreamDelta
    finish_reason: Optional[Literal["stop", "length", "tool_calls"]] = None


class CerebrasStreamChunk(BaseModel):
    id: str
    object: Literal["chat.completion.chunk"] = "chat.completion.chunk"
    created: int
    model: str
    choices: List[CerebrasStreamChoice]
    usage: Optional[CerebrasUsage] = None
