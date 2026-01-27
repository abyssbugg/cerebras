"""Unit tests for request/response translation."""
import pytest
from app.models.anthropic import (
    AnthropicMessagesRequest,
    AnthropicMessagesResponse,
    Message,
    TextContent,
    ResponseContentBlock,
    Usage,
)
from app.models.cerebras import (
    CerebrasChatRequest,
    CerebrasChatResponse,
    CerebrasMessage,
    CerebrasChoice,
    CerebrasUsage,
)
from app.translators.request import (
    translate_request,
    get_cerebras_model,
    extract_text_from_content,
)
from app.translators.response import translate_response, translate_finish_reason
from app.translators.prompt_tuning import (
    detect_task_type,
    get_behavioral_prefix,
    adjust_temperature,
)


class TestRequestTranslation:
    """Tests for Anthropic -> Cerebras request translation."""
    
    def test_basic_request_translation(self):
        """Test basic request translation."""
        request = AnthropicMessagesRequest(
            model="claude-sonnet-4-20250514",
            max_tokens=100,
            messages=[
                Message(role="user", content="Hello")
            ]
        )
        
        cerebras_req = translate_request(request)
        
        assert cerebras_req.model == "llama-3.3-70b"
        assert cerebras_req.max_tokens == 100
        assert len(cerebras_req.messages) == 1
        assert cerebras_req.messages[0].role == "user"
        assert cerebras_req.messages[0].content == "Hello"
    
    def test_system_prompt_prefixing(self):
        """Test that behavioral prefix is PREFIXED, not replacing system prompt."""
        request = AnthropicMessagesRequest(
            model="claude-sonnet-4",
            max_tokens=100,
            messages=[Message(role="user", content="Hi")],
            system="You are a helpful assistant."
        )
        
        behavioral_prefix = "Be concise."
        cerebras_req = translate_request(request, behavioral_prefix)
        
        # Find system message
        system_msg = None
        for msg in cerebras_req.messages:
            if msg.role == "system":
                system_msg = msg
                break
        
        assert system_msg is not None
        # Behavioral prefix should come BEFORE user's system prompt
        assert system_msg.content.startswith("Be concise.")
        assert "You are a helpful assistant." in system_msg.content
    
    def test_model_mapping(self):
        """Test model name mapping."""
        assert get_cerebras_model("claude-sonnet-4-20250514") == "llama-3.3-70b"
        assert get_cerebras_model("claude-3-5-haiku-20241022") == "llama-3.1-8b"
        assert get_cerebras_model("unknown-model") == "llama-3.3-70b"  # Default
    
    def test_content_extraction_string(self):
        """Test text extraction from string content."""
        result = extract_text_from_content("Hello world")
        assert result == "Hello world"
    
    def test_content_extraction_list(self):
        """Test text extraction from list content."""
        content = [
            TextContent(type="text", text="Part 1"),
            TextContent(type="text", text="Part 2"),
        ]
        result = extract_text_from_content(content)
        assert "Part 1" in result
        assert "Part 2" in result
    
    def test_stop_sequences(self):
        """Test stop sequence translation."""
        request = AnthropicMessagesRequest(
            model="claude-sonnet-4",
            max_tokens=100,
            messages=[Message(role="user", content="Hi")],
            stop_sequences=["STOP", "END"]
        )
        
        cerebras_req = translate_request(request)
        assert cerebras_req.stop == ["STOP", "END"]
    
    def test_temperature_preserved(self):
        """Test temperature is preserved."""
        request = AnthropicMessagesRequest(
            model="claude-sonnet-4",
            max_tokens=100,
            messages=[Message(role="user", content="Hi")],
            temperature=0.7
        )
        
        cerebras_req = translate_request(request)
        assert cerebras_req.temperature == 0.7


