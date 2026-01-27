import re
from app.models.anthropic import AnthropicMessagesResponse, ResponseContentBlock


LANGUAGE_EXTENSIONS = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".jsx": "jsx",
    ".tsx": "tsx",
    ".java": "java",
    ".cpp": "cpp",
    ".c": "c",
    ".h": "c",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".php": "php",
    ".swift": "swift",
    ".kt": "kotlin",
    ".scala": "scala",
    ".sql": "sql",
    ".html": "html",
    ".css": "css",
    ".scss": "scss",
    ".sass": "sass",
    ".less": "less",
    ".json": "json",
    ".xml": "xml",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".md": "markdown",
    ".sh": "bash",
    ".bash": "bash",
    ".zsh": "zsh",
    ".ps1": "powershell",
    ".dockerfile": "dockerfile",
    ".toml": "toml",
    ".ini": "ini",
    ".cfg": "ini",
    ".r": "r",
    ".lua": "lua",
    ".perl": "perl",
    ".pl": "perl",
}

LANGUAGE_KEYWORDS = {
    "python": ["def ", "import ", "from ", "class ", "if __name__", "async def"],
    "javascript": ["const ", "let ", "var ", "function ", "=>", "require(", "export "],
    "typescript": ["interface ", "type ", ": string", ": number", ": boolean"],
    "java": ["public class", "public static void", "System.out"],
    "cpp": ["#include", "std::", "int main("],
    "rust": ["fn main(", "let mut", "impl ", "pub fn"],
    "go": ["package main", "func main(", "import ("],
    "sql": ["SELECT ", "INSERT ", "UPDATE ", "DELETE ", "CREATE TABLE"],
    "html": ["<!DOCTYPE", "<html", "<div", "<span", "<body"],
    "css": ["{", "}", "color:", "background:", "margin:", "padding:"],
    "bash": ["#!/bin/bash", "echo ", "if [", "for ", "while "],
    "json": ['{"', '": "', '": {'],
    "yaml": ["---", ": ", "- "],
}


def detect_language(code: str) -> str:
    """Detect programming language from code content."""
    code_lower = code.lower()
    
    # Check for explicit language hints
    for lang, keywords in LANGUAGE_KEYWORDS.items():
        matches = sum(1 for kw in keywords if kw.lower() in code_lower)
        if matches >= 2:
            return lang
    
    # Default to empty (no language tag)
    return ""


def add_language_tags_to_code_blocks(text: str) -> str:
    """
    Add language tags to code blocks that don't have them.
    Conservative processing - only adds formatting, no content changes.
    """
    # Pattern for code blocks without language specification
    pattern = r"```\n([^`]+?)```"
    
    def replace_block(match):
        code = match.group(1)
        lang = detect_language(code)
        if lang:
            return f"```{lang}\n{code}```"
        return match.group(0)
    
    return re.sub(pattern, replace_block, text)


def enhance_response(response: AnthropicMessagesResponse) -> AnthropicMessagesResponse:
    """
    Enhance response formatting.
    Conservative processing - formatting only, no content changes.
    
    IMPORTANT: Creates a new response object with enhanced content to avoid
    mutating the original response (prevents side effects).
    """
    enhanced_content: list[ResponseContentBlock] = []
    
    for block in response.content:
        if block.type == "text" and block.text:
            enhanced_text = add_language_tags_to_code_blocks(block.text)
            enhanced_content.append(ResponseContentBlock(
                type="text",
                text=enhanced_text
            ))
        else:
            # Create a copy of the block to avoid reference issues
            enhanced_content.append(ResponseContentBlock(
                type=block.type,
                text=block.text,
                id=block.id,
                name=block.name,
                input=block.input
            ))
    
    # Return a new response object instead of mutating the original
    return AnthropicMessagesResponse(
        id=response.id,
        type=response.type,
        role=response.role,
        content=enhanced_content,
        model=response.model,
        stop_reason=response.stop_reason,
        stop_sequence=response.stop_sequence,
        usage=response.usage
    )
