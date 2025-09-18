#!/usr/bin/env python3
"""Debug script for testing the Caten API endpoints individually."""

import asyncio
import aiohttp
import json
import sys
from pathlib import Path


async def test_health():
    """Test health endpoint."""
    print("Testing /health endpoint...")
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get("http://localhost:8000/health") as response:
                print(f"Status: {response.status}")
                result = await response.json()
                print(f"Response: {json.dumps(result, indent=2)}")
                return response.status == 200
        except Exception as e:
            print(f"Error: {e}")
            return False


async def test_important_words():
    """Test important words endpoint."""
    print("\nTesting /api/v1/important-words-from-text endpoint...")
    
    test_text = "The sophisticated algorithm demonstrates remarkable efficiency in processing complex datasets."
    
    async with aiohttp.ClientSession() as session:
        try:
            payload = {"text": test_text}
            async with session.post("http://localhost:8000/api/v1/important-words-from-text", json=payload) as response:
                print(f"Status: {response.status}")
                result = await response.json()
                print(f"Response: {json.dumps(result, indent=2)}")
                
                if response.status == 200:
                    print(f"Found {len(result['important_words_location'])} important words:")
                    for i, loc in enumerate(result['important_words_location']):
                        word = test_text[loc['index']:loc['index'] + loc['length']]
                        print(f"  {i+1}. '{word}' at {loc['index']}")
                
                return response.status == 200, result if response.status == 200 else None
        except Exception as e:
            print(f"Error: {e}")
            return False, None


async def test_words_explanation(text, locations):
    """Test words explanation streaming endpoint."""
    print("\nTesting /api/v1/words-explanation endpoint (streaming)...")
    
    async with aiohttp.ClientSession() as session:
        try:
            payload = {
                "text": text,
                "important_words_location": locations[:2]  # Test with first 2 words
            }
            
            async with session.post("http://localhost:8000/api/v1/words-explanation", json=payload) as response:
                print(f"Status: {response.status}")
                print(f"Content-Type: {response.headers.get('content-type')}")
                
                if response.status == 200:
                    print("Streaming response:")
                    async for line in response.content:
                        line = line.decode('utf-8').strip()
                        if line.startswith('data: '):
                            data = line[6:]
                            if data == '[DONE]':
                                print("  [DONE]")
                                break
                            try:
                                parsed = json.loads(data)
                                print(f"  Received: {len(parsed.get('words_info', []))} word(s)")
                                for word_info in parsed.get('words_info', []):
                                    print(f"    - {word_info['word']}: {word_info['meaning'][:50]}...")
                            except json.JSONDecodeError:
                                print(f"  Raw data: {data}")
                
                return response.status == 200
        except Exception as e:
            print(f"Error: {e}")
            return False


async def test_more_explanations():
    """Test more explanations endpoint."""
    print("\nTesting /api/v1/get-more-explanations endpoint...")
    
    async with aiohttp.ClientSession() as session:
        try:
            payload = {
                "word": "sophisticated",
                "meaning": "having great knowledge or experience",
                "examples": [
                    "She has sophisticated taste in art.",
                    "The sophisticated system works perfectly."
                ]
            }
            
            async with session.post("http://localhost:8000/api/v1/get-more-explanations", json=payload) as response:
                print(f"Status: {response.status}")
                result = await response.json()
                print(f"Response: {json.dumps(result, indent=2)}")
                
                if response.status == 200:
                    print(f"Total examples: {len(result['examples'])}")
                    for i, example in enumerate(result['examples'], 1):
                        marker = "NEW" if i > 2 else "ORIG"
                        print(f"  {i}. [{marker}] {example}")
                
                return response.status == 200
        except Exception as e:
            print(f"Error: {e}")
            return False


async def test_image_to_text():
    """Test image to text endpoint."""
    print("\nTesting /api/v1/image-to-text endpoint...")
    print("Note: This test creates a simple test image. For real testing, use an actual image file.")
    
    # Create a simple test image with PIL
    try:
        from PIL import Image, ImageDraw
        import io
        
        # Create a simple image with text
        img = Image.new('RGB', (200, 100), color='white')
        draw = ImageDraw.Draw(img)
        draw.text((10, 40), "Hello World", fill='black')
        
        # Save to bytes
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes.seek(0)
        
        async with aiohttp.ClientSession() as session:
            data = aiohttp.FormData()
            data.add_field('file', img_bytes, filename='test.png', content_type='image/png')
            
            async with session.post("http://localhost:8000/api/v1/image-to-text", data=data) as response:
                print(f"Status: {response.status}")
                result = await response.json()
                print(f"Response: {json.dumps(result, indent=2)}")
                return response.status == 200
                
    except ImportError:
        print("PIL not available for image test. Skipping image to text test.")
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False


async def main():
    """Run all debug tests."""
    print("=== Caten API Debug Tests ===\n")
    
    tests = [
        ("Health Check", test_health()),
        ("Important Words", test_important_words()),
    ]
    
    results = {}
    
    # Run basic tests first
    for test_name, test_coro in tests:
        print(f"Running {test_name}...")
        if test_name == "Important Words":
            success, data = await test_coro
            results[test_name] = success
            if success and data:
                # Run dependent tests
                print(f"Running Words Explanation (depends on Important Words)...")
                results["Words Explanation"] = await test_words_explanation(
                    data['text'], 
                    data['important_words_location']
                )
        else:
            results[test_name] = await test_coro
    
    # Run independent tests
    results["More Explanations"] = await test_more_explanations()
    results["Image to Text"] = await test_image_to_text()
    
    # Summary
    print(f"\n=== Test Results ===")
    for test_name, success in results.items():
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"{test_name}: {status}")
    
    total_tests = len(results)
    passed_tests = sum(1 for success in results.values() if success)
    print(f"\nOverall: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("🎉 All tests passed! API is working correctly.")
    else:
        print("⚠️ Some tests failed. Check the API server and configuration.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
