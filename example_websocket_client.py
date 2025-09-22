#!/usr/bin/env python3
"""
Example WebSocket client for testing the /words-explanation-v2 endpoint.
This demonstrates how to connect to the WebSocket and receive streaming word explanations.
"""

import asyncio
import json
import websockets
from typing import Dict, Any


async def test_websocket_words_explanation():
    """Test the WebSocket words explanation endpoint."""
    
    # WebSocket URL
    websocket_url = "ws://localhost:8000/api/v1/words-explanation-v2"
    
    # Sample request data (same format as the REST API)
    request_data = {
        "text": "The serendipitous discovery of the ancient manuscript in the dusty library was truly fortuitous. The librarian's meticulous examination revealed intricate calligraphy that had been preserved for centuries.",
        "important_words_location": [
            {"word": "serendipitous", "index": 4, "length": 13},
            {"word": "manuscript", "index": 35, "length": 10},
            {"word": "fortuitous", "index": 95, "length": 10},
            {"word": "meticulous", "index": 120, "length": 10},
            {"word": "calligraphy", "index": 150, "length": 11}
        ]
    }
    
    try:
        print("Connecting to WebSocket...")
        async with websockets.connect(websocket_url) as websocket:
            print("Connected! Sending request...")
            
            # Send the request data
            await websocket.send(json.dumps(request_data))
            print("Request sent. Waiting for responses...\n")
            
            # Receive and process messages
            message_count = 0
            async for message in websocket:
                try:
                    data = json.loads(message)
                    
                    # Check if it's a completion message
                    if "status" in data and data["status"] == "completed":
                        print(f"✅ {data['message']}")
                        break
                    
                    # Check if it's an error message
                    if "error_code" in data:
                        print(f"❌ Error: {data['error_code']} - {data['error_message']}")
                        break
                    
                    # Process word explanation
                    if "word_info" in data:
                        word_info = data["word_info"]
                        message_count += 1
                        
                        print(f"📝 Word {message_count}: {word_info['word']}")
                        print(f"   Meaning: {word_info['meaning']}")
                        print(f"   Examples:")
                        for i, example in enumerate(word_info['examples'], 1):
                            print(f"     {i}. {example}")
                        print()
                
                except json.JSONDecodeError as e:
                    print(f"❌ Failed to parse message: {e}")
                    print(f"Raw message: {message}")
                except Exception as e:
                    print(f"❌ Error processing message: {e}")
                    print(f"Raw message: {message}")
    
    except websockets.exceptions.ConnectionClosed as e:
        print(f"❌ WebSocket connection closed: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")


async def test_websocket_with_invalid_data():
    """Test the WebSocket with invalid data to see error handling."""
    
    websocket_url = "ws://localhost:8000/api/v1/words-explanation-v2"
    
    # Invalid request data
    invalid_request = {
        "text": "",  # Empty text should cause validation error
        "important_words_location": []
    }
    
    try:
        print("\n" + "="*50)
        print("Testing with invalid data...")
        print("="*50)
        
        async with websockets.connect(websocket_url) as websocket:
            print("Connected! Sending invalid request...")
            
            await websocket.send(json.dumps(invalid_request))
            print("Invalid request sent. Waiting for error response...\n")
            
            async for message in websocket:
                try:
                    data = json.loads(message)
                    
                    if "error_code" in data:
                        print(f"❌ Expected error received: {data['error_code']} - {data['error_message']}")
                        break
                    else:
                        print(f"Unexpected message: {data}")
                
                except json.JSONDecodeError as e:
                    print(f"❌ Failed to parse message: {e}")
                    print(f"Raw message: {message}")
                    break
    
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    print("WebSocket Words Explanation Test Client")
    print("="*50)
    
    # Run the test
    asyncio.run(test_websocket_words_explanation())
    
    # Test error handling
    asyncio.run(test_websocket_with_invalid_data())
