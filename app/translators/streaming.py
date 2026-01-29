import asyncio
import json
import time
import uuid
from typing import AsyncIterator, Optional, Dict, List
from app.models.cerebras import CerebrasStreamChunk
from app.config import get_settings
from app.utils.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)


# Track tool calls being built during streaming
class ToolCallAccumulator:
    """Accumulates tool call fragments during streaming."""
    
    def __init__(self):
        self.tool_calls: Dict[int, dict] = {}  # index -> {id, name, arguments}
    
    def add_fragment(self, index: int, tool_id: Optional[str], tool_type: Optional[str], function: Optional[dict]):
        """Add a tool call fragment."""
        if index not in self.tool_calls:
            self.tool_calls[index] = {"id": "", "name": "", "arguments": ""}
        
        if tool_id:
            self.tool_calls[index]["id"] = tool_id
        if function:
            if function.get("name"):
                self.tool_calls[index]["name"] = function["name"]
            if function.get("arguments"):
                self.tool_calls[index]["arguments"] += function["arguments"]
    
    def get_complete_tool_calls(self) -> List[dict]:
        """Get all accumulated tool calls."""
        return [
            {"id": tc["id"], "name": tc["name"], "arguments": tc["arguments"]}
            for tc in self.tool_calls.values()
            if tc["id"] and tc["name"]
        ]


def create_message_start_event(message_id: str, model: str, input_tokens: int = 0) -> str:
    """
    Create the message_start SSE event.
    
    NOTE: input_tokens is initially 0 and will be accurate only if Cerebras 
    provides usage data in stream chunks. This is a known limitation of streaming APIs.
    """
    event = {
        "type": "message_start",
        "message": {
            "id": message_id,
            "type": "message",
            "role": "assistant",
            "content": [],
            "model": model,
            "stop_reason": None,
            "stop_sequence": None,
            "usage": {"input_tokens": input_tokens, "output_tokens": 0}
        }
    }
    return f"event: message_start\ndata: {json.dumps(event)}\n\n"


def create_content_block_start_event(index: int = 0) -> str:
    """Create the content_block_start SSE event."""
    event = {
        "type": "content_block_start",
        "index": index,
        "content_block": {"type": "text", "text": ""}
    }
    return f"event: content_block_start\ndata: {json.dumps(event)}\n\n"


def create_content_block_delta_event(text: str, index: int = 0) -> str:
    """Create a content_block_delta SSE event."""
    event = {
        "type": "content_block_delta",
        "index": index,
        "delta": {"type": "text_delta", "text": text}
    }
    return f"event: content_block_delta\ndata: {json.dumps(event)}\n\n"


def create_content_block_stop_event(index: int = 0) -> str:
    """Create the content_block_stop SSE event."""
    event = {
        "type": "content_block_stop",
        "index": index
    }
    return f"event: content_block_stop\ndata: {json.dumps(event)}\n\n"


def create_message_delta_event(
    stop_reason: Optional[str] = "end_turn",
    output_tokens: int = 0
) -> str:
    """Create the message_delta SSE event."""
    event = {
        "type": "message_delta",
        "delta": {"stop_reason": stop_reason, "stop_sequence": None},
        "usage": {"output_tokens": output_tokens}
    }
    return f"event: message_delta\ndata: {json.dumps(event)}\n\n"


def create_message_stop_event() -> str:
    """Create the message_stop SSE event."""
    event = {"type": "message_stop"}
    return f"event: message_stop\ndata: {json.dumps(event)}\n\n"


def create_ping_event() -> str:
    """Create a ping SSE event for heartbeat."""
    event = {"type": "ping"}
    return f"event: ping\ndata: {json.dumps(event)}\n\n"


def create_tool_use_content_block_start_event(index: int, tool_id: str, name: str) -> str:
    """Create content_block_start for tool_use."""
    event = {
        "type": "content_block_start",
        "index": index,
        "content_block": {
            "type": "tool_use",
            "id": tool_id,
            "name": name,
            "input": {}
        }
    }
    return f"event: content_block_start\ndata: {json.dumps(event)}\n\n"


def create_tool_use_input_delta_event(index: int, partial_json: str) -> str:
    """Create content_block_delta for tool_use input."""
    event = {
        "type": "content_block_delta",
        "index": index,
        "delta": {
            "type": "input_json_delta",
            "partial_json": partial_json
        }
    }
    return f"event: content_block_delta\ndata: {json.dumps(event)}\n\n"


def translate_cerebras_finish_reason(reason: Optional[str]) -> Optional[str]:
    """Translate Cerebras finish reason to Anthropic format."""
    if not reason:
        return None
    mapping = {
        "stop": "end_turn",
        "length": "max_tokens",
        "tool_calls": "tool_use",
    }
    return mapping.get(reason, "end_turn")


