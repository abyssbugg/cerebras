"""
Model Router for Cerebras Anthropic Gateway

This module handles model routing for the gateway.
For Cerebras Code Max plans, all requests use zai-glm-4.7.

To support other Cerebras plans with different models in the future,
update CEREBRAS_MODELS and the routing logic below.
"""

from typing import List
from app.models.anthropic import Message
from app.config import get_settings
from app.utils.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)

# Available Cerebras models
# Currently configured for Cerebras Code Max (zai-glm-4.7 only)
CEREBRAS_MODELS = {
    "zai-glm-4.7": {
        "capabilities": ["code", "analysis", "creative", "general"],
        "max_context": 128000,
        "cost_tier": "included",  # Part of Code Max subscription
        "quality_tier": "high"
    }
}


def get_optimal_model(
    messages: List[Message],
    requested_model: str = None
) -> str:
    """
    Get the Cerebras model to use for this request.
    
    For Cerebras Code Max plans, always returns zai-glm-4.7.
    The original requested model (e.g., claude-sonnet-4) is echoed
    back in the response, not this internal model name.
    
    Args:
        messages: The conversation messages
        requested_model: The model requested by the client (for logging)
    
    Returns:
        The internal Cerebras model name to use (zai-glm-4.7)
    """
    # Always use the configured model (zai-glm-4.7 for Code Max)
    model = settings.cerebras_model
    
    logger.debug(
        "Model routing",
        requested_model=requested_model,
        cerebras_model=model
    )
    
    return model


def get_available_models() -> List[str]:
    """Get list of available Cerebras models."""
    return list(CEREBRAS_MODELS.keys())


def get_model_info(model: str) -> dict:
    """Get information about a specific model."""
    return CEREBRAS_MODELS.get(model, {})
