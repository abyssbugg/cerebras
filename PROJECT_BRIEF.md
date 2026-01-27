# Cerebras Anthropic Gateway - AI Agent Project Brief

## Project Overview

Build a production-ready API gateway that translates Anthropic Messages API requests to Cerebras inference API. Users can use Claude Code, Cursor, and other Anthropic SDK clients with Cerebras models by changing only 2 environment variables.

**Goal**: Drop-in Anthropic API replacement backed by Cerebras (like GLM and MiniMax do)

**User Setup**:
```bash
export ANTHROPIC_BASE_URL=https://your-gateway.com
export ANTHROPIC_API_KEY=your-gateway-key
# Then use Claude Code normally - zero code changes
```

---

## Complete Todo List (20 Tasks)

### ✅ **Phase 1: Core Foundation (P0 - Week 1)**

1. **Create project structure with FastAPI, config, and dependencies**
   - Set up folder structure with app/, tests/, scripts/, deployment/
   - Create requirements.txt with pinned versions
   - Initialize FastAPI app structure

2. **Define Pydantic models for Anthropic and Cerebras request/response schemas**
   - app/models/anthropic.py - All Anthropic Messages API models
   - app/models/cerebras.py - Cerebras chat completion models
   - Include validation for all fields

3. **Implement request/response translators (Anthropic to Cerebras Chat format)**
   - app/translators/request.py - Anthropic Messages → Cerebras Chat
   - app/translators/response.py - Cerebras → Anthropic Messages
   - Handle model name echo-back (always return requested model)

4. **Build SSE event translation with heartbeat/ping support**
   - app/translators/streaming.py - Convert Cerebras SSE to Anthropic SSE
   - Emit `event: ping` every 15 seconds during long generations
   - Follow exact Anthropic SSE event order

5. **Implement async Cerebras API client with streaming and retry logic**
   - app/clients/cerebras.py - Async httpx client
   - Connection pooling and timeout handling
   - Exponential backoff retry logic

6. **Create /v1/messages endpoint with full Anthropic compatibility**
   - app/api/routes/messages.py - POST /v1/messages
   - Support both streaming and non-streaming
   - Return proper Anthropic response format

7. **Implement /v1/messages/count_tokens as best-effort estimation**
   - app/api/routes/token_count.py - POST /v1/messages/count_tokens
   - Use tiktoken (cl100k_base) for estimation
   - Document as "estimated token counts"

8. **Implement API key auth, rate limiting, and request validation/sanitization**
   - app/api/middleware/auth.py - x-api-key validation
   - app/api/middleware/rate_limit.py - Redis-backed rate limiting
   - app/api/middleware/validation.py - Request sanitization (length limits, etc.)

### ✅ **Phase 2: Production Features (P0 - Week 2)**

9. **Build enhanced prompt tuning layer for Claude-like behavior**
   - app/translators/prompt_tuning.py - Behavioral system prompts
   - Temperature adjustment per task type
   - Never use "Claude" branding - use behavioral instructions

10. **Add response post-processing for code blocks and formatting**
    - app/translators/response_enhancer.py - Add language tags to code blocks
    - Conservative processing - formatting only, no content changes

11. **Set up Prometheus metrics, structured logging, OpenTelemetry tracing**
    - app/utils/metrics.py - Prometheus metrics (request count, latency, tokens)
    - app/utils/logging.py - Structured JSON logging with structlog
    - Add OpenTelemetry middleware for distributed tracing

12. **Implement response caching for deterministic requests (temperature=0)**
    - app/services/cache_service.py - Redis-backed response cache
    - Only cache when temperature <= 0.1
    - TTL: 1 hour default

13. **Build intelligent model router based on task type**
    - app/services/model_router.py - Detect task type from messages
    - Route to optimal Cerebras model (llama-3.3-70b vs llama-3.1-8b)

14. **Implement graceful degradation with fallback provider support**
    - app/services/fallback_service.py - Multi-provider fallback chain
    - Feature-flagged, disabled by default
    - Fallback order: Cerebras → Groq → Together AI

15. **Create Dockerfile and deployment configurations**
    - Dockerfile - Production-ready Python 3.11 image
    - docker-compose.yml - Local development setup with Redis
    - Include Cloud Run and VM deployment notes

### ✅ **Phase 3: Quality Assurance (P1 - Week 3)**

16. **Implement strict Anthropic schema validator for all responses and SSE events**
    - app/utils/schema_validator.py - Validate EVERY response before sending
    - Validate each SSE event against expected schema
    - Prevent silent client failures

17. **Build compatibility test harness comparing against Anthropic behavior**
    - benchmarks/compatibility_harness.py - Compare response structures
    - Validate streaming event order matches Anthropic
    - Test with real Claude Code

