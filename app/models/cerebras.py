from typing import List, Optional, Literal, Union
from pydantic import BaseModel, Field


class CerebrasMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class CerebrasChatRequest(BaseModel):
    model: str
    messages: List[CerebrasMessage]
    max_tokens: Optional[int] = None
    temperature: Optional[float] = Field(default=1.0, ge=0.0, le=2.0)
    top_p: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    stop: Optional[Union[str, List[str]]] = None
    stream: bool = False


class CerebrasChoice(BaseModel):
    index: int
    message: CerebrasMessage
    finish_reason: Optional[Literal["stop", "length"]] = None


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


class CerebrasStreamDelta(BaseModel):
    role: Optional[str] = None
    content: Optional[str] = None


class CerebrasStreamChoice(BaseModel):
    index: int
    delta: CerebrasStreamDelta
    finish_reason: Optional[Literal["stop", "length"]] = None


class CerebrasStreamChunk(BaseModel):
    id: str
    object: Literal["chat.completion.chunk"] = "chat.completion.chunk"
    created: int
    model: str
    choices: List[CerebrasStreamChoice]
    usage: Optional[CerebrasUsage] = None
