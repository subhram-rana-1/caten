#!/usr/bin/env python3
"""Example client for testing the Caten API."""

import asyncio
import aiohttp
import json
from pathlib import Path


class CatenClient:
    """Client for interacting with the Caten API."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def health_check(self):
        """Check API health."""
        async with self.session.get(f"{self.base_url}/health") as response:
            return await response.json()
    
    async def image_to_text(self, image_path: str):
        """Extract text from image."""
        with open(image_path, 'rb') as f:
            data = aiohttp.FormData()
            data.add_field('file', f, filename=Path(image_path).name)
            
            async with self.session.post(f"{self.base_url}/api/v1/image-to-text", data=data) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error = await response.json()
                    print(f"Error: {error}")
                    return None
    
    async def get_important_words(self, text: str):
        """Get important words from text."""
        payload = {"text": text}
        async with self.session.post(f"{self.base_url}/api/v1/important-words-from-text", json=payload) as response:
            if response.status == 200:
                return await response.json()
            else:
                error = await response.json()
                print(f"Error: {error}")
                return None
    
    async def get_words_explanation_stream(self, text: str, important_words_location: list):
        """Stream word explanations."""
        payload = {
            "text": text,
            "important_words_location": important_words_location
        }
        
        async with self.session.post(f"{self.base_url}/api/v1/words-explanation", json=payload) as response:
            if response.status == 200:
                async for line in response.content:
                    line = line.decode('utf-8').strip()
                    if line.startswith('data: '):
                        data = line[6:]  # Remove 'data: ' prefix
                        if data == '[DONE]':
                            break
                        try:
                            yield json.loads(data)
                        except json.JSONDecodeError:
                            print(f"Failed to parse: {data}")
            else:
                error = await response.json()
                print(f"Error: {error}")
    
    async def get_more_explanations(self, word: str, meaning: str, examples: list):
        """Get more explanations for a word."""
        payload = {
            "word": word,
            "meaning": meaning,
            "examples": examples
        }
        
        async with self.session.post(f"{self.base_url}/api/v1/get-more-explanations", json=payload) as response:
            if response.status == 200:
                return await response.json()
            else:
                error = await response.json()
                print(f"Error: {error}")
                return None


async def main():
    """Example usage of the Caten API client."""
    async with CatenClient() as client:
        # Test health check
        print("=== Health Check ===")
        health = await client.health_check()
        print(f"Health: {health}")
        
        # Test important words extraction
        print("\n=== Important Words Extraction ===")
        sample_text = """
        The rapid advancement of artificial intelligence has revolutionized numerous industries, 
        creating unprecedented opportunities while simultaneously raising profound ethical questions 
        about the future of human employment and societal structures.
        """
        
        words_result = await client.get_important_words(sample_text.strip())
        if words_result:
            print(f"Found {len(words_result['important_words_location'])} important words:")
            for i, location in enumerate(words_result['important_words_location']):
                word = sample_text[location['index']:location['index'] + location['length']]
                print(f"  {i+1}. '{word}' at position {location['index']}")
        
        # Test word explanations streaming
        if words_result:
            print("\n=== Word Explanations (Streaming) ===")
            async for explanation in client.get_words_explanation_stream(
                words_result['text'], 
                words_result['important_words_location'][:3]  # Limit to first 3 words
            ):
                if 'words_info' in explanation:
                    for word_info in explanation['words_info']:
                        print(f"\nWord: {word_info['word']}")
                        print(f"Meaning: {word_info['meaning']}")
                        print(f"Examples:")
                        for example in word_info['examples']:
                            print(f"  - {example}")
        
        # Test more explanations
        if words_result and words_result['important_words_location']:
            print("\n=== More Explanations ===")
            first_location = words_result['important_words_location'][0]
            first_word = sample_text[first_location['index']:first_location['index'] + first_location['length']]
            
            more_result = await client.get_more_explanations(
                word=first_word,
                meaning="having great speed or happening quickly",
                examples=[
                    "The car was moving at a rapid pace.",
                    "She made rapid progress in her studies."
                ]
            )
            
            if more_result:
                print(f"Word: {more_result['word']}")
                print(f"All examples ({len(more_result['examples'])}):")
                for i, example in enumerate(more_result['examples'], 1):
                    print(f"  {i}. {example}")


if __name__ == "__main__":
    asyncio.run(main())
