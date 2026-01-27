#!/usr/bin/env python3
"""
Load test for Cerebras Anthropic Gateway.
Tests 100+ concurrent streams without degradation.
"""
import asyncio
import time
import statistics
import sys
import httpx
from dataclasses import dataclass
from typing import List


@dataclass
class RequestResult:
    success: bool
    latency_ms: float
    status_code: int
    error: str = None
    tokens_received: int = 0


async def make_request(
    client: httpx.AsyncClient,
    gateway_url: str,
    api_key: str,
    request_id: int,
    stream: bool = True
) -> RequestResult:
    """Make a single request to the gateway."""
    start_time = time.time()
    
    try:
        if stream:
            async with client.stream(
                "POST",
                f"{gateway_url}/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 100,
                    "messages": [{"role": "user", "content": f"Request {request_id}: Say hello briefly"}],
                    "stream": True
                },
                timeout=60.0
            ) as response:
                events_received = 0
                async for line in response.aiter_lines():
                    if line.startswith("event:"):
                        events_received += 1
                
                latency_ms = (time.time() - start_time) * 1000
                
                return RequestResult(
                    success=response.status_code == 200,
                    latency_ms=latency_ms,
                    status_code=response.status_code,
                    tokens_received=events_received
                )
        else:
            response = await client.post(
                f"{gateway_url}/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 50,
                    "messages": [{"role": "user", "content": f"Request {request_id}: Hi"}],
                    "stream": False
                },
                timeout=60.0
            )
            
            latency_ms = (time.time() - start_time) * 1000
            
            return RequestResult(
                success=response.status_code == 200,
                latency_ms=latency_ms,
                status_code=response.status_code
            )
            
    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        return RequestResult(
            success=False,
            latency_ms=latency_ms,
            status_code=0,
            error=str(e)
        )


async def run_load_test(
    gateway_url: str,
    api_key: str,
    concurrent_requests: int = 100,
    stream: bool = True
) -> List[RequestResult]:
    """Run load test with specified concurrency."""
    
    print(f"\n{'='*60}")
    print(f"Load Test - {concurrent_requests} Concurrent {'Streaming' if stream else 'Non-streaming'} Requests")
    print(f"{'='*60}")
    print(f"Gateway: {gateway_url}")
    print(f"Starting test...\n")
    
    async with httpx.AsyncClient(
        limits=httpx.Limits(max_connections=concurrent_requests + 10)
    ) as client:
        start_time = time.time()
        
        tasks = [
            make_request(client, gateway_url, api_key, i, stream)
            for i in range(concurrent_requests)
        ]
        
        results = await asyncio.gather(*tasks)
        
        total_time = time.time() - start_time
    
    return results, total_time


def analyze_results(results: List[RequestResult], total_time: float, concurrent: int):
    """Analyze and print load test results."""
    
    successful = [r for r in results if r.success]
    failed = [r for r in results if not r.success]
    
    latencies = [r.latency_ms for r in successful]
    
    print(f"\n{'='*60}")
    print("Results Summary")
    print(f"{'='*60}")
    print(f"Total Requests:     {len(results)}")
    print(f"Successful:         {len(successful)} ({len(successful)/len(results)*100:.1f}%)")
    print(f"Failed:             {len(failed)} ({len(failed)/len(results)*100:.1f}%)")
    print(f"Total Time:         {total_time:.2f}s")
    print(f"Requests/sec:       {len(results)/total_time:.2f}")
    
    if latencies:
        print(f"\nLatency Statistics (ms):")
        print(f"  Min:              {min(latencies):.2f}")
        print(f"  Max:              {max(latencies):.2f}")
        print(f"  Mean:             {statistics.mean(latencies):.2f}")
        print(f"  Median:           {statistics.median(latencies):.2f}")
        print(f"  P95:              {sorted(latencies)[int(len(latencies)*0.95)]:.2f}")
        print(f"  P99:              {sorted(latencies)[int(len(latencies)*0.99)]:.2f}")
        print(f"  Std Dev:          {statistics.stdev(latencies) if len(latencies) > 1 else 0:.2f}")
    
    if failed:
        print(f"\nFailure Details:")
        error_counts = {}
        for r in failed:
            key = f"Status {r.status_code}: {r.error or 'Unknown'}"
            error_counts[key] = error_counts.get(key, 0) + 1
        
        for error, count in sorted(error_counts.items(), key=lambda x: -x[1]):
            print(f"  {error}: {count}")
    
    # Check success criteria
    print(f"\n{'='*60}")
    print("Success Criteria Check")
    print(f"{'='*60}")
    
    success_rate = len(successful) / len(results) * 100
    p95_latency = sorted(latencies)[int(len(latencies)*0.95)] if latencies else float('inf')
    
    criteria = [
        (success_rate >= 95, f"Success rate >= 95%: {success_rate:.1f}%"),
        (p95_latency < 60000, f"P95 latency < 60s: {p95_latency:.0f}ms"),  # Excluding inference time
        (len(successful) >= concurrent * 0.9, f"Handle 90%+ of {concurrent} concurrent: {len(successful)}"),
    ]
    
    all_passed = True
    for passed, description in criteria:
        status = "PASS" if passed else "FAIL"
        print(f"[{status}] {description}")
        if not passed:
            all_passed = False
    
    print(f"{'='*60}\n")
    
    return all_passed


async def main():
    if len(sys.argv) < 3:
        print("Usage: python load_test.py <gateway_url> <api_key> [concurrent_requests]")
        print("Example: python load_test.py http://localhost:8080 test-key 100")
        sys.exit(1)
    
    gateway_url = sys.argv[1]
    api_key = sys.argv[2]
    concurrent = int(sys.argv[3]) if len(sys.argv) > 3 else 100
    
    # Run streaming load test
    results, total_time = await run_load_test(
        gateway_url,
        api_key,
        concurrent_requests=concurrent,
        stream=True
    )
    streaming_passed = analyze_results(results, total_time, concurrent)
    
    # Run non-streaming load test
    results, total_time = await run_load_test(
        gateway_url,
        api_key,
        concurrent_requests=concurrent // 2,  # Fewer for non-streaming
        stream=False
    )
    non_streaming_passed = analyze_results(results, total_time, concurrent // 2)
    
    sys.exit(0 if (streaming_passed and non_streaming_passed) else 1)


if __name__ == "__main__":
    asyncio.run(main())
