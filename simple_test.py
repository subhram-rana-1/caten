#!/usr/bin/env python3
"""
Simple OpenAI connection test
"""

import os
import sys
from pathlib import Path

# Add the app directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

print("🔍 Simple OpenAI Test")
print("=" * 30)

try:
    print("1. Loading environment...")
    from app.config import settings
    print(f"   ✅ Settings loaded")
    print(f"   API Key configured: {bool(settings.openai_api_key)}")

    print("\n2. Testing OpenAI service import...")
    from app.services.llm.open_ai import openai_service
    print(f"   ✅ OpenAI service imported")

    print("\n3. Testing client initialization...")
    has_client = hasattr(openai_service, 'client') and openai_service.client is not None
    print(f"   Client exists: {has_client}")

    if has_client:
        print(f"   Client type: {type(openai_service.client).__name__}")
        print("   ✅ OpenAI client properly initialized")
    else:
        print("   ❌ OpenAI client not initialized")

except Exception as e:
    print(f"❌ Error: {e}")
    print(f"Error type: {type(e).__name__}")
    import traceback
    traceback.print_exc()