18. **Create deployment smoke test script for post-deployment verification**
    - scripts/smoke_test.sh - Automated post-deployment tests
    - Test health check, non-streaming, streaming, token counting
    - Exit with error code if any test fails

19. **Create unit, integration, and load tests**
    - tests/unit/test_translation.py - Translation accuracy
    - tests/unit/test_streaming.py - SSE event formatting
    - tests/integration/test_end_to_end.py - Full request flow
    - benchmarks/load_test.py - 100+ concurrent streams test

20. **Write README, API docs, and usage examples**
    - README.md - Complete setup guide
    - .env.example - All configuration options
    - Include curl examples and troubleshooting

---

## Technical Requirements

### Core Translation Rules

1. **Model Echo-Back**: Always return the requested model name in response (not internal model)
2. **System Prompt**: PREFIX user system prompt with behavioral guidelines, never overwrite
3. **Temperature Adjustment**: Multiply by 0.85 for code generation tasks
4. **SSE Event Order**: message_start → content_block_start → content_block_delta(s) → content_block_stop → message_delta → message_stop
5. **Heartbeat**: Emit `event: ping` every 15 seconds during streaming
6. **Validation**: Validate ALL responses against Pydantic models before returning

### Key Files to Create

**Core Application** (8 files):
- app/main.py
- app/config.py
- app/api/routes/messages.py
- app/api/routes/token_count.py
- app/api/routes/health.py
- app/api/middleware/auth.py
- app/api/middleware/rate_limit.py
- app/api/middleware/validation.py

**Translation Layer** (5 files):
- app/translators/request.py
- app/translators/response.py
- app/translators/streaming.py
- app/translators/prompt_tuning.py
- app/translators/response_enhancer.py

**Services** (4 files):
- app/services/cache_service.py
- app/services/model_router.py
- app/services/fallback_service.py
- app/services/usage_tracker.py

**Clients** (1 file):
- app/clients/cerebras.py

**Models** (3 files):
- app/models/anthropic.py
- app/models/cerebras.py
- app/models/errors.py

**Utilities** (4 files):
- app/utils/logging.py
- app/utils/metrics.py
- app/utils/tokenizer.py
- app/utils/schema_validator.py

**Deployment** (3 files):
- Dockerfile
- docker-compose.yml
- requirements.txt

**Scripts** (1 file):
- scripts/smoke_test.sh

**Tests** (3 files):
- tests/unit/test_translation.py
- tests/unit/test_streaming.py
- benchmarks/compatibility_harness.py

**Documentation** (2 files):
- README.md
- .env.example

**Total**: 33 files

---

## Dependencies (requirements.txt)

```
fastapi==0.109.0
uvicorn[standard]==0.27.0
httpx==0.26.0
pydantic==2.5.0
pydantic-settings==2.1.0
python-dotenv==1.0.0
redis==5.0.1
sse-starlette==1.8.0
tiktoken==0.5.2
prometheus-client==0.19.0
opentelemetry-api==1.22.0
opentelemetry-sdk==1.22.0
opentelemetry-instrumentation-fastapi==0.43b0
structlog==24.1.0
sentry-sdk[fastapi]==1.39.0
```

---

## Environment Variables Required

```bash
# Cerebras API
CEREBRAS_API_KEY=your-cerebras-key
CEREBRAS_BASE_URL=https://api.cerebras.ai/v1
CEREBRAS_MODEL=llama-3.3-70b

# Gateway Config
ENVIRONMENT=production
DEBUG=false
API_KEY_HEADER=x-api-key

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS_PER_MINUTE=60
REDIS_URL=redis://localhost:6379/0

# Optional Features
ENABLE_FALLBACK_PROVIDERS=false
SENTRY_DSN=your-sentry-dsn
```

---

## Success Criteria

- ✅ Claude Code works without any code changes
- ✅ Cursor IDE works without any code changes
- ✅ All streaming events match Anthropic format exactly
- ✅ P95 latency < 200ms (excluding Cerebras inference time)
- ✅ Handle 100+ concurrent streams without degradation
- ✅ Smoke tests pass on every deployment
- ✅ Zero schema validation errors

---

## Quick Start After Build

```bash
# 1. Set environment variables
export CEREBRAS_API_KEY=your-key

# 2. Run with Docker
docker-compose up

# 3. Test with curl
curl -X POST http://localhost:8080/v1/messages \
  -H "x-api-key: test" \
  -H "anthropic-version: 2023-06-01" \
  -d '{"model":"claude-sonnet-4","max_tokens":100,"messages":[{"role":"user","content":"Hello"}]}'

# 4. Run smoke tests
./scripts/smoke_test.sh http://localhost:8080 test-key
```

---

## Reference Plan Location

Full detailed plan: `cerebras_anthropic_gateway_f09e97e1.plan.md`
