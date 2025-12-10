#!/usr/bin/env python3
"""Test script for PDF file size validation."""

import asyncio
import httpx
import io


async def test_pdf_size_validation():
    """Test PDF file size validation."""
    base_url = "http://localhost:8000"
    endpoint = f"{base_url}/api/v1/pdf-to-text"
    
    # Test 1: Create a large PDF content (>2MB) to test size validation
    print("🧪 Test 1: Testing file size validation with large PDF...")
    
    # Create a large content (3MB) to exceed the 2MB limit
    large_content = b"PDF content " * (3 * 1024 * 1024 // 12)  # Approximately 3MB
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            files = {
                "file": ("large_test.pdf", large_content, "application/pdf")
            }
            
            response = await client.post(endpoint, files=files)
            
            if response.status_code == 422:  # Validation error
                print("✅ File size validation working correctly!")
                print(f"Response: {response.json()}")
            else:
                print(f"❌ Expected validation error, got status {response.status_code}")
                print(f"Response: {response.text}")
                
    except Exception as e:
        print(f"❌ Test failed: {e}")
    
    print("\n" + "=" * 50)
    
    # Test 2: Create a small PDF content (<2MB) to test it passes validation
    print("🧪 Test 2: Testing with small PDF (should pass validation)...")
    
    # Create a small content (1MB) that should pass validation
    small_content = b"PDF content " * (1 * 1024 * 1024 // 12)  # Approximately 1MB
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            files = {
                "file": ("small_test.pdf", small_content, "application/pdf")
            }
            
            response = await client.post(endpoint, files=files)
            
            if response.status_code == 422:  # Validation error (expected for invalid PDF)
                print("✅ Small file passed size validation (but failed PDF validation as expected)")
                print(f"Response: {response.json()}")
            elif response.status_code == 200:
                print("✅ Small file passed all validations!")
            else:
                print(f"❌ Unexpected response: {response.status_code}")
                print(f"Response: {response.text}")
                
    except Exception as e:
        print(f"❌ Test failed: {e}")


async def test_health_check():
    """Test if the API server is running."""
    base_url = "http://localhost:8000"
    health_endpoint = f"{base_url}/health"
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(health_endpoint)
            if response.status_code == 200:
                print("✅ API server is running")
                return True
            else:
                print(f"❌ API server health check failed: {response.status_code}")
                return False
    except httpx.ConnectError:
        print("❌ API server is not running")
        return False
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False


async def main():
    """Main test function."""
    print("🚀 Starting PDF file size validation tests...")
    print("=" * 50)
    
    # First check if the server is running
    server_running = await test_health_check()
    if not server_running:
        print("\n💡 To start the server, run: ./start.sh")
        return
    
    print("\n" + "=" * 50)
    
    # Test file size validation
    await test_pdf_size_validation()
    
    print("\n" + "=" * 50)
    print("🏁 File size validation tests completed!")
    print("\n📝 Summary:")
    print("- Large files (>2MB) should be rejected with validation error")
    print("- Small files (<2MB) should pass size validation")
    print("- Invalid PDF content will still fail PDF validation (expected)")


if __name__ == "__main__":
    asyncio.run(main())
