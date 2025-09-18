#!/usr/bin/env python3
"""Example script demonstrating the complete workflow of the Caten API."""

import asyncio
import aiohttp
import json


async def complete_workflow_example():
    """Demonstrate the complete workflow from text analysis to getting more meanings."""
    
    base_url = "http://localhost:8000"
    
    # Sample text for analysis
    text = """
    The ubiquitous nature of smartphones has fundamentally transformed contemporary society, 
    creating an unprecedented paradigm where instantaneous communication transcends geographical 
    boundaries and facilitates the proliferation of information at an exponential rate.
    """
    
    async with aiohttp.ClientSession() as session:
        
        # Step 1: Extract important words
        print("Step 1: Extracting important words...")
        print(f"Text: {text.strip()}")
        
        payload = {"text": text.strip()}
        async with session.post(f"{base_url}/api/v1/important-words-from-text", json=payload) as response:
            if response.status != 200:
                print(f"Error in step 1: {await response.text()}")
                return
            
            words_result = await response.json()
            print(f"\nFound {len(words_result['important_words_location'])} important words:")
            
            words_with_text = []
            for i, location in enumerate(words_result['important_words_location']):
                word = text[location['index']:location['index'] + location['length']]
                words_with_text.append((word, location))
                print(f"  {i+1}. '{word}' at position {location['index']}")
        
        # Step 2: Get explanations for the first few words (streaming)
        print(f"\nStep 2: Getting explanations for first 3 words (streaming)...")
        
        selected_locations = words_result['important_words_location'][:3]
        explanation_payload = {
            "text": text.strip(),
            "important_words_location": selected_locations
        }
        
        explanations = []
        async with session.post(f"{base_url}/api/v1/words-explanation", json=explanation_payload) as response:
            if response.status != 200:
                print(f"Error in step 2: {await response.text()}")
                return
            
            print("Receiving explanations via streaming...")
            async for line in response.content:
                line = line.decode('utf-8').strip()
                if line.startswith('data: '):
                    data = line[6:]  # Remove 'data: ' prefix
                    if data == '[DONE]':
                        print("Streaming completed.")
                        break
                    
                    try:
                        explanation_data = json.loads(data)
                        if 'words_info' in explanation_data:
                            # Print new words that were added
                            current_count = len(explanation_data['words_info'])
                            if current_count > len(explanations):
                                new_word_info = explanation_data['words_info'][-1]
                                explanations.append(new_word_info)
                                print(f"\n  Word: {new_word_info['word']}")
                                print(f"  Meaning: {new_word_info['meaning']}")
                                print(f"  Examples:")
                                for example in new_word_info['examples']:
                                    print(f"    - {example}")
                    
                    except json.JSONDecodeError as e:
                        print(f"Failed to parse streaming data: {data}")
        
        # Step 3: Get more examples for the first word
        if explanations:
            print(f"\nStep 3: Getting more examples for '{explanations[0]['word']}'...")
            
            more_payload = {
                "word": explanations[0]['word'],
                "meaning": explanations[0]['meaning'],
                "examples": explanations[0]['examples']
            }
            
            async with session.post(f"{base_url}/api/v1/get-more-explanations", json=more_payload) as response:
                if response.status != 200:
                    print(f"Error in step 3: {await response.text()}")
                    return
                
                more_result = await response.json()
                print(f"\nWord: {more_result['word']}")
                print(f"Meaning: {more_result['meaning']}")
                print(f"All examples ({len(more_result['examples'])}):")
                for i, example in enumerate(more_result['examples'], 1):
                    marker = "NEW" if i > 2 else "ORIGINAL"
                    print(f"  {i}. [{marker}] {example}")
        
        print(f"\n=== Workflow Complete ===")
        print(f"✓ Analyzed text with {len(text.split())} words")
        print(f"✓ Identified {len(words_result['important_words_location'])} important words")
        print(f"✓ Got explanations for {len(explanations)} words via streaming")
        print(f"✓ Generated additional examples for 1 word")


async def image_to_text_workflow():
    """Demonstrate image to text workflow (requires an actual image file)."""
    
    base_url = "http://localhost:8000"
    
    # Note: You need to have an actual image file for this to work
    # image_path = "sample_image.jpg"  # Replace with actual image path
    
    print("Image to Text Workflow:")
    print("Note: This requires an actual image file. Update the image_path variable.")
    print("Example usage:")
    print("""
    async with aiohttp.ClientSession() as session:
        with open(image_path, 'rb') as f:
            data = aiohttp.FormData()
            data.add_field('file', f, filename='sample.jpg')
            
            async with session.post(f"{base_url}/api/v1/image-to-text", data=data) as response:
                if response.status == 200:
                    result = await response.json()
                    print(f"Extracted text: {result['text']}")
                    
                    # Now you can use this text with the word analysis workflow
                    # ... continue with important words extraction
    """)


if __name__ == "__main__":
    print("=== Caten API Complete Workflow Example ===\n")
    
    # Run the complete text analysis workflow
    asyncio.run(complete_workflow_example())
    
    print(f"\n" + "="*50 + "\n")
    
    # Show image workflow example
    asyncio.run(image_to_text_workflow())
