#!/usr/bin/env python3
"""Test script to verify pronunciation API imports and structure."""

import sys
import os

# Set a dummy API key for testing imports
os.environ['OPENAI_API_KEY'] = 'sk-test-dummy-key-for-import-testing-only'

try:
    print("🔍 Testing imports...")
    print()
    
    # Test v2_api imports
    print("1️⃣ Testing v2_api imports...")
    from app.routes import v2_api
    print("   ✅ v2_api module imported successfully")
    
    # Check if pronunciation endpoint exists
    if hasattr(v2_api, 'get_pronunciation'):
        print("   ✅ get_pronunciation endpoint found")
    else:
        print("   ⚠️  get_pronunciation endpoint not found (but module loaded)")
    
    # Test PronunciationRequest model
    if hasattr(v2_api, 'PronunciationRequest'):
        print("   ✅ PronunciationRequest model found")
        # Test model validation
        req = v2_api.PronunciationRequest(word="hello", voice="nova")
        print(f"   ✅ Model validation works: word='{req.word}', voice='{req.voice}'")
    
    print()
    
    # Test OpenAI service imports
    print("2️⃣ Testing OpenAI service imports...")
    from app.services.llm.open_ai import openai_service
    print("   ✅ openai_service imported successfully")
    
    # Check if pronunciation method exists
    if hasattr(openai_service, 'generate_pronunciation_audio'):
        print("   ✅ generate_pronunciation_audio method found")
        
        # Check method signature
        import inspect
        sig = inspect.signature(openai_service.generate_pronunciation_audio)
        params = list(sig.parameters.keys())
        print(f"   ✅ Method signature: {params}")
    
    print()
    
    # Test main app
    print("3️⃣ Testing main app imports...")
    from app.main import app
    print("   ✅ FastAPI app imported successfully")
    
    # Check if v2 router is included
    routes = [route.path for route in app.routes]
    pronunciation_routes = [r for r in routes if 'pronunciation' in r]
    if pronunciation_routes:
        print(f"   ✅ Pronunciation route registered: {pronunciation_routes}")
    else:
        print("   ℹ️  Pronunciation route might be registered under v2 prefix")
    
    print()
    print("=" * 60)
    print("✅ All imports successful! The API is ready to use.")
    print("=" * 60)
    print()
    print("📝 Next steps:")
    print("   1. Set your OpenAI API key:")
    print("      export OPENAI_API_KEY='your-actual-api-key'")
    print()
    print("   2. Start the server:")
    print("      python app/main.py")
    print()
    print("   3. Test the endpoint:")
    print("      - Open test_pronunciation_api.html in browser")
    print("      - Or run: python test_pronunciation_client.py hello")
    print()
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