class TestResponseTranslation:
    """Tests for Cerebras -> Anthropic response translation."""
    
    def test_basic_response_translation(self):
        """Test basic response translation."""
        cerebras_resp = CerebrasChatResponse(
            id="test-id",
            object="chat.completion",
            created=1234567890,
            model="llama-3.3-70b",
            choices=[
                CerebrasChoice(
                    index=0,
                    message=CerebrasMessage(role="assistant", content="Hello!"),
                    finish_reason="stop"
                )
            ],
            usage=CerebrasUsage(
                prompt_tokens=10,
                completion_tokens=5,
                total_tokens=15
            )
        )
        
        original_model = "claude-sonnet-4-20250514"
        response = translate_response(cerebras_resp, original_model)
        
        assert response.type == "message"
        assert response.role == "assistant"
        assert response.model == original_model  # CRITICAL: Echo-back
        assert len(response.content) == 1
        assert response.content[0].text == "Hello!"
        assert response.usage.input_tokens == 10
        assert response.usage.output_tokens == 5
    
    def test_model_echo_back(self):
        """Test that requested model is echoed back, not internal model."""
        cerebras_resp = CerebrasChatResponse(
            id="test-id",
            object="chat.completion",
            created=1234567890,
            model="llama-3.3-70b",
            choices=[
                CerebrasChoice(
                    index=0,
                    message=CerebrasMessage(role="assistant", content="Hi"),
                    finish_reason="stop"
                )
            ],
            usage=CerebrasUsage(prompt_tokens=5, completion_tokens=2, total_tokens=7)
        )
        
        # User requested claude-sonnet-4
        response = translate_response(cerebras_resp, "claude-sonnet-4")
        
        # Response must have claude-sonnet-4, NOT llama-3.3-70b
        assert response.model == "claude-sonnet-4"
        assert response.model != "llama-3.3-70b"
    
    def test_finish_reason_mapping(self):
        """Test finish reason translation."""
        assert translate_finish_reason("stop") == "end_turn"
        assert translate_finish_reason("length") == "max_tokens"
        assert translate_finish_reason(None) is None


class TestPromptTuning:
    """Tests for prompt tuning functionality."""
    
    def test_code_task_detection(self):
        """Test code task detection."""
        messages = [
            Message(role="user", content="Write a Python function to sort a list")
        ]
        assert detect_task_type(messages) == "code"
    
    def test_general_task_detection(self):
        """Test general task detection."""
        messages = [
            Message(role="user", content="What is the capital of France?")
        ]
        assert detect_task_type(messages) == "general"
    
    def test_temperature_adjustment_for_code(self):
        """Test temperature is adjusted for code tasks."""
        messages = [
            Message(role="user", content="Write a Python function")
        ]
        
        original_temp = 1.0
        adjusted = adjust_temperature(original_temp, messages)
        
        # Temperature should be multiplied by 0.85 for code tasks
        assert adjusted == 0.85
    
    def test_temperature_no_adjustment_for_general(self):
        """Test temperature is not adjusted for general tasks."""
        messages = [
            Message(role="user", content="Hello, how are you?")
        ]
        
        original_temp = 0.7
        adjusted = adjust_temperature(original_temp, messages)
        
        assert adjusted == 0.7
    
    def test_behavioral_prefix_not_empty(self):
        """Test behavioral prefix is generated."""
        messages = [
            Message(role="user", content="Hello")
        ]
        
        prefix = get_behavioral_prefix(messages)
        assert prefix
        assert len(prefix) > 0


class TestValidation:
    """Tests for schema validation."""
    
    def test_valid_response_passes_validation(self):
        """Test valid response passes validation."""
        from app.utils.schema_validator import validate_response
        
        response = {
            "id": "msg_test123",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": "Hello"}],
            "model": "claude-sonnet-4",
            "stop_reason": "end_turn",
            "stop_sequence": None,
            "usage": {"input_tokens": 10, "output_tokens": 5}
        }
        
        assert validate_response(response) is True
    
    def test_missing_field_fails_validation(self):
        """Test missing field fails validation."""
        from app.utils.schema_validator import validate_response, SchemaValidationError
        
        response = {
            "id": "msg_test123",
            "type": "message",
            "role": "assistant",
            # Missing 'content'
            "model": "claude-sonnet-4",
            "usage": {"input_tokens": 10, "output_tokens": 5}
        }
        
        with pytest.raises(SchemaValidationError):
            validate_response(response)
