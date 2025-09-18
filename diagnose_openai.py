#!/usr/bin/env python3
"""
Standalone OpenAI connection diagnostic script.
This will help identify the exact issue with the OpenAI API connection.
"""

import os
import asyncio
import sys
from pathlib import Path

# Add the app directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from app.config import settings
from app.services.llm.open_ai import openai_service

async def diagnose_openai_connection():
    """Run comprehensive OpenAI connection diagnostics."""
    print("🔍 OpenAI Connection Diagnostic Tool")
    print("=" * 50)

    # 1. Check environment variables
    print("\n1. Environment Variables:")
    print(f"   OPENAI_API_KEY exists: {'OPENAI_API_KEY' in os.environ}")
    if 'OPENAI_API_KEY' in os.environ:
        key = os.environ['OPENAI_API_KEY']
        print(f"   API Key length: {len(key)}")
        print(f"   API Key format: {'Valid (starts with sk-)' if key.startswith('sk-') else 'Invalid'}")
        print(f"   API Key preview: {key[:10]}...{key[-4:] if len(key) > 14 else '***'}")

    # 2. Check settings loading
    print("\n2. Settings Configuration:")
    try:
        print(f"   Settings loaded: ✅")
        print(f"   OpenAI API Key configured: {bool(settings.openai_api_key)}")
        if settings.openai_api_key:
            print(f"   API Key length in settings: {len(settings.openai_api_key)}")
            print(f"   API Key format in settings: {'Valid' if settings.openai_api_key.startswith('sk-') else 'Invalid'}")
        print(f"   GPT-4 Turbo Model: {settings.gpt4_turbo_model}")
        print(f"   GPT-4o Model: {settings.gpt4o_model}")
    except Exception as e:
        print(f"   Settings loading failed: ❌ {e}")
        return

    # 3. Check OpenAI service initialization
    print("\n3. OpenAI Service Initialization:")
    try:
        # Try to access the client
        client_exists = hasattr(openai_service, 'client') and openai_service.client is not None
        print(f"   OpenAI client initialized: {'✅' if client_exists else '❌'}")

        if client_exists:
            print(f"   Client type: {type(openai_service.client).__name__}")
    except Exception as e:
        print(f"   OpenAI service initialization failed: ❌ {e}")
        return

    # 4. Test basic connection
    print("\n4. Testing OpenAI API Connection:")
    try:
        print("   Attempting connection test...")
        is_connected = await openai_service.test_connection()
        print(f"   Connection test result: {'✅ SUCCESS' if is_connected else '❌ FAILED'}")
    except Exception as e:
        print(f"   Connection test failed: ❌ {e}")
        print(f"   Error type: {type(e).__name__}")

        # Additional error details
        if hasattr(e, 'response'):
            print(f"   HTTP Status Code: {getattr(e.response, 'status_code', 'N/A')}")
        if hasattr(e, 'request'):
            print(f"   Request URL: {getattr(e.request, 'url', 'N/A')}")

    # 5. Test a simple API call
    print("\n5. Testing Simple API Call:")
    try:
        print("   Making a simple chat completion request...")
        response = await openai_service.client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Say hello"}],
            max_tokens=5
        )
        print("   ✅ Simple API call successful!")
        print(f"   Response ID: {response.id}")
        print(f"   Model used: {response.model}")
    except Exception as e:
        print(f"   ❌ Simple API call failed: {e}")
        print(f"   Error type: {type(e).__name__}")

        # Check for specific error types
        if "authentication" in str(e).lower():
            print("   🚨 AUTHENTICATION ERROR: Check your API key")
        elif "quota" in str(e).lower():
            print("   🚨 QUOTA ERROR: Check your OpenAI billing/credits")
        elif "connection" in str(e).lower():
            print("   🚨 CONNECTION ERROR: Check your internet connection")
        elif "timeout" in str(e).lower():
            print("   🚨 TIMEOUT ERROR: API request took too long")

    # 6. Recommendations
    print("\n6. Recommendations:")
    if not settings.openai_api_key:
        print("   ❌ No API key found. Set OPENAI_API_KEY environment variable.")
    elif not settings.openai_api_key.startswith('sk-'):
        print("   ❌ Invalid API key format. OpenAI keys should start with 'sk-'")
    else:
        print("   ✅ API key format looks correct")
        print("   💡 If connection still fails, check:")
        print("      - Your OpenAI account has available credits")
        print("      - The API key has necessary permissions")
        print("      - Your network allows HTTPS connections to api.openai.com")

if __name__ == "__main__":
    asyncio.run(diagnose_openai_connection())
