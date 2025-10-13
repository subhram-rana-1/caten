"""Test client for the voice-to-text API endpoint."""

import asyncio
import httpx
import os
from pathlib import Path


async def test_voice_to_text():
    """Test the voice-to-text API with a sample audio file."""
    
    # API endpoint
    url = "http://localhost:8000/api/v2/voice-to-text"
    
    # For testing, you would need an actual audio file
    # This is just a demonstration of how to use the API
    print("Voice-to-Text API Test")
    print("=" * 50)
    print(f"Endpoint: {url}")
    print()
    
    # Check if there's a sample audio file
    test_audio_files = [
        "test_audio.mp3",
        "sample.wav",
        "recording.webm"
    ]
    
    audio_file_path = None
    for filename in test_audio_files:
        if os.path.exists(filename):
            audio_file_path = filename
            break
    
    if not audio_file_path:
        print("⚠️  No test audio file found!")
        print()
        print("To test this API, please:")
        print("1. Create or download a sample audio file (mp3, wav, webm, etc.)")
        print("2. Save it as 'test_audio.mp3' in the current directory")
        print("3. Run this script again")
        print()
        print("Example using curl:")
        print(f"  curl -X POST {url} \\")
        print('    -F "audio_file=@/path/to/your/audio.mp3"')
        return
    
    print(f"✓ Found audio file: {audio_file_path}")
    print(f"  Size: {os.path.getsize(audio_file_path) / 1024:.2f} KB")
    print()
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Read the audio file
            with open(audio_file_path, "rb") as f:
                files = {
                    "audio_file": (os.path.basename(audio_file_path), f, "audio/mpeg")
                }
                
                print("Sending request to API...")
                response = await client.post(url, files=files)
            
            print(f"Status Code: {response.status_code}")
            print()
            
            if response.status_code == 200:
                result = response.json()
                print("✓ Success!")
                print()
                print("Transcribed Text:")
                print("-" * 50)
                print(result["text"])
                print("-" * 50)
            else:
                print("✗ Error!")
                print(response.json())
    
    except httpx.ConnectError:
        print("✗ Connection Error!")
        print()
        print("Make sure the FastAPI server is running:")
        print("  python -m uvicorn app.main:app --reload")
    
    except Exception as e:
        print(f"✗ Error: {str(e)}")


async def test_api_validation():
    """Test the API validation with invalid inputs."""
    
    url = "http://localhost:8000/api/v2/voice-to-text"
    
    print()
    print("Testing API Validation")
    print("=" * 50)
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Test 1: No file
            print("\n1. Testing with no file...")
            try:
                response = await client.post(url)
                print(f"   Status: {response.status_code}")
                if response.status_code == 422:
                    print("   ✓ Correctly rejected (422 Validation Error)")
            except Exception as e:
                print(f"   Error: {e}")
            
            # Test 2: Invalid file type (if we have a text file)
            print("\n2. Testing with invalid file type...")
            try:
                # Create a temporary text file
                test_file = "test_invalid.txt"
                with open(test_file, "w") as f:
                    f.write("This is not an audio file")
                
                with open(test_file, "rb") as f:
                    files = {"audio_file": (test_file, f, "text/plain")}
                    response = await client.post(url, files=files)
                
                print(f"   Status: {response.status_code}")
                if response.status_code == 400:
                    print("   ✓ Correctly rejected (400 Bad Request)")
                    print(f"   Message: {response.json()['detail']}")
                
                # Clean up
                os.remove(test_file)
            except Exception as e:
                print(f"   Error: {e}")
    
    except httpx.ConnectError:
        print("\n✗ Connection Error! Server not running.")


async def main():
    """Run all tests."""
    await test_voice_to_text()
    await test_api_validation()


if __name__ == "__main__":
    asyncio.run(main())

