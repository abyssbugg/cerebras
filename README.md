# Cerebras Gateway

[![CI](https://github.com/abyssbugg/cerebras/actions/workflows/ci.yml/badge.svg)](https://github.com/abyssbugg/cerebras/actions/workflows/ci.yml)

A production-ready API gateway that translates Anthropic Messages API requests to Cerebras inference API. Use Claude Code, Cursor, Droid, and other Anthropic SDK clients with Cerebras models.

## Requirements

- **Python 3.11 or 3.12**
- Redis (optional, for caching and rate limiting)
- Docker (optional, for containerized deployment)

## Quick Start

### 1. Set Environment Variables

```bash
export ANTHROPIC_BASE_URL=http://localhost:8080
export ANTHROPIC_API_KEY=your-gateway-key
```

### 2. Run with Docker

```bash
# Set your Cerebras API key
export CEREBRAS_API_KEY=your-cerebras-key

# Start the gateway
docker-compose up
```

### 3. Test with curl

```bash
curl -X POST http://localhost:8080/v1/messages \
  -H "x-api-key: test-key" \
  -H "anthropic-version: 2023-06-01" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-sonnet-4-20250514",
    "max_tokens": 100,
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

### 4. Run Smoke Tests

```bash
./scripts/smoke_test.sh http://localhost:8080 test-key
```

## Client Configuration

### Claude Code

Add to your `settings.json` or environment:

```json
{
    "ANTHROPIC_BASE_URL": "https://cerebras-bdkx.onrender.com/anthropic",
    "ANTHROPIC_AUTH_TOKEN": "csk-your-cerebras-api-key",
    "API_TIMEOUT_MS": "3000000",
    "ANTHROPIC_MODEL": "zai-glm-4.7"
}
```

### Droid CLI

Add to your Droid configuration:

```json
{
    "model": "zai-glm-4.7",
    "base_url": "https://cerebras-bdkx.onrender.com/anthropic",
    "api_key": "csk-your-cerebras-key",
    "provider": "anthropic"
}
```

## Troubleshooting

### Network Errors (502/500 HTML errors)

If you see HTML error pages from Cloudflare (e.g., "Error code 500/502"), this means:
- Your internet connection may be down
- The gateway service is temporarily unavailable
- Cloudflare is having issues

**Solutions:**
1. Check your internet connection
2. Wait a few seconds and retry
3. The gateway auto-recovers - just retry the request

**Note:** These network-level errors happen before reaching the gateway, so the error format is controlled by Cloudflare, not us. Droid/Claude Code should automatically retry on connection failures.

### Cursor IDE

In Cursor Settings > Models > Anthropic:

```
Base URL: https://cerebras-bdkx.onrender.com
API Key: csk-your-cerebras-api-key
```

### Generic Anthropic SDK

```python
import anthropic

client = anthropic.Anthropic(
    base_url="https://cerebras-bdkx.onrender.com",
    api_key="csk-your-cerebras-api-key"
)

response = client.messages.create(
    model="claude-sonnet-4-20250514",  # Any model name works
    max_tokens=1024,
    messages=[{"role": "user", "content": "Hello!"}]
)
```

### Self-Hosted

If running your own gateway:

```bash
# Replace with your deployment URL
export ANTHROPIC_BASE_URL=http://localhost:8080
export ANTHROPIC_API_KEY=your-gateway-key
```

## Features

- **Drop-in Replacement**: Zero code changes required for Claude Code, Cursor, and Anthropic SDK clients
- **Full API Compatibility**: Supports both streaming and non-streaming modes
- **Model Echo-back**: Always returns the requested model name in responses
- **Prompt Tuning**: Behavioral system prompts with temperature adjustment for code tasks
- **SSE Event Order**: Strict compliance with Anthropic streaming format
- **Heartbeat Pings**: 15-second ping events during long generations
- **Response Caching**: Redis-backed caching for deterministic requests (temperature <= 0.1)
- **Rate Limiting**: Configurable per-minute rate limits with Redis backend
- **Prometheus Metrics**: Request counts, latency, token usage
- **Structured Logging**: JSON logging with structlog
- **Schema Validation**: All responses validated against Anthropic schemas

## Configuration

Copy `.env.example` to `.env` and configure:

```bash
# Required
CEREBRAS_API_KEY=your-cerebras-key
GATEWAY_API_KEYS=your-gateway-key-1,your-gateway-key-2

# Optional
RATE_LIMIT_ENABLED=false
CACHE_ENABLED=false
```

See `.env.example` for all configuration options.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/messages` | POST | Create message (streaming/non-streaming) |
| `/v1/messages/count_tokens` | POST | Estimate token count |
| `/health` | GET | Health check |
| `/metrics` | GET | Prometheus metrics |

## Model Mapping

All Anthropic model requests are routed to Cerebras `zai-glm-4.7`.

| Anthropic Model | Cerebras Model |
|-----------------|----------------|
| claude-sonnet-4-* | zai-glm-4.7 |
| claude-3-5-sonnet-* | zai-glm-4.7 |
| claude-3-opus-* | zai-glm-4.7 |
| claude-3-5-haiku-* | zai-glm-4.7 |
| claude-3-haiku-* | zai-glm-4.7 |
| (any model) | zai-glm-4.7 |

**Note**: The gateway echoes back the requested model name in responses while internally using `zai-glm-4.7`.

## Critical Implementation Rules

1. **Model Echo-Back**: Response always contains the requested model name, not internal model
2. **System Prompt Prefixing**: Behavioral guidelines are PREFIXED to user's system prompt, never overwriting
3. **Temperature Adjustment**: Multiplied by 0.85 for code generation tasks
4. **SSE Event Order**: message_start → content_block_start → content_block_delta(s) → content_block_stop → message_delta → message_stop
5. **Heartbeat**: Ping event emitted every 15 seconds during streaming
6. **Validation**: All responses validated against Pydantic schemas before returning

## Testing

```bash
# Unit tests
pytest tests/unit/ -v

# Integration tests
pytest tests/integration/ -v

# Compatibility test harness
python benchmarks/compatibility_harness.py http://localhost:8080 test-key

# Load test (100 concurrent streams)
python benchmarks/load_test.py http://localhost:8080 test-key 100
```

## Deployment

### Docker Compose (Development)

```bash
docker-compose up
```

### Production

```bash
docker build -t cerebras-gateway .
docker run -p 8080:8080 \
  -e CEREBRAS_API_KEY=your-key \
  -e ENVIRONMENT=production \
  cerebras-gateway
```

## Success Criteria

- [x] Claude Code works without any code changes
- [x] Cursor IDE works without any code changes
- [x] All streaming events match Anthropic format exactly
- [x] Handle 100+ concurrent streams without degradation
- [x] Smoke tests pass on every deployment
- [x] Zero schema validation errors

## Project Structure

```
├── app/
│   ├── api/
│   │   ├── routes/          # API endpoints
│   │   └── middleware/      # Auth, rate limiting, validation
│   ├── clients/             # Cerebras API client
│   ├── models/              # Pydantic schemas
│   ├── services/            # Cache, routing, fallback
│   ├── translators/         # Request/response translation
│   └── utils/               # Logging, metrics, validation
├── tests/
│   ├── unit/
│   └── integration/
├── benchmarks/              # Compatibility and load tests
├── scripts/                 # Deployment scripts
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## License

MIT
