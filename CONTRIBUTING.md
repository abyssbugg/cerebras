# Contributing to Cerebras Anthropic Gateway

Thank you for your interest in contributing! This document provides guidelines for contributing to this project.

## Development Setup

### Prerequisites

- Python 3.11 or 3.12
- Redis (optional, for caching and rate limiting)
- Docker (optional, for containerized development)

### Local Setup

```bash
# Clone the repository
git clone https://github.com/abyssbugg/cerebras.git
cd cerebras

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env
# Edit .env with your configuration

# Run the server
uvicorn app.main:app --reload --port 8080
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/unit/test_translation.py -v

# Run integration tests
pytest tests/integration/ -v
```

## Code Style

### Python Guidelines

- Follow PEP 8 style guidelines
- Use type hints for function parameters and return values
- Keep functions focused and under 50 lines when possible
- Add docstrings for classes and public functions

### File Organization

```
app/
├── api/           # HTTP routes and middleware
├── clients/       # External API clients
├── models/        # Pydantic data models
├── services/      # Business logic services
├── translators/   # Request/response translation
└── utils/         # Shared utilities
```

## Making Changes

### Branch Naming

- `feature/description` - New features
- `fix/description` - Bug fixes
- `docs/description` - Documentation updates
- `refactor/description` - Code refactoring

### Commit Messages

Write clear, concise commit messages:

```
Add configurable CORS origins setting

- Add cors_origins setting to config.py
- Update main.py to use configurable origins
- Document setting in .env.example
```

### Pull Request Process

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add or update tests as needed
5. Run tests to ensure they pass
6. Update documentation if needed
7. Submit a pull request

### PR Description Template

```markdown
## Summary
Brief description of changes

## Changes
- Change 1
- Change 2

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests pass
- [ ] Manual testing completed

## Documentation
- [ ] README updated (if needed)
- [ ] .env.example updated (if needed)
```

## Critical Guidelines

### Model Echo-Back

**CRITICAL**: Always return the user's requested model name in responses, not the internal Cerebras model name.

```python
# Correct - echo back original_model
response.model = original_model  # e.g., "claude-sonnet-4"

# Wrong - don't expose internal model
response.model = cerebras_model  # e.g., "zai-glm-4.7"
```

### System Prompt Prefixing

**CRITICAL**: Behavioral prefixes are PREFIXED to user's system prompt, never replacing it.

```python
# Correct - prefix
combined = f"{behavioral_prefix}\n\n{user_system_prompt}"

# Wrong - replace
combined = behavioral_prefix  # Lost user's system prompt!
```

### SSE Event Order

**CRITICAL**: Streaming events must follow this exact order:

1. `message_start`
2. `content_block_start`
3. `content_block_delta` (repeated)
4. `content_block_stop`
5. `message_delta`
6. `message_stop`

### Response Validation

**CRITICAL**: All responses must be validated against Anthropic schemas before returning.

## Questions?

Open an issue if you have questions or need clarification on anything.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
