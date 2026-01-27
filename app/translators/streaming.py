import asyncio
import json
import time
import uuid
from typing import AsyncIterator, Optional
from app.models.cerebras import CerebrasStreamChunk
from app.config import get_settings
from app.utils.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)


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


def translate_cerebras_finish_reason(reason: Optional[str]) -> Optional[str]:
    """Translate Cerebras finish reason to Anthropic format."""
    if not reason:
        return None
    mapping = {
        "stop": "end_turn",
        "length": "max_tokens",
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
    2. content_block_start
    3. content_block_delta (repeated)
    4. content_block_stop
    5. message_delta
    6. message_stop
    
    Heartbeat: ping event every 15 seconds (even if upstream is silent)
    """
    message_id = f"msg_{uuid.uuid4().hex[:24]}"
    
    # Track tokens and state
    input_tokens = 0
    total_output_tokens = 0
    stop_reason = "end_turn"
    last_ping_time = time.time()
    first_chunk = True
    
    # 3. content_block_delta (repeated) with heartbeat monitoring
    # Extract input_tokens from first chunk if available
    try:
        async for chunk in cerebras_stream:
            # Extract usage from first chunk for input_tokens
            if first_chunk:
                if chunk.usage and hasattr(chunk.usage, 'prompt_tokens'):
                    input_tokens = chunk.usage.prompt_tokens
                
                # 1. message_start (CRITICAL: echo back original_model)
                yield create_message_start_event(message_id, original_model, input_tokens)
                
                # 2. content_block_start
                yield create_content_block_start_event(index=0)
                
                first_chunk = False
            
            # Heartbeat ping every 15 seconds
            current_time = time.time()
            if current_time - last_ping_time >= settings.heartbeat_interval_seconds:
                yield create_ping_event()
                last_ping_time = current_time
            
            if chunk.choices:
                choice = chunk.choices[0]
                
                if choice.delta and choice.delta.content:
                    yield create_content_block_delta_event(choice.delta.content, index=0)
                
                if choice.finish_reason:
                    stop_reason = translate_cerebras_finish_reason(choice.finish_reason)
            
            if chunk.usage:
                if hasattr(chunk.usage, 'completion_tokens'):
                    total_output_tokens = chunk.usage.completion_tokens
                if hasattr(chunk.usage, 'prompt_tokens') and not input_tokens:
                    input_tokens = chunk.usage.prompt_tokens
    except asyncio.TimeoutError:
        # Stream timed out, send final events
        logger.warning("Stream timeout, completing response")
    
    # Handle case where no chunks were received
    if first_chunk:
        # Still send message_start and content_block_start
        yield create_message_start_event(message_id, original_model, input_tokens)
        yield create_content_block_start_event(index=0)
    
    # Final ping if time since last ping is close to interval
    current_time = time.time()
    if current_time - last_ping_time >= settings.heartbeat_interval_seconds:
        yield create_ping_event()
    
    # 4. content_block_stop
    yield create_content_block_stop_event(index=0)
    
    # 5. message_delta
    yield create_message_delta_event(stop_reason=stop_reason, output_tokens=total_output_tokens)
    
    # 6. message_stop
    yield create_message_stop_event()
