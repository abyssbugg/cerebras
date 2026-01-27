"""Unit tests for SSE streaming functionality."""
import json
from app.translators.streaming import (
    create_message_start_event,
    create_content_block_start_event,
    create_content_block_delta_event,
    create_content_block_stop_event,
    create_message_delta_event,
    create_message_stop_event,
    create_ping_event,
    translate_cerebras_finish_reason,
)
from app.utils.schema_validator import validate_streaming_event


class TestSSEEventCreation:
    """Tests for SSE event creation functions."""
    
    def test_message_start_event_structure(self):
        """Test message_start event has correct structure."""
        event = create_message_start_event("msg_123", "claude-sonnet-4")
        
        # Parse SSE format
        lines = event.strip().split("\n")
        assert lines[0] == "event: message_start"
        assert lines[1].startswith("data: ")
        
        data = json.loads(lines[1][6:])
        assert data["type"] == "message_start"
        assert "message" in data
        assert data["message"]["id"] == "msg_123"
        assert data["message"]["model"] == "claude-sonnet-4"
        assert data["message"]["role"] == "assistant"
        assert data["message"]["content"] == []
    
    def test_content_block_start_event(self):
        """Test content_block_start event."""
        event = create_content_block_start_event(index=0)
        
        lines = event.strip().split("\n")
        assert lines[0] == "event: content_block_start"
        
        data = json.loads(lines[1][6:])
        assert data["type"] == "content_block_start"
        assert data["index"] == 0
        assert data["content_block"]["type"] == "text"
    
    def test_content_block_delta_event(self):
        """Test content_block_delta event."""
        event = create_content_block_delta_event("Hello", index=0)
        
        lines = event.strip().split("\n")
        assert lines[0] == "event: content_block_delta"
        
        data = json.loads(lines[1][6:])
        assert data["type"] == "content_block_delta"
        assert data["index"] == 0
        assert data["delta"]["type"] == "text_delta"
        assert data["delta"]["text"] == "Hello"
    
    def test_content_block_stop_event(self):
        """Test content_block_stop event."""
        event = create_content_block_stop_event(index=0)
        
        lines = event.strip().split("\n")
        assert lines[0] == "event: content_block_stop"
        
        data = json.loads(lines[1][6:])
        assert data["type"] == "content_block_stop"
        assert data["index"] == 0
    
    def test_message_delta_event(self):
        """Test message_delta event."""
        event = create_message_delta_event(stop_reason="end_turn", output_tokens=42)
        
        lines = event.strip().split("\n")
        assert lines[0] == "event: message_delta"
        
        data = json.loads(lines[1][6:])
        assert data["type"] == "message_delta"
        assert data["delta"]["stop_reason"] == "end_turn"
        assert data["usage"]["output_tokens"] == 42
    
    def test_message_stop_event(self):
        """Test message_stop event."""
        event = create_message_stop_event()
        
        lines = event.strip().split("\n")
        assert lines[0] == "event: message_stop"
        
        data = json.loads(lines[1][6:])
        assert data["type"] == "message_stop"
    
    def test_ping_event(self):
        """Test ping event for heartbeat."""
        event = create_ping_event()
        
        lines = event.strip().split("\n")
        assert lines[0] == "event: ping"
        
        data = json.loads(lines[1][6:])
        assert data["type"] == "ping"


class TestSSEEventOrder:
    """Tests for SSE event ordering."""
    
    def test_event_order_is_correct(self):
        """
        Test that events are created in correct order:
        message_start -> content_block_start -> content_block_delta(s) 
        -> content_block_stop -> message_delta -> message_stop
        """
        events = [
            create_message_start_event("msg_1", "claude-sonnet-4"),
            create_content_block_start_event(0),
            create_content_block_delta_event("Hello", 0),
            create_content_block_delta_event(" World", 0),
            create_content_block_stop_event(0),
            create_message_delta_event("end_turn", 10),
            create_message_stop_event(),
        ]
        
        event_types = []
        for event in events:
            lines = event.strip().split("\n")
            event_type = lines[0].replace("event: ", "")
            event_types.append(event_type)
        
        # Verify order
        assert event_types[0] == "message_start"
        assert event_types[1] == "content_block_start"
        assert event_types[2] == "content_block_delta"
        assert event_types[3] == "content_block_delta"
        assert event_types[4] == "content_block_stop"
        assert event_types[5] == "message_delta"
        assert event_types[6] == "message_stop"


class TestFinishReasonTranslation:
    """Tests for Cerebras -> Anthropic finish reason translation."""
    
    def test_stop_to_end_turn(self):
        """Test 'stop' -> 'end_turn'."""
        assert translate_cerebras_finish_reason("stop") == "end_turn"
    
    def test_length_to_max_tokens(self):
        """Test 'length' -> 'max_tokens'."""
        assert translate_cerebras_finish_reason("length") == "max_tokens"
    
    def test_none_stays_none(self):
        """Test None -> None."""
        assert translate_cerebras_finish_reason(None) is None
    
    def test_unknown_defaults_to_end_turn(self):
        """Test unknown reason defaults to 'end_turn'."""
        assert translate_cerebras_finish_reason("unknown") == "end_turn"


class TestSSEEventValidation:
    """Tests for SSE event schema validation."""
    
    def test_valid_message_start_passes(self):
        """Test valid message_start passes validation."""
        event = create_message_start_event("msg_test", "claude-sonnet-4")
        assert validate_streaming_event(event) is True
    
    def test_valid_content_block_delta_passes(self):
        """Test valid content_block_delta passes validation."""
        event = create_content_block_delta_event("test", 0)
        assert validate_streaming_event(event) is True
    
    def test_valid_ping_passes(self):
        """Test valid ping passes validation."""
        event = create_ping_event()
        assert validate_streaming_event(event) is True
    
    def test_all_events_pass_validation(self):
        """Test all generated events pass validation."""
        events = [
            create_message_start_event("msg_1", "claude-sonnet-4"),
            create_content_block_start_event(0),
            create_content_block_delta_event("test", 0),
            create_content_block_stop_event(0),
            create_message_delta_event("end_turn", 5),
            create_message_stop_event(),
            create_ping_event(),
        ]
        
        for event in events:
            assert validate_streaming_event(event) is True


class TestModelEchoBackInStreaming:
    """Tests for model echo-back in streaming events."""
    
    def test_message_start_echoes_model(self):
        """Test message_start contains correct model."""
        requested_model = "claude-sonnet-4-20250514"
        event = create_message_start_event("msg_1", requested_model)
        
        lines = event.strip().split("\n")
        data = json.loads(lines[1][6:])
        
        # Model in message_start must be the requested model
        assert data["message"]["model"] == requested_model
        assert data["message"]["model"] != "llama-3.3-70b"  # Not internal model
