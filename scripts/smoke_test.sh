#!/bin/bash
#
# Smoke Test Script for Cerebras Anthropic Gateway
# Usage: ./smoke_test.sh <gateway_url> <api_key>
# Example: ./smoke_test.sh http://localhost:8080 test-key
#

set -e

GATEWAY_URL="${1:-http://localhost:8080}"
API_KEY="${2:-test-key}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PASSED=0
FAILED=0

log_pass() {
    echo -e "${GREEN}[PASS]${NC} $1"
    ((PASSED++))
}

log_fail() {
    echo -e "${RED}[FAIL]${NC} $1"
    ((FAILED++))
}

log_info() {
    echo -e "${YELLOW}[INFO]${NC} $1"
}

echo ""
echo "=============================================="
echo "Cerebras Anthropic Gateway - Smoke Tests"
echo "=============================================="
echo "Gateway URL: ${GATEWAY_URL}"
echo "=============================================="
echo ""

# Test 1: Health Check
log_info "Testing health endpoint..."
HEALTH_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" "${GATEWAY_URL}/health")
if [ "$HEALTH_RESPONSE" = "200" ]; then
    log_pass "Health check returned 200"
else
    log_fail "Health check failed with status $HEALTH_RESPONSE"
fi

# Test 2: Root Endpoint
log_info "Testing root endpoint..."
ROOT_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" "${GATEWAY_URL}/")
if [ "$ROOT_RESPONSE" = "200" ]; then
    log_pass "Root endpoint returned 200"
else
    log_fail "Root endpoint failed with status $ROOT_RESPONSE"
fi

# Test 3: Metrics Endpoint
log_info "Testing metrics endpoint..."
METRICS_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" "${GATEWAY_URL}/metrics")
if [ "$METRICS_RESPONSE" = "200" ]; then
    log_pass "Metrics endpoint returned 200"
else
    log_fail "Metrics endpoint failed with status $METRICS_RESPONSE"
fi

# Test 4: Authentication Required
log_info "Testing authentication requirement..."
AUTH_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST "${GATEWAY_URL}/v1/messages" \
    -H "Content-Type: application/json" \
    -d '{"model":"claude-sonnet-4","max_tokens":10,"messages":[{"role":"user","content":"hi"}]}')
if [ "$AUTH_RESPONSE" = "401" ]; then
    log_pass "Authentication correctly required (401)"
else
    log_fail "Authentication not enforced, got status $AUTH_RESPONSE"
fi

# Test 5: Non-streaming Request
log_info "Testing non-streaming request..."
NON_STREAM_RESPONSE=$(curl -s -w "\n%{http_code}" \
    -X POST "${GATEWAY_URL}/v1/messages" \
    -H "x-api-key: ${API_KEY}" \
    -H "anthropic-version: 2023-06-01" \
    -H "Content-Type: application/json" \
    -d '{"model":"claude-sonnet-4-20250514","max_tokens":50,"messages":[{"role":"user","content":"Say hello in one word"}],"stream":false}')

HTTP_CODE=$(echo "$NON_STREAM_RESPONSE" | tail -n1)
BODY=$(echo "$NON_STREAM_RESPONSE" | sed '$d')

if [ "$HTTP_CODE" = "200" ]; then
    # Check for required fields
    if echo "$BODY" | grep -q '"type":"message"'; then
        log_pass "Non-streaming request successful with correct response type"
    else
        log_fail "Non-streaming response missing 'type:message'"
    fi
    
    # Check model echo-back
    if echo "$BODY" | grep -q '"model":"claude-sonnet-4-20250514"'; then
        log_pass "Model correctly echoed back"
    else
        log_fail "Model not echoed back correctly"
    fi
else
    log_fail "Non-streaming request failed with status $HTTP_CODE"
    echo "Response: $BODY"
fi

# Test 6: Streaming Request
log_info "Testing streaming request..."
STREAM_OUTPUT=$(curl -s -N \
    -X POST "${GATEWAY_URL}/v1/messages" \
    -H "x-api-key: ${API_KEY}" \
    -H "anthropic-version: 2023-06-01" \
    -H "Content-Type: application/json" \
    -d '{"model":"claude-sonnet-4-20250514","max_tokens":50,"messages":[{"role":"user","content":"Hi"}],"stream":true}' \
    --max-time 30 2>&1)

# Check for SSE event markers
if echo "$STREAM_OUTPUT" | grep -q "event: message_start"; then
    log_pass "Streaming: message_start event received"
else
    log_fail "Streaming: missing message_start event"
fi

if echo "$STREAM_OUTPUT" | grep -q "event: content_block_start"; then
    log_pass "Streaming: content_block_start event received"
else
    log_fail "Streaming: missing content_block_start event"
fi

if echo "$STREAM_OUTPUT" | grep -q "event: content_block_delta"; then
    log_pass "Streaming: content_block_delta events received"
else
    log_fail "Streaming: missing content_block_delta events"
fi

if echo "$STREAM_OUTPUT" | grep -q "event: message_stop"; then
    log_pass "Streaming: message_stop event received"
else
    log_fail "Streaming: missing message_stop event"
fi

# Test 7: Token Count Endpoint
log_info "Testing token count endpoint..."
TOKEN_RESPONSE=$(curl -s -w "\n%{http_code}" \
    -X POST "${GATEWAY_URL}/v1/messages/count_tokens" \
    -H "x-api-key: ${API_KEY}" \
    -H "Content-Type: application/json" \
    -d '{"model":"claude-sonnet-4-20250514","messages":[{"role":"user","content":"Hello world"}]}')

HTTP_CODE=$(echo "$TOKEN_RESPONSE" | tail -n1)
BODY=$(echo "$TOKEN_RESPONSE" | sed '$d')

if [ "$HTTP_CODE" = "200" ]; then
    if echo "$BODY" | grep -q '"input_tokens"'; then
        log_pass "Token count endpoint returned input_tokens"
    else
        log_fail "Token count missing input_tokens field"
    fi
else
    log_fail "Token count endpoint failed with status $HTTP_CODE"
fi

# Test 8: Invalid Request Handling
log_info "Testing invalid request handling..."
INVALID_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST "${GATEWAY_URL}/v1/messages" \
    -H "x-api-key: ${API_KEY}" \
    -H "Content-Type: application/json" \
    -d '{"invalid":"request"}')
if [ "$INVALID_RESPONSE" = "422" ] || [ "$INVALID_RESPONSE" = "400" ]; then
    log_pass "Invalid request correctly rejected ($INVALID_RESPONSE)"
else
    log_fail "Invalid request not rejected properly, got $INVALID_RESPONSE"
fi

# Summary
echo ""
echo "=============================================="
echo "Smoke Test Summary"
echo "=============================================="
echo -e "${GREEN}Passed: ${PASSED}${NC}"
echo -e "${RED}Failed: ${FAILED}${NC}"
echo "=============================================="
echo ""

if [ $FAILED -gt 0 ]; then
    echo -e "${RED}Some tests failed!${NC}"
    exit 1
else
    echo -e "${GREEN}All tests passed!${NC}"
    exit 0
fi
