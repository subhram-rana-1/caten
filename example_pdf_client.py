#!/usr/bin/env python3
"""Example client for the PDF-to-text API endpoint."""

import asyncio
import httpx
import json
from pathlib import Path


class CatenPdfClient:
    """Client for interacting with the Caten PDF-to-text API."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.pdf_endpoint = f"{base_url}/api/v1/pdf-to-text"
        self.important_words_endpoint = f"{base_url}/api/v1/important-words-from-text"
        self.words_explanation_endpoint = f"{base_url}/api/v1/words-explanation"
    
    async def extract_text_from_pdf(self, pdf_file_path: str) -> dict:
        """Extract text from a PDF file."""
        try:
            pdf_path = Path(pdf_file_path)
            if not pdf_path.exists():
                raise FileNotFoundError(f"PDF file not found: {pdf_file_path}")
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                with open(pdf_path, "rb") as f:
                    files = {
                        "file": (pdf_path.name, f.read(), "application/pdf")
                    }
                    
                    response = await client.post(self.pdf_endpoint, files=files)
                    response.raise_for_status()
                    
                    return response.json()
                    
        except httpx.HTTPStatusError as e:
            print(f"HTTP error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            print(f"Error extracting text from PDF: {e}")
            raise
    
    async def get_important_words(self, text: str) -> dict:
        """Get important words from extracted text."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                payload = {"text": text}
                response = await client.post(
                    self.important_words_endpoint,
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                response.raise_for_status()
                return response.json()
                
        except httpx.HTTPStatusError as e:
            print(f"HTTP error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            print(f"Error getting important words: {e}")
            raise
    
    async def get_word_explanations(self, text: str, important_words: list) -> dict:
        """Get word explanations for important words."""
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                payload = {
                    "text": text,
                    "important_words_location": important_words
                }
                response = await client.post(
                    self.words_explanation_endpoint,
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                response.raise_for_status()
                return response.json()
                
        except httpx.HTTPStatusError as e:
            print(f"HTTP error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            print(f"Error getting word explanations: {e}")
            raise


async def complete_pdf_workflow_example():
    """Complete workflow example: PDF -> Text -> Important Words -> Explanations."""
    client = CatenPdfClient()
    
    # Example PDF file path (you would replace this with your actual PDF)
    pdf_file_path = "sample.pdf"  # Replace with actual PDF file
    
    try:
        print("🚀 Starting complete PDF processing workflow...")
        print("=" * 60)
        
        # Step 1: Extract text from PDF
        print("📄 Step 1: Extracting text from PDF...")
        pdf_result = await client.extract_text_from_pdf(pdf_file_path)
        extracted_text = pdf_result["text"]
        
        print(f"✅ Successfully extracted text ({len(extracted_text)} characters)")
        print(f"📝 Text preview: {extracted_text[:200]}...")
        print()
        
        # Step 2: Get important words
        print("🔍 Step 2: Identifying important words...")
        important_words_result = await client.get_important_words(extracted_text)
        important_words = important_words_result["important_words_location"]
        
        print(f"✅ Found {len(important_words)} important words:")
        for word_info in important_words:
            print(f"   - {word_info['word']} (at position {word_info['index']})")
        print()
        
        # Step 3: Get word explanations
        print("📚 Step 3: Getting word explanations...")
        explanations_result = await client.get_word_explanations(extracted_text, important_words)
        words_info = explanations_result["words_info"]
        
        print(f"✅ Generated explanations for {len(words_info)} words:")
        for word_info in words_info:
            print(f"\n📖 Word: {word_info['word']}")
            print(f"   Meaning: {word_info['meaning']}")
            print(f"   Examples:")
            for i, example in enumerate(word_info['examples'], 1):
                print(f"     {i}. {example}")
        
        print("\n" + "=" * 60)
        print("🎉 Complete workflow finished successfully!")
        
    except FileNotFoundError:
        print(f"❌ PDF file not found: {pdf_file_path}")
        print("💡 Please provide a valid PDF file path")
    except Exception as e:
        print(f"❌ Workflow failed: {e}")


async def simple_pdf_test():
    """Simple test of just the PDF-to-text functionality."""
    client = CatenPdfClient()
    
    # Create a simple test PDF (you would replace this with a real PDF file)
    print("🧪 Testing PDF-to-text API with sample content...")
    
    try:
        # This is just a demonstration - in practice you'd use a real PDF file
        print("💡 To test with a real PDF, replace 'sample.pdf' with your actual PDF file path")
        print("📄 Example usage:")
        print("   pdf_result = await client.extract_text_from_pdf('your_document.pdf')")
        print("   print(pdf_result['text'])")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")


async def main():
    """Main function to run examples."""
    print("🔧 Caten PDF API Client Examples")
    print("=" * 50)
    
    # Check if server is running
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get("http://localhost:8000/health")
            if response.status_code == 200:
                print("✅ API server is running")
            else:
                print("❌ API server is not responding properly")
                return
    except httpx.ConnectError:
        print("❌ Cannot connect to API server")
        print("💡 Make sure the server is running: ./start.sh")
        return
    
    print("\nChoose an example to run:")
    print("1. Simple PDF-to-text test")
    print("2. Complete workflow (PDF -> Text -> Important Words -> Explanations)")
    
    choice = input("\nEnter your choice (1 or 2): ").strip()
    
    if choice == "1":
        await simple_pdf_test()
    elif choice == "2":
        await complete_pdf_workflow_example()
    else:
        print("❌ Invalid choice. Please run the script again and choose 1 or 2.")


if __name__ == "__main__":
    asyncio.run(main())
