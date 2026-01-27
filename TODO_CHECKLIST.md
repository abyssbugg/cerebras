# Cerebras Anthropic Gateway - Todo Checklist

## Project Goal
Build API gateway: Anthropic Messages API → Cerebras Inference
**Result**: Use Claude Code with Cerebras (2 env vars, zero code changes)

---

## 20 Tasks - Checked in Order

### Week 1: Core Foundation (Tasks 1-8)

- [ ] 1. Create project structure with FastAPI, config, and dependencies
- [ ] 2. Define Pydantic models for Anthropic and Cerebras request/response schemas  
- [ ] 3. Implement request/response translators (Anthropic to Cerebras Chat format)
- [ ] 4. Build SSE event translation with heartbeat/ping support
- [ ] 5. Implement async Cerebras API client with streaming and retry logic
- [ ] 6. Create /v1/messages endpoint with full Anthropic compatibility
- [ ] 7. Implement /v1/messages/count_tokens as best-effort estimation
- [ ] 8. Implement API key auth, rate limiting, and request validation/sanitization

### Week 2: Production Features (Tasks 9-15)

- [ ] 9. Build enhanced prompt tuning layer for Claude-like behavior
- [ ] 10. Add response post-processing for code blocks and formatting
- [ ] 11. Set up Prometheus metrics, structured logging, OpenTelemetry tracing
- [ ] 12. Implement response caching for deterministic requests (temperature=0)
- [ ] 13. Build intelligent model router based on task type
- [ ] 14. Implement graceful degradation with fallback provider support
- [ ] 15. Create Dockerfile and deployment configurations

### Week 3: Quality Assurance (Tasks 16-20)

- [ ] 16. Implement strict Anthropic schema validator for all responses and SSE events
- [ ] 17. Build compatibility test harness comparing against Anthropic behavior
- [ ] 18. Create deployment smoke test script for post-deployment verification
- [ ] 19. Create unit, integration, and load tests
- [ ] 20. Write README, API docs, and usage examples

---

## Critical Rules to Follow

1. **Model Echo-Back**: Always return requested model name (not internal model)
2. **System Prompt**: PREFIX behavioral guidelines, never overwrite user prompt
3. **Temperature**: Multiply by 0.85 for code tasks
4. **SSE Order**: message_start → content_block_start → deltas → content_block_stop → message_delta → message_stop
5. **Heartbeat**: Ping event every 15 seconds during streaming
6. **Validation**: Validate ALL responses against Pydantic schemas

---

## Files to Create (33 total)

### Core (8 files)
- app/main.py, app/config.py
- app/api/routes/{messages,token_count,health}.py
- app/api/middleware/{auth,rate_limit,validation}.py

### Translation (5 files)
- app/translators/{request,response,streaming,prompt_tuning,response_enhancer}.py

### Services (4 files)
- app/services/{cache_service,model_router,fallback_service,usage_tracker}.py

### Models & Utils (7 files)
- app/models/{anthropic,cerebras,errors}.py
- app/clients/cerebras.py
- app/utils/{logging,metrics,tokenizer,schema_validator}.py

### Deployment & Tests (9 files)
- Dockerfile, docker-compose.yml, requirements.txt, README.md, .env.example
- scripts/smoke_test.sh
- tests/unit/{test_translation,test_streaming}.py
- benchmarks/compatibility_harness.py

---

## Quick Test After Build

```bash
docker-compose up
./scripts/smoke_test.sh http://localhost:8080 test-key
```

Done when: Claude Code works with 2 env var changes, all smoke tests pass.
