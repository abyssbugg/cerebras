# Changelog

All notable changes to the Cerebras Anthropic Gateway will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-01-29

### Added
- Configurable CORS origins via `CORS_ORIGINS` environment variable
- Configurable connection timeouts (`CEREBRAS_TIMEOUT_SECONDS`, `CEREBRAS_CONNECT_TIMEOUT_SECONDS`)
- Configurable max retries (`CEREBRAS_MAX_RETRIES`)
- Thread-safe in-memory rate limiting with `threading.Lock`
- Unit tests for rate limiting middleware
- Unit tests for cache service
- CONTRIBUTING.md with development guidelines
- Performance tuning documentation for uvicorn workers
- `requirements.lock` for reproducible builds
- Validation of `/anthropic/v1/messages` path in addition to `/v1/messages`
- Request body caching in validation middleware via `request.state.validated_body`

### Changed
- Default Cerebras model updated to `zai-glm-4.7` in all configuration files
- Updated docker-compose.yml to use `zai-glm-4.7` as default model
- Improved documentation for optional services (fallback, usage tracking)
- Test suite updated to use correct model name (`zai-glm-4.7`)

### Fixed
- CORS security: Now configurable instead of hardcoded wildcard
- Thread safety: In-memory rate limit store now uses lock for concurrent access
- Test model mismatch: All tests now use `zai-glm-4.7` instead of `llama-3.3-70b`

### Security
- CORS origins now configurable (default: `*` for development, should be restricted in production)

## [1.0.0] - 2026-01-15

### Added
- Initial release of Cerebras Anthropic Gateway
- Full Anthropic Messages API compatibility
- Streaming and non-streaming support
- SSE event compliance with Anthropic format
- Model echo-back (always returns requested model name)
- Behavioral system prompt prefixing
- Temperature adjustment for code tasks (0.85x multiplier)
- Heartbeat ping events during streaming (15-second intervals)
- Redis-backed response caching
- Redis-backed rate limiting with in-memory fallback
- Prometheus metrics endpoint
- Structured JSON logging with structlog
- Schema validation for all responses
- Token counting endpoint
- Health check endpoint
- Docker and docker-compose support
- Render.com deployment support

### Features
- Passthrough authentication mode (users provide Cerebras API key)
- Gateway authentication mode (server-issued keys)
- Multi-provider fallback support (Groq, Together AI) - optional
- Usage tracking per API key - optional

### Compatibility
- Claude Code
- Cursor IDE
- Droid CLI
- Any Anthropic SDK client

---

## Version History

| Version | Date | Status |
|---------|------|--------|
| 1.1.0 | 2026-01-29 | Current |
| 1.0.0 | 2026-01-15 | Initial Release |
