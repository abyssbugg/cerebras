from typing import List, Optional
from app.models.anthropic import Message, TextContent
from app.config import get_settings

settings = get_settings()

BEHAVIORAL_PREFIX = """You are a highly capable AI assistant focused on providing accurate, helpful, and thoughtful responses. Key guidelines:

1. Be direct and concise while remaining thorough
2. Acknowledge uncertainty when appropriate
3. For code tasks: provide working, well-documented solutions
4. Follow best practices and security guidelines
5. Break down complex problems into manageable steps
6. Ask clarifying questions when requirements are ambiguous"""


CODE_TASK_INDICATORS = [
    "code", "function", "class", "implement", "bug", "error", "debug",
    "python", "javascript", "typescript", "java", "c++", "rust", "go",
    "sql", "html", "css", "react", "vue", "angular", "node", "django",
    "flask", "fastapi", "api", "endpoint", "database", "query",
    "algorithm", "data structure", "refactor", "optimize", "test",
    "```", "def ", "function ", "class ", "const ", "let ", "var ",
    "import ", "from ", "require(", "export ", "async ", "await ",
]


def detect_task_type(messages: List[Message]) -> str:
    """
    Detect the type of task from messages.
    Returns: 'code', 'analysis', 'creative', or 'general'
    """
    text_content = ""
    
    for msg in messages:
        if isinstance(msg.content, str):
            text_content += msg.content.lower() + " "
        else:
            for block in msg.content:
                if isinstance(block, TextContent) or (isinstance(block, dict) and block.get("type") == "text"):
                    text = block.text if isinstance(block, TextContent) else block.get("text", "")
                    text_content += text.lower() + " "
    
    # Check for code indicators
    code_score = sum(1 for indicator in CODE_TASK_INDICATORS if indicator.lower() in text_content)
    
    if code_score >= 2:
        return "code"
    
    # Check for analysis indicators
    analysis_indicators = ["analyze", "explain", "compare", "evaluate", "review", "summarize"]
    if any(ind in text_content for ind in analysis_indicators):
        return "analysis"
    
    # Check for creative indicators
    creative_indicators = ["write", "story", "poem", "creative", "imagine", "describe"]
    if any(ind in text_content for ind in creative_indicators):
        return "creative"
    
    return "general"


def get_behavioral_prefix(messages: List[Message]) -> str:
    """
    Get behavioral prefix for system prompt.
    CRITICAL: This is PREFIXED to user's system prompt, never overwrites.
    """
    task_type = detect_task_type(messages)
    
    base_prefix = BEHAVIORAL_PREFIX
    
    if task_type == "code":
        base_prefix += """

For this code-related task:
- Write clean, maintainable, and well-documented code
- Follow language-specific best practices and conventions
- Consider edge cases and error handling
- Explain your approach when helpful"""
    
    elif task_type == "analysis":
        base_prefix += """

For this analysis task:
- Provide balanced and objective analysis
- Support conclusions with evidence
- Consider multiple perspectives
- Organize information clearly"""
    
    return base_prefix


def adjust_temperature(
    temperature: Optional[float],
    messages: List[Message]
) -> Optional[float]:
    """
    Adjust temperature based on task type.
    CRITICAL: For code tasks, multiply by 0.85 for more consistent output.
    """
    if temperature is None:
        return None
    
    task_type = detect_task_type(messages)
    
    if task_type == "code":
        adjusted = temperature * settings.temperature_multiplier_code
        return min(adjusted, 1.0)
    
    return temperature
