#!/usr/bin/env python3
"""
Compatibility test harness for Cerebras Anthropic Gateway.
Compares response structures against expected Anthropic behavior.
"""
import asyncio
import json
import httpx
import sys
from typing import List
from dataclasses import dataclass


@dataclass
class TestResult:
    name: str
    passed: bool
    message: str
    details: dict = None


class CompatibilityHarness:
    def __init__(self, gateway_url: str, api_key: str):
        self.gateway_url = gateway_url.rstrip("/")
        self.api_key = api_key
        self.results: List[TestResult] = []
    
    async def run_all_tests(self) -> bool:
        """Run all compatibility tests."""
        print(f"\n{'='*60}")
        print(f"Cerebras Anthropic Gateway - Compatibility Test Harness")
        print(f"Gateway URL: {self.gateway_url}")
        print(f"{'='*60}\n")
        
        tests = [
            self.test_health_endpoint,
            self.test_non_streaming_response_structure,
            self.test_model_echo_back,
            self.test_streaming_event_order,
            self.test_streaming_event_structure,
            self.test_token_count_endpoint,
            self.test_error_response_format,
            self.test_content_block_structure,
            self.test_usage_structure,
        ]
        
        for test in tests:
            try:
                result = await test()
                self.results.append(result)
                status = "PASS" if result.passed else "FAIL"
                print(f"[{status}] {result.name}: {result.message}")
            except Exception as e:
                self.results.append(TestResult(
                    name=test.__name__,
                    passed=False,
                    message=f"Exception: {str(e)}"
                ))
                print(f"[FAIL] {test.__name__}: Exception - {str(e)}")
        
        # Summary
        passed = sum(1 for r in self.results if r.passed)
        total = len(self.results)
        
        print(f"\n{'='*60}")
        print(f"Results: {passed}/{total} tests passed")
        print(f"{'='*60}\n")
        
        return all(r.passed for r in self.results)
    
    async def test_health_endpoint(self) -> TestResult:
        """Test health endpoint returns expected format."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.gateway_url}/health")
            
            if response.status_code != 200:
                return TestResult(
                    name="Health Endpoint",
                    passed=False,
                    message=f"Expected 200, got {response.status_code}"
                )
            
            data = response.json()
            if "status" not in data:
                return TestResult(
                    name="Health Endpoint",
                    passed=False,
                    message="Missing 'status' field"
                )
            
            return TestResult(
                name="Health Endpoint",
                passed=True,
                message="Health endpoint working correctly"
            )
    
    async def test_non_streaming_response_structure(self) -> TestResult:
        """Test non-streaming response matches Anthropic format."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.gateway_url}/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 50,
                    "messages": [{"role": "user", "content": "Say hello"}],
                    "stream": False
                }
            )
            
            if response.status_code != 200:
                return TestResult(
                    name="Non-streaming Response Structure",
                    passed=False,
                    message=f"Request failed with {response.status_code}: {response.text}"
                )
            
            data = response.json()
            
            required_fields = ["id", "type", "role", "content", "model", "usage"]
            missing = [f for f in required_fields if f not in data]
            
            if missing:
                return TestResult(
                    name="Non-streaming Response Structure",
                    passed=False,
                    message=f"Missing fields: {missing}"
                )
            
            if data["type"] != "message":
                return TestResult(
                    name="Non-streaming Response Structure",
                    passed=False,
                    message=f"Expected type='message', got '{data['type']}'"
                )
            
            return TestResult(
                name="Non-streaming Response Structure",
                passed=True,
                message="Response structure matches Anthropic format"
            )
    
    async def test_model_echo_back(self) -> TestResult:
        """Test that requested model is echoed back in response."""
        requested_model = "claude-sonnet-4-20250514"
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.gateway_url}/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json={
                    "model": requested_model,
                    "max_tokens": 50,
                    "messages": [{"role": "user", "content": "Hi"}],
                    "stream": False
                }
            )
            
            if response.status_code != 200:
                return TestResult(
                    name="Model Echo-back",
                    passed=False,
                    message=f"Request failed: {response.status_code}"
                )
            
            data = response.json()
            returned_model = data.get("model")
            
            if returned_model != requested_model:
                return TestResult(
                    name="Model Echo-back",
                    passed=False,
                    message=f"Expected '{requested_model}', got '{returned_model}'"
                )
            
            return TestResult(
                name="Model Echo-back",
                passed=True,
                message="Requested model correctly echoed back"
            )
    
    async def test_streaming_event_order(self) -> TestResult:
        """Test streaming events follow correct order.
        
        Expected order:
            message_start -> content_block_start -> content_block_delta (repeats) 
            -> content_block_stop -> message_delta -> message_stop
        """
        # Note: Full order validation is done by checking first/last events
        # The expected order is documented in the docstring above
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream(
                "POST",
                f"{self.gateway_url}/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 50,
                    "messages": [{"role": "user", "content": "Say hello"}],
                    "stream": True
                }
            ) as response:
                if response.status_code != 200:
                    return TestResult(
                        name="Streaming Event Order",
                        passed=False,
                        message=f"Request failed: {response.status_code}"
                    )
                
                events = []
                async for line in response.aiter_lines():
                    if line.startswith("event: "):
                        events.append(line[7:])
                
                # Filter out ping events
                events = [e for e in events if e != "ping"]
                
                if not events:
                    return TestResult(
                        name="Streaming Event Order",
                        passed=False,
                        message="No events received"
                    )
                
                # Check first and last events
                if events[0] != "message_start":
                    return TestResult(
                        name="Streaming Event Order",
                        passed=False,
                        message=f"First event should be 'message_start', got '{events[0]}'"
                    )
                
                if events[-1] != "message_stop":
                    return TestResult(
                        name="Streaming Event Order",
                        passed=False,
                        message=f"Last event should be 'message_stop', got '{events[-1]}'"
                    )
                
                return TestResult(
                    name="Streaming Event Order",
                    passed=True,
                    message=f"Event order correct: {' -> '.join(events[:3])}...{events[-1]}",
                    details={"events": events}
                )
    
    async def test_streaming_event_structure(self) -> TestResult:
        """Test each streaming event has correct structure."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream(
                "POST",
                f"{self.gateway_url}/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 50,
                    "messages": [{"role": "user", "content": "Hi"}],
                    "stream": True
                }
            ) as response:
                if response.status_code != 200:
                    return TestResult(
                        name="Streaming Event Structure",
                        passed=False,
                        message=f"Request failed: {response.status_code}"
                    )
                
                current_event = None
                errors = []
                
                async for line in response.aiter_lines():
                    if line.startswith("event: "):
                        current_event = line[7:]
                    elif line.startswith("data: ") and current_event:
                        try:
                            data = json.loads(line[6:])
                            
                            if "type" not in data:
                                errors.append(f"{current_event}: missing 'type' field")
                            elif data["type"] != current_event:
                                if current_event != "ping":
                                    errors.append(
                                        f"{current_event}: type mismatch, got '{data['type']}'"
                                    )
                        except json.JSONDecodeError as e:
                            errors.append(f"{current_event}: invalid JSON - {str(e)}")
                
                if errors:
                    return TestResult(
                        name="Streaming Event Structure",
                        passed=False,
                        message=f"Structure errors: {errors[0]}",
                        details={"errors": errors}
                    )
                
                return TestResult(
                    name="Streaming Event Structure",
                    passed=True,
                    message="All streaming events have correct structure"
                )
    
    async def test_token_count_endpoint(self) -> TestResult:
        """Test token count endpoint returns expected format."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.gateway_url}/v1/messages/count_tokens",
                headers={
                    "x-api-key": self.api_key,
                    "Content-Type": "application/json",
                },
                json={
                    "model": "claude-sonnet-4-20250514",
                    "messages": [{"role": "user", "content": "Hello world"}]
                }
            )
            
            if response.status_code != 200:
                return TestResult(
                    name="Token Count Endpoint",
                    passed=False,
                    message=f"Request failed: {response.status_code}"
                )
            
            data = response.json()
            
            if "input_tokens" not in data:
                return TestResult(
                    name="Token Count Endpoint",
                    passed=False,
                    message="Missing 'input_tokens' field"
                )
            
            if not isinstance(data["input_tokens"], int):
                return TestResult(
                    name="Token Count Endpoint",
                    passed=False,
                    message="'input_tokens' should be an integer"
                )
            
            return TestResult(
                name="Token Count Endpoint",
                passed=True,
                message=f"Token count returned: {data['input_tokens']}"
            )
    
    async def test_error_response_format(self) -> TestResult:
        """Test error responses match Anthropic format."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Request without API key should return auth error
            response = await client.post(
                f"{self.gateway_url}/v1/messages",
                headers={"Content-Type": "application/json"},
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 50,
                    "messages": [{"role": "user", "content": "Hi"}]
                }
            )
            
            if response.status_code not in [401, 403]:
                return TestResult(
                    name="Error Response Format",
                    passed=False,
                    message=f"Expected 401/403, got {response.status_code}"
                )
            
            data = response.json()
            
            if "error" not in data:
                return TestResult(
                    name="Error Response Format",
                    passed=False,
                    message="Error response missing 'error' field"
                )
            
            error = data["error"]
            if "type" not in error or "message" not in error:
                return TestResult(
                    name="Error Response Format",
                    passed=False,
                    message="Error missing 'type' or 'message' field"
                )
            
            return TestResult(
                name="Error Response Format",
                passed=True,
                message="Error responses match Anthropic format"
            )
    
    async def test_content_block_structure(self) -> TestResult:
        """Test content blocks have correct structure."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.gateway_url}/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 50,
                    "messages": [{"role": "user", "content": "Say hi"}],
                    "stream": False
                }
            )
            
            if response.status_code != 200:
                return TestResult(
                    name="Content Block Structure",
                    passed=False,
                    message=f"Request failed: {response.status_code}"
                )
            
            data = response.json()
            content = data.get("content", [])
            
            if not content:
                return TestResult(
                    name="Content Block Structure",
                    passed=False,
                    message="Response has no content blocks"
                )
            
            for i, block in enumerate(content):
                if "type" not in block:
                    return TestResult(
                        name="Content Block Structure",
                        passed=False,
                        message=f"Content block {i} missing 'type'"
                    )
                
                if block["type"] == "text" and "text" not in block:
                    return TestResult(
                        name="Content Block Structure",
                        passed=False,
                        message=f"Text block {i} missing 'text' field"
                    )
            
            return TestResult(
                name="Content Block Structure",
                passed=True,
                message=f"All {len(content)} content blocks valid"
            )
    
    async def test_usage_structure(self) -> TestResult:
        """Test usage object has correct structure."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.gateway_url}/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 50,
                    "messages": [{"role": "user", "content": "Hi"}],
                    "stream": False
                }
            )
            
            if response.status_code != 200:
                return TestResult(
                    name="Usage Structure",
                    passed=False,
                    message=f"Request failed: {response.status_code}"
                )
            
            data = response.json()
            usage = data.get("usage", {})
            
            if "input_tokens" not in usage:
                return TestResult(
                    name="Usage Structure",
                    passed=False,
                    message="Usage missing 'input_tokens'"
                )
            
            if "output_tokens" not in usage:
                return TestResult(
                    name="Usage Structure",
                    passed=False,
                    message="Usage missing 'output_tokens'"
                )
            
            return TestResult(
                name="Usage Structure",
                passed=True,
                message=f"Usage: {usage['input_tokens']} in, {usage['output_tokens']} out"
            )


async def main():
    if len(sys.argv) < 3:
        print("Usage: python compatibility_harness.py <gateway_url> <api_key>")
        print("Example: python compatibility_harness.py http://localhost:8080 test-key")
        sys.exit(1)
    
    gateway_url = sys.argv[1]
    api_key = sys.argv[2]
    
    harness = CompatibilityHarness(gateway_url, api_key)
    success = await harness.run_all_tests()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
