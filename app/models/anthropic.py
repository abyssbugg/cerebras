from typing import List, Optional, Union, Literal
from pydantic import BaseModel, Field
import uuid


class TextContent(BaseModel):
    type: Literal["text"] = "text"
    text: str


class ImageSource(BaseModel):
    type: Literal["base64", "url"] = "base64"
    media_type: str = "image/png"
    data: str = ""
    url: Optional[str] = None


class ImageContent(BaseModel):
    type: Literal["image"] = "image"
    source: ImageSource


class ToolUseContent(BaseModel):
    type: Literal["tool_use"] = "tool_use"
    id: str
    name: str
    input: dict


class ToolResultContent(BaseModel):
    type: Literal["tool_result"] = "tool_result"
    tool_use_id: str
    content: Union[str, List[Union[TextContent, ImageContent]]]
    is_error: bool = False


ContentBlock = Union[TextContent, ImageContent, ToolUseContent, ToolResultContent]


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: Union[str, List[ContentBlock]]


class Tool(BaseModel):
    name: str
    description: str
    input_schema: dict


class ToolChoice(BaseModel):
    type: Literal["auto", "any", "tool"] = "auto"
    name: Optional[str] = None


class Metadata(BaseModel):
    user_id: Optional[str] = None


class AnthropicMessagesRequest(BaseModel):
    model: str
    messages: List[Message]
    max_tokens: int
    system: Optional[Union[str, List[TextContent]]] = None
    metadata: Optional[Metadata] = None
    stop_sequences: Optional[List[str]] = None
    stream: bool = False
    temperature: Optional[float] = Field(default=1.0, ge=0.0, le=1.0)
    top_k: Optional[int] = None
    top_p: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    tools: Optional[List[Tool]] = None
    tool_choice: Optional[ToolChoice] = None


class Usage(BaseModel):
    input_tokens: int
    output_tokens: int


class ResponseContentBlock(BaseModel):
    type: Literal["text", "tool_use"] = "text"
    text: Optional[str] = None
    id: Optional[str] = None
    name: Optional[str] = None
    input: Optional[dict] = None


class AnthropicMessagesResponse(BaseModel):
    id: str = Field(default_factory=lambda: f"msg_{uuid.uuid4().hex[:24]}")
    type: Literal["message"] = "message"
    role: Literal["assistant"] = "assistant"
    content: List[ResponseContentBlock]
    model: str
    stop_reason: Optional[Literal["end_turn", "max_tokens", "stop_sequence", "tool_use"]] = None
    stop_sequence: Optional[str] = None
    usage: Usage


# Streaming Event Models
class MessageStartEvent(BaseModel):
    type: Literal["message_start"] = "message_start"
    message: dict


class ContentBlockStartEvent(BaseModel):
    type: Literal["content_block_start"] = "content_block_start"
    index: int
    content_block: dict


class ContentBlockDeltaEvent(BaseModel):
    type: Literal["content_block_delta"] = "content_block_delta"
    index: int
    delta: dict


class ContentBlockStopEvent(BaseModel):
    type: Literal["content_block_stop"] = "content_block_stop"
    index: int


class MessageDeltaEvent(BaseModel):
    type: Literal["message_delta"] = "message_delta"
    delta: dict
    usage: dict


class MessageStopEvent(BaseModel):
    type: Literal["message_stop"] = "message_stop"


class PingEvent(BaseModel):
    type: Literal["ping"] = "ping"


class AnthropicTokenCountRequest(BaseModel):
    model: str
    messages: List[Message]
    system: Optional[Union[str, List[TextContent]]] = None
    tools: Optional[List[Tool]] = None


class AnthropicTokenCountResponse(BaseModel):
    input_tokens: int
