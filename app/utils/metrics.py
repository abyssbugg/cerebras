from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi import FastAPI, Request
from fastapi.responses import Response

# Request metrics
REQUEST_COUNT = Counter(
    "cerebras_gateway_requests_total",
    "Total number of requests",
    ["method", "endpoint", "status"]
)

REQUEST_LATENCY = Histogram(
    "cerebras_gateway_request_latency_seconds",
    "Request latency in seconds",
    ["endpoint"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

# Token metrics
TOKENS_PROCESSED = Counter(
    "cerebras_gateway_tokens_total",
    "Total tokens processed",
    ["type"]  # input, output
)

# Connection metrics
ACTIVE_CONNECTIONS = Gauge(
    "cerebras_gateway_active_connections",
    "Number of active connections"
)

STREAMING_CONNECTIONS = Gauge(
    "cerebras_gateway_streaming_connections",
    "Number of active streaming connections"
)
# TODO: Increment in messages.py when stream starts, decrement when complete

# Cache metrics
CACHE_HITS = Counter(
    "cerebras_gateway_cache_hits_total",
    "Total cache hits"
)

CACHE_MISSES = Counter(
    "cerebras_gateway_cache_misses_total",
    "Total cache misses"
)

# Error metrics
ERROR_COUNT = Counter(
    "cerebras_gateway_errors_total",
    "Total errors",
    ["error_type"]
)

# Upstream metrics
UPSTREAM_LATENCY = Histogram(
    "cerebras_gateway_upstream_latency_seconds",
    "Upstream (Cerebras) latency in seconds",
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0]
)
# TODO: Track in cerebras_client.py before/after API calls


def setup_metrics(app: FastAPI):
    """Set up Prometheus metrics endpoint.
    
    NOTE: This only adds the /metrics endpoint. Middleware for tracking
    active connections should be added in main.py BEFORE app startup.
    """
    
    @app.get("/metrics")
    async def metrics():
        return Response(
            content=generate_latest(),
            media_type=CONTENT_TYPE_LATEST
        )


async def track_active_connections(request: Request, call_next):
    """Middleware to track active connections. Add this in main.py."""
    ACTIVE_CONNECTIONS.inc()
    try:
        response = await call_next(request)
        return response
    finally:
        ACTIVE_CONNECTIONS.dec()
