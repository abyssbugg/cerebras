# Python Version Compatibility

## Supported Python Versions

**Required**: Python 3.11 or 3.12

## Python 3.14 Compatibility Issues

Several dependencies do not yet support Python 3.14:

1. **tiktoken** - Requires PyO3 which maxes out at Python 3.12
2. **pydantic-core** - Native extension with Python 3.12 max support
3. **sse-starlette** - May have compatibility issues

## Installation Instructions

### Option 1: Use pyenv (Recommended)

```bash
# Install pyenv if not already installed
curl https://pyenv.run | bash

# Install Python 3.12
pyenv install 3.12.0

# Set local Python version
pyenv local 3.12.0

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Option 2: Use system Python 3.12

```bash
# Verify Python version
python3 --version  # Should be 3.11.x or 3.12.x

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Option 3: Docker (Guaranteed compatibility)

```bash
# Use the provided Dockerfile which uses Python 3.11
docker-compose up
```

## Testing Python Version

```bash
python -c "import sys; print(f'Python {sys.version}')"
```

## Dependency Update Strategy

- **Quarterly Review**: Check for dependency updates every 3 months
- **Security Patches**: Apply immediately when CVEs are announced
- **Major Upgrades**: Test thoroughly in staging before production
- **Python 3.14**: Wait for all dependencies to support before upgrading

## Known Working Configurations

| Python Version | Status | Notes |
|---------------|--------|-------|
| 3.9 | ⚠️ Works | Missing some type hints, not recommended |
| 3.10 | ⚠️ Works | Missing some features, not recommended |
| 3.11 | ✅ Recommended | Fully tested and supported |
| 3.12 | ✅ Recommended | Fully tested and supported |
| 3.13 | ⚠️ Untested | May work, not officially supported |
| 3.14 | ❌ Broken | tiktoken and pydantic-core incompatible |

## Troubleshooting

### Error: "no module named tiktoken"

```bash
# Make sure you're using Python 3.11 or 3.12
python --version

# Reinstall in clean environment
rm -rf .venv
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Error: "Building wheel for pydantic-core failed"

This typically means Python 3.14 is being used. Switch to Python 3.12:

```bash
pyenv local 3.12.0
rm -rf .venv
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Error: "sse-starlette not found"

We've fixed the version to 2.1.0 (1.8.0 doesn't exist). If you still see issues:

```bash
pip install --upgrade pip
pip install sse-starlette==2.1.0
```

## Future Python Support

We will add Python 3.14 support when:
- tiktoken releases a compatible version
- pydantic-core releases a compatible version
- All tests pass with Python 3.14

Expected timeline: Q2 2025 (estimated)
