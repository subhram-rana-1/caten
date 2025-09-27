#!/usr/bin/env python3
"""Test script for the v2/simplify SSE API endpoint."""

import asyncio
import httpx
import json
from typing import List, Dict, Any

async def test_simplify_sse():
    """Test the simplify SSE endpoint."""
    base_url = "http://localhost:8000"
    
    # Test data - multiple text objects to simplify
    test_data = [
        {
            "textStartIndex": 56,
            "textLength": 275,
            "text": "The serendipitous discovery of the ancient manuscript in the sepulchral chamber of the abandoned cathedral was nothing short of preternatural. Scholars were perplexed by its ineffable contents, which seemed to defy conventional epistemology.",
            "previousSimplifiedTexts": [
                "Finding the old manuscript in the tomb of the empty cathedral was an amazing surprise. Experts were confused by its mysterious contents, which seemed to challenge normal ways of understanding."
            ]
        },
        {
            "textStartIndex": 256,
            "textLength": 309,
            "text": "The palimpsest was so obfuscated by time that many feared the inextricable truth within it would remain hidden forever. The entire expedition was surrounded by an air of elusive mystery, as if the document itself held an inscrutable power over its seekers.",
            "previousSimplifiedTexts": [
                "The old document was so faded that people worried its secrets might never be found. The whole search felt mysterious, as if the document had a strange hold on those looking for it."
            ]
        }
    ]
    
    print("Testing v2/simplify SSE endpoint...")
    print(f"Request data: {json.dumps(test_data, indent=2)}")
    print("\n" + "="*50)
    print("SSE Response:")
    print("="*50)
    
    async with httpx.AsyncClient() as client:
        try:
            async with client.stream(
                "POST",
                f"{base_url}/api/v2/simplify",
                json=test_data,
                headers={"Accept": "text/event-stream"}
            ) as response:
                print(f"Status Code: {response.status_code}")
                print(f"Headers: {dict(response.headers)}")
                print("\nStreaming data:")
                print("-" * 30)
                
                event_count = 0
                async for line in response.aiter_lines():
                    if line.strip():
                        print(f"Line {event_count + 1}: {line}")
                        
                        # Parse SSE data
                        if line.startswith("data: "):
                            data_content = line[6:]  # Remove "data: " prefix
                            
                            if data_content == "[DONE]":
                                print("\n✅ Stream completed successfully!")
                                break
                            elif data_content.startswith("{"):
                                try:
                                    # Parse the JSON data
                                    event_data = json.loads(data_content)
                                    print(f"✅ Parsed event {event_count + 1}:")
                                    print(f"   - textStartIndex: {event_data.get('textStartIndex')}")
                                    print(f"   - textLength: {event_data.get('textLength')}")
                                    print(f"   - text: {event_data.get('text', '')[:50]}...")
                                    print(f"   - simplifiedText: {event_data.get('simplifiedText', '')[:50]}...")
                                    print(f"   - previousSimplifiedTexts count: {len(event_data.get('previousSimplifiedTexts', []))}")
                                    print()
                                except json.JSONDecodeError as e:
                                    print(f"❌ Failed to parse JSON: {e}")
                                    print(f"   Raw data: {data_content}")
                            else:
                                print(f"ℹ️  Non-JSON data: {data_content}")
                        
                        event_count += 1
                        
        except httpx.ConnectError:
            print("❌ Connection failed. Make sure the server is running on localhost:8000")
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_simplify_sse())
