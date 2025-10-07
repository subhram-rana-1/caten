#!/usr/bin/env python3
"""Test script for the PDF-to-text API endpoint."""

import asyncio
import httpx
import os
from pathlib import Path


async def test_pdf_to_text():
    """Test the PDF-to-text API endpoint."""
    base_url = "http://localhost:8000"
    endpoint = f"{base_url}/api/v1/pdf-to-text"
    
    # Create a simple test PDF content (this would normally be a real PDF file)
    # For testing purposes, we'll create a minimal PDF-like file
    test_pdf_content = b"""%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj

2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj

3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
/Contents 4 0 R
>>
endobj

4 0 obj
<<
/Length 44
>>
stream
BT
/F1 12 Tf
100 700 Td
(Hello World!) Tj
ET
endstream
endobj

xref
0 5
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000206 00000 n 
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
299
%%EOF"""
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Test with a simple PDF file
            files = {
                "file": ("test.pdf", test_pdf_content, "application/pdf")
            }
            
            print(f"Testing PDF-to-text endpoint: {endpoint}")
            response = await client.post(endpoint, files=files)
            
            print(f"Status Code: {response.status_code}")
            print(f"Response Headers: {dict(response.headers)}")
            
            if response.status_code == 200:
                result = response.json()
                print("✅ PDF-to-text API test successful!")
                print(f"Extracted text length: {len(result.get('text', ''))}")
                print(f"Extracted text preview: {result.get('text', '')[:200]}...")
            else:
                print(f"❌ PDF-to-text API test failed!")
                print(f"Error: {response.text}")
                
    except httpx.ConnectError:
        print("❌ Could not connect to the API server. Make sure it's running on localhost:8000")
    except Exception as e:
        print(f"❌ Test failed with error: {e}")


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
    print("🚀 Starting PDF-to-text API tests...")
    print("=" * 50)
    
    # First check if the server is running
    server_running = await test_health_check()
    if not server_running:
        print("\n💡 To start the server, run: ./start.sh")
        return
    
    print("\n" + "=" * 50)
    
    # Test the PDF endpoint
    await test_pdf_to_text()
    
    print("\n" + "=" * 50)
    print("🏁 Tests completed!")


if __name__ == "__main__":
    asyncio.run(main())
