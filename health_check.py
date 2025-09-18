#!/usr/bin/env python3
"""Simple health check script for deployment verification."""

import sys
import asyncio
import aiohttp
import argparse


async def check_health(url: str, timeout: int = 10) -> bool:
    """Check if the API is healthy."""
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
            async with session.get(f"{url}/health") as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("status") == "healthy":
                        print(f"✓ API is healthy at {url}")
                        print(f"  Version: {data.get('version', 'unknown')}")
                        print(f"  Timestamp: {data.get('timestamp', 'unknown')}")
                        return True
                    else:
                        print(f"✗ API returned unhealthy status: {data}")
                        return False
                else:
                    print(f"✗ API returned status code: {response.status}")
                    return False
    
    except asyncio.TimeoutError:
        print(f"✗ Timeout connecting to {url}")
        return False
    except Exception as e:
        print(f"✗ Error connecting to {url}: {e}")
        return False


async def check_endpoints(url: str, timeout: int = 10) -> bool:
    """Check if all endpoints are accessible."""
    endpoints = [
        "/health",
        "/docs",
        "/openapi.json"
    ]
    
    all_good = True
    
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
            for endpoint in endpoints:
                try:
                    async with session.get(f"{url}{endpoint}") as response:
                        if response.status < 400:
                            print(f"✓ {endpoint} - Status: {response.status}")
                        else:
                            print(f"✗ {endpoint} - Status: {response.status}")
                            all_good = False
                except Exception as e:
                    print(f"✗ {endpoint} - Error: {e}")
                    all_good = False
    
    except Exception as e:
        print(f"✗ Failed to check endpoints: {e}")
        return False
    
    return all_good


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Health check for Caten API")
    parser.add_argument("--url", default="http://localhost:8000", help="API URL to check")
    parser.add_argument("--timeout", type=int, default=10, help="Timeout in seconds")
    parser.add_argument("--endpoints", action="store_true", help="Check all endpoints")
    
    args = parser.parse_args()
    
    print(f"Checking Caten API at {args.url}...")
    
    if args.endpoints:
        success = asyncio.run(check_endpoints(args.url, args.timeout))
    else:
        success = asyncio.run(check_health(args.url, args.timeout))
    
    if success:
        print("✓ All checks passed!")
        sys.exit(0)
    else:
        print("✗ Health check failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
