import json
import re
from typing import Any, Optional
from pydantic import ValidationError
from app.models.anthropic import (
    AnthropicMessagesResponse,
    MessageStartEvent,
    ContentBlockStartEvent,
    ContentBlockDeltaEvent,
    ContentBlockStopEvent,
    MessageDeltaEvent,
    MessageStopEvent,
    PingEvent,
)
from app.utils.logging import get_logger

logger = get_logger(__name__)


class SchemaValidationError(Exception):
    """Raised when response doesn't match expected schema."""
    def __init__(self, message: str, details: Optional[dict] = None):
        self.message = message
        self.details = details or {}
        super().__init__(message)


def validate_response(response: dict) -> bool:
    """
    Validate non-streaming response against Anthropic schema.
    CRITICAL: Validate ALL responses before returning to prevent silent client failures.
    """
    try:
        # Required fields
        required_fields = ["id", "type", "role", "content", "model", "usage"]
        for field in required_fields:
            if field not in response:
                raise SchemaValidationError(
                    f"Missing required field: {field}",
                    {"missing_field": field}
                )
        
        # Type validation
        if response["type"] != "message":
            raise SchemaValidationError(
                f"Invalid type: expected 'message', got '{response['type']}'"
            )
        
        if response["role"] != "assistant":
            raise SchemaValidationError(
                f"Invalid role: expected 'assistant', got '{response['role']}'"
            )
        
        # Content validation
        if not isinstance(response["content"], list):
            raise SchemaValidationError("Content must be a list")
        
        for block in response["content"]:
            if "type" not in block:
                raise SchemaValidationError("Content block missing 'type' field")
            if block["type"] == "text" and "text" not in block:
                raise SchemaValidationError("Text content block missing 'text' field")
        
        # Usage validation
        usage = response.get("usage", {})
        if "input_tokens" not in usage or "output_tokens" not in usage:
            raise SchemaValidationError("Usage missing token counts")
        
        # Model presence validation
        # NOTE: This validates model field is present. Model echo-back 
        # (matching requested model name) is enforced in translate_response()
        if not response.get("model"):
            raise SchemaValidationError("Response missing model field")
        
        # Validate using Pydantic model
        AnthropicMessagesResponse(**response)
        
        return True
        
    except ValidationError as e:
        logger.error("Pydantic validation failed", errors=e.errors())
        raise SchemaValidationError(
            "Response validation failed",
            {"pydantic_errors": e.errors()}
        )
    except SchemaValidationError:
        raise
    except Exception as e:
        logger.error("Schema validation error", error=str(e))
        raise SchemaValidationError(f"Validation error: {str(e)}")


def validate_streaming_event(event_str: str) -> bool:
    """
    Validate individual SSE event against expected schema.
    CRITICAL: Validate each SSE event to ensure correct format.
    """
    try:
        # Parse SSE event
        lines = event_str.strip().split("\n")
        event_type = None
        data = None
        
        for line in lines:
            if line.startswith("event: "):
                event_type = line[7:]
            elif line.startswith("data: "):
                data = line[6:]
        
        if not event_type or not data:
            # Allow empty events
            return True
        
        # Parse JSON data
        event_data = json.loads(data)
        
        # Validate based on event type
        if event_type == "message_start":
            _validate_message_start(event_data)
        elif event_type == "content_block_start":
            _validate_content_block_start(event_data)
        elif event_type == "content_block_delta":
            _validate_content_block_delta(event_data)
        elif event_type == "content_block_stop":
            _validate_content_block_stop(event_data)
        elif event_type == "message_delta":
            _validate_message_delta(event_data)
        elif event_type == "message_stop":
            _validate_message_stop(event_data)
        elif event_type == "ping":
            _validate_ping(event_data)
        elif event_type == "error":
            # Error events are always valid
            pass
        else:
            logger.warning(f"Unknown event type: {event_type}")
        
        return True
        
    except json.JSONDecodeError as e:
        logger.error("Failed to parse SSE event JSON", error=str(e))
        raise SchemaValidationError(f"Invalid JSON in SSE event: {str(e)}")
    except SchemaValidationError:
        raise
    except Exception as e:
        logger.error("SSE event validation error", error=str(e))
        raise SchemaValidationError(f"SSE validation error: {str(e)}")


def _validate_message_start(data: dict) -> None:
    """Validate message_start event."""
    if data.get("type") != "message_start":
        raise SchemaValidationError("message_start event has wrong type")
    
    message = data.get("message")
    if not message:
        raise SchemaValidationError("message_start missing 'message' field")
    
    required = ["id", "type", "role", "content", "model"]
    for field in required:
        if field not in message:
            raise SchemaValidationError(f"message_start.message missing '{field}'")


def _validate_content_block_start(data: dict) -> None:
    """Validate content_block_start event."""
    if data.get("type") != "content_block_start":
        raise SchemaValidationError("content_block_start event has wrong type")
    
    if "index" not in data:
        raise SchemaValidationError("content_block_start missing 'index'")
    
    content_block = data.get("content_block")
    if not content_block:
        raise SchemaValidationError("content_block_start missing 'content_block'")
    
    if "type" not in content_block:
        raise SchemaValidationError("content_block missing 'type'")


def _validate_content_block_delta(data: dict) -> None:
    """Validate content_block_delta event."""
    if data.get("type") != "content_block_delta":
        raise SchemaValidationError("content_block_delta event has wrong type")
    
    if "index" not in data:
        raise SchemaValidationError("content_block_delta missing 'index'")
    
    delta = data.get("delta")
    if not delta:
        raise SchemaValidationError("content_block_delta missing 'delta'")
    
    if "type" not in delta:
        raise SchemaValidationError("content_block_delta.delta missing 'type'")


def _validate_content_block_stop(data: dict) -> None:
    """Validate content_block_stop event."""
    if data.get("type") != "content_block_stop":
        raise SchemaValidationError("content_block_stop event has wrong type")
    
    if "index" not in data:
        raise SchemaValidationError("content_block_stop missing 'index'")


def _validate_message_delta(data: dict) -> None:
    """Validate message_delta event."""
    if data.get("type") != "message_delta":
        raise SchemaValidationError("message_delta event has wrong type")
    
    if "delta" not in data:
        raise SchemaValidationError("message_delta missing 'delta'")
    
    if "usage" not in data:
        raise SchemaValidationError("message_delta missing 'usage'")


def _validate_message_stop(data: dict) -> None:
    """Validate message_stop event."""
    if data.get("type") != "message_stop":
        raise SchemaValidationError("message_stop event has wrong type")


def _validate_ping(data: dict) -> None:
    """Validate ping event."""
    if data.get("type") != "ping":
        raise SchemaValidationError("ping event has wrong type")
