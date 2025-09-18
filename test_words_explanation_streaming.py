#!/usr/bin/env python3
"""Test script to verify words explanation streaming behavior."""

import asyncio
import json
import httpx
import sys

async def test_words_explanation_streaming():
    """Test the words explanation API to ensure individual word responses."""

    # Test data with 3 words
    test_request = {
        "text": "The ephemeral beauty of the sunset was truly magnificent and extraordinary.",
        "important_words_location": [
            {"word": "ephemeral", "index": 4, "length": 9},
            {"word": "magnificent", "index": 53, "length": 11},
            {"word": "extraordinary", "index": 69, "length": 13}
        ]
    }

    url = "http://localhost:8000/api/v1/words-explanation"

    print("Testing words explanation streaming...")
    print(f"Test text: {test_request['text']}")
    print(f"Words to explain: {[word['word'] for word in test_request['important_words_location']]}")
    print("-" * 80)

    received_words = []
    event_count = 0

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream(
                "POST",
                url,
                json=test_request,
                headers={"Accept": "text/event-stream"}
            ) as response:

                if response.status_code != 200:
                    print(f"Error: HTTP {response.status_code}")
                    print(f"Response: {await response.atext()}")
                    return False

                print("Streaming response:")

                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        event_count += 1
                        data = line[6:]  # Remove "data: " prefix

                        if data == "[DONE]":
                            print(f"\n{event_count}. [DONE] - Stream completed")
                            break

                        try:
                            event_data = json.loads(data)

                            if "error_code" in event_data:
                                print(f"\n{event_count}. ERROR: {event_data}")
                                return False

                            if "word_info" in event_data:
                                word_info = event_data["word_info"]
                                word = word_info["word"]
                                meaning = word_info["meaning"]
                                examples = word_info["examples"]

                                print(f"\n{event_count}. Word: {word}")
                                print(f"   Meaning: {meaning}")
                                print(f"   Examples: {examples}")

                                received_words.append(word)

                        except json.JSONDecodeError as e:
                            print(f"\n{event_count}. JSON decode error: {e}")
                            print(f"   Raw data: {data}")
                            return False

    except Exception as e:
        print(f"Connection error: {e}")
        return False

    # Verify results
    print("\n" + "=" * 80)
    print("TEST RESULTS:")
    print(f"Expected words: {[word['word'] for word in test_request['important_words_location']]}")
    print(f"Received words: {received_words}")
    print(f"Total events received: {event_count}")

    expected_words = [word['word'] for word in test_request['important_words_location']]

    # Check if we received each word exactly once
    success = True
    for expected_word in expected_words:
        count = received_words.count(expected_word)
        if count == 1:
            print(f"✓ {expected_word}: received exactly once")
        else:
            print(f"✗ {expected_word}: received {count} times (expected 1)")
            success = False

    # Check for any unexpected words
    for word in received_words:
        if word not in expected_words:
            print(f"✗ Unexpected word received: {word}")
            success = False

    if success:
        print("\n🎉 SUCCESS: All words received exactly once!")
        print("✓ No cumulative behavior detected")
        print("✓ Streaming works as expected")
    else:
        print("\n❌ FAILURE: Cumulative behavior or other issues detected")

    return success

async def test_server_health():
    """Check if the server is running."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get("http://localhost:8000/health")
            return response.status_code == 200
    except:
        return False

async def main():
    """Main test function."""
    print("Words Explanation Streaming Test")
    print("=" * 80)

    # Check server health first
    print("Checking server health...")
    if not await test_server_health():
        print("❌ Server is not running at http://localhost:8000")
        print("Please start the server with: python -m app.main")
        sys.exit(1)

    print("✓ Server is running")
    print()

    # Run the streaming test
    success = await test_words_explanation_streaming()

    if success:
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
