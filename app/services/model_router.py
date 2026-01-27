from typing import List
from app.models.anthropic import Message
from app.translators.prompt_tuning import detect_task_type
from app.config import get_settings
from app.utils.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)

# Model capabilities and costs
CEREBRAS_MODELS = {
    "llama-3.3-70b": {
        "capabilities": ["code", "analysis", "creative", "general"],
        "max_context": 8192,
        "cost_tier": "high",
        "quality_tier": "high"
    },
    "llama-3.1-8b": {
        "capabilities": ["general", "simple_code"],
        "max_context": 8192,
        "cost_tier": "low",
        "quality_tier": "medium"
    }
}

# Task type to optimal model mapping
TASK_MODEL_MAPPING = {
    "code": "llama-3.3-70b",
    "analysis": "llama-3.3-70b",
    "creative": "llama-3.3-70b",
    "general": "llama-3.3-70b",  # Default to larger model
}


def estimate_complexity(messages: List[Message]) -> str:
    """Estimate task complexity from messages."""
    total_length = 0
    
    for msg in messages:
        if isinstance(msg.content, str):
            total_length += len(msg.content)
        else:
            for block in msg.content:
                if hasattr(block, 'text'):
                    total_length += len(block.text)
    
    # Simple heuristic based on message length
    if total_length > 5000:
        return "high"
    elif total_length > 1000:
        return "medium"
    else:
        return "low"


def get_optimal_model(
    messages: List[Message],
    requested_model: str = None
) -> str:
    """
    Get optimal Cerebras model based on task type and complexity.
    
    Returns the internal Cerebras model name to use.
    Note: The original requested model should still be echoed back in responses.
    """
    task_type = detect_task_type(messages)
    complexity = estimate_complexity(messages)
    
    # Default model from config
    default_model = settings.cerebras_model
    
    # Get suggested model based on task
    suggested_model = TASK_MODEL_MAPPING.get(task_type, default_model)
    
    # For low complexity tasks, consider using smaller model
    if complexity == "low" and task_type == "general":
        suggested_model = "llama-3.1-8b"
    
    logger.debug(
        "Model routing decision",
        task_type=task_type,
        complexity=complexity,
        suggested_model=suggested_model
    )
    
    return suggested_model


def get_available_models() -> List[str]:
    """Get list of available Cerebras models."""
    return list(CEREBRAS_MODELS.keys())


def get_model_info(model: str) -> dict:
    """Get information about a specific model."""
    return CEREBRAS_MODELS.get(model, {})