async def translate_stream(
    cerebras_stream: AsyncIterator[CerebrasStreamChunk],
    original_model: str
) -> AsyncIterator[str]:
    """
    Translate Cerebras streaming response to Anthropic SSE format.
    
    SSE Event Order (CRITICAL):
    1. message_start
    2. content_block_start (for text, index=0)
    3. content_block_delta (repeated for text)
    4. content_block_stop (for text)
    5. [If tool calls] content_block_start/delta/stop for each tool (index=1,2,...)
    6. message_delta
    7. message_stop
    
    Heartbeat: ping event every 15 seconds (even if upstream is silent)
    """
    message_id = f"msg_{uuid.uuid4().hex[:24]}"
    
    # Track tokens and state
    input_tokens = 0
    total_output_tokens = 0
    stop_reason = "end_turn"
    last_ping_time = time.time()
    first_chunk = True
    has_text_content = False
    text_block_started = False
    
    # Track tool calls being accumulated
    tool_accumulator = ToolCallAccumulator()
    tool_blocks_started: Dict[int, bool] = {}  # Track which tool blocks we've started
    current_content_index = 0  # Track content block index
    
    try:
        async for chunk in cerebras_stream:
            # Extract usage from first chunk for input_tokens
            if first_chunk:
                if chunk.usage and hasattr(chunk.usage, 'prompt_tokens'):
                    input_tokens = chunk.usage.prompt_tokens
                
                # 1. message_start (CRITICAL: echo back original_model)
                yield create_message_start_event(message_id, original_model, input_tokens)
                first_chunk = False
            
            # Heartbeat ping every 15 seconds
            current_time = time.time()
            if current_time - last_ping_time >= settings.heartbeat_interval_seconds:
                yield create_ping_event()
                last_ping_time = current_time
            
            if chunk.choices:
                choice = chunk.choices[0]
                
                # Handle text content
                if choice.delta and choice.delta.text:
                    if not text_block_started:
                        # 2. content_block_start for text
                        yield create_content_block_start_event(index=0)
                        text_block_started = True
                        current_content_index = 1  # Next block will be index 1
                    
                    has_text_content = True
                    yield create_content_block_delta_event(choice.delta.text, index=0)
                
                # Handle tool calls in streaming
                if choice.delta and choice.delta.tool_calls:
                    # Close text block if it was open and we're starting tools
                    if text_block_started and has_text_content:
                        yield create_content_block_stop_event(index=0)
                        text_block_started = False  # Mark as closed
                    elif not text_block_started and not has_text_content:
                        # No text content at all, start with tool calls
                        current_content_index = 0
                    
                    for tool_call_delta in choice.delta.tool_calls:
                        tc_index = tool_call_delta.index
                        
                        # Accumulate the fragment
                        tool_accumulator.add_fragment(
                            tc_index,
                            tool_call_delta.id,
                            tool_call_delta.type,
                            tool_call_delta.function
                        )
                        
                        # Start the tool block if this is the first fragment with id and name
                        if tc_index not in tool_blocks_started:
                            tc = tool_accumulator.tool_calls.get(tc_index, {})
                            if tc.get("id") and tc.get("name"):
                                content_idx = current_content_index + tc_index
                                yield create_tool_use_content_block_start_event(
                                    content_idx,
                                    tc["id"],
                                    tc["name"]
                                )
                                tool_blocks_started[tc_index] = True
                        
                        # Stream the arguments as they come
                        if tool_call_delta.function and tool_call_delta.function.get("arguments"):
                            content_idx = current_content_index + tc_index
                            yield create_tool_use_input_delta_event(
                                content_idx,
                                tool_call_delta.function["arguments"]
                            )
                
                if choice.finish_reason:
                    stop_reason = translate_cerebras_finish_reason(choice.finish_reason)
            
            if chunk.usage:
                if hasattr(chunk.usage, 'completion_tokens'):
                    total_output_tokens = chunk.usage.completion_tokens
                if hasattr(chunk.usage, 'prompt_tokens') and not input_tokens:
                    input_tokens = chunk.usage.prompt_tokens
                    
    except asyncio.TimeoutError:
        logger.warning("Stream timeout, completing response")
    
    # Handle case where no chunks were received
    if first_chunk:
        yield create_message_start_event(message_id, original_model, input_tokens)
        yield create_content_block_start_event(index=0)
        text_block_started = True
    
    # Final ping if needed
    current_time = time.time()
    if current_time - last_ping_time >= settings.heartbeat_interval_seconds:
        yield create_ping_event()
    
    # Close text block if still open
    if text_block_started:
        yield create_content_block_stop_event(index=0)
    
    # Close any tool blocks that were started
    for tc_index in sorted(tool_blocks_started.keys()):
        content_idx = (1 if has_text_content else 0) + tc_index
        yield create_content_block_stop_event(index=content_idx)
    
    # 6. message_delta
    yield create_message_delta_event(stop_reason=stop_reason, output_tokens=total_output_tokens)
    
    # 7. message_stop
    yield create_message_stop_event()
