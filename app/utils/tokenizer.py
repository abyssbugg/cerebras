import tiktoken
from functools import lru_cache

ENCODING_NAME = "cl100k_base"


@lru_cache(maxsize=1)
def get_encoding():
    """Get the tiktoken encoding (cached)."""
    return tiktoken.get_encoding(ENCODING_NAME)


def count_tokens(text: str) -> int:
    """
    Count tokens in text using tiktoken cl100k_base encoding.
    This is a best-effort estimation for Cerebras models.
    """
    if not text:
        return 0
    
    encoding = get_encoding()
    return len(encoding.encode(text))


def truncate_to_token_limit(text: str, max_tokens: int) -> str:
    """Truncate text to fit within token limit."""
    if not text:
        return text
    
    encoding = get_encoding()
    tokens = encoding.encode(text)
    
    if len(tokens) <= max_tokens:
        return text
    
    truncated_tokens = tokens[:max_tokens]
    return encoding.decode(truncated_tokens)
