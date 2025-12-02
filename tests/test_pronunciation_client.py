#!/usr/bin/env python3
"""
Test client for the V2 pronunciation API.
This script generates pronunciation audio for words using OpenAI TTS.
"""

import requests
import argparse
import sys
from pathlib import Path


def generate_pronunciation(word: str, voice: str = "nova", base_url: str = "http://localhost:8000"):
    """
    Generate pronunciation audio for a word.
    
    Args:
        word: The word to generate pronunciation for
        voice: Voice to use (alloy, echo, fable, onyx, nova, shimmer)
        base_url: Base URL of the API server
    
    Returns:
        bytes: Audio data
    """
    url = f"{base_url}/api/v2/pronunciation"
    
    payload = {
        "word": word,
        "voice": voice
    }
    
    print(f"🎵 Generating pronunciation for '{word}' with '{voice}' voice...")
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        
        print(f"✅ Successfully generated pronunciation audio")
        print(f"   Audio size: {len(response.content)} bytes")
        print(f"   Content type: {response.headers.get('Content-Type')}")
        
        return response.content
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Error: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"   Status code: {e.response.status_code}")
            print(f"   Response: {e.response.text}")
        sys.exit(1)


def save_audio(audio_data: bytes, word: str, output_dir: str = "."):
    """
    Save audio data to a file.
    
    Args:
        audio_data: Audio data bytes
        word: The word (used in filename)
        output_dir: Directory to save the file
    """
    output_path = Path(output_dir) / f"{word}_pronunciation.mp3"
    
    with open(output_path, 'wb') as f:
        f.write(audio_data)
    
    print(f"💾 Saved audio to: {output_path}")
    print(f"   You can play it with: mpv {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate pronunciation audio for words using OpenAI TTS",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate pronunciation for a single word with default voice (nova)
  python test_pronunciation_client.py hello
  
  # Generate with a specific voice
  python test_pronunciation_client.py beautiful --voice shimmer
  
  # Generate for multiple words
  python test_pronunciation_client.py serendipity extraordinary philosophical
  
  # Save to a specific directory
  python test_pronunciation_client.py hello --output ./audio_files
  
Available voices:
  - nova     (Sweet female - American) [Default]
  - shimmer  (Soft female - American)
  - alloy    (Neutral)
  - echo     (Male)
  - fable    (British male)
  - onyx     (Deep male)
        """
    )
    
    parser.add_argument(
        'words',
        nargs='+',
        help='Word(s) to generate pronunciation for'
    )
    
    parser.add_argument(
        '--voice',
        default='nova',
        choices=['alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer'],
        help='Voice to use (default: nova - sweet female American)'
    )
    
    parser.add_argument(
        '--output',
        default='.',
        help='Output directory for audio files (default: current directory)'
    )
    
    parser.add_argument(
        '--base-url',
        default='http://localhost:8000',
        help='Base URL of the API server (default: http://localhost:8000)'
    )
    
    args = parser.parse_args()
    
    # Create output directory if it doesn't exist
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"🚀 Starting pronunciation generation")
    print(f"   Server: {args.base_url}")
    print(f"   Voice: {args.voice}")
    print(f"   Output directory: {output_dir.absolute()}")
    print()
    
    # Generate pronunciation for each word
    for i, word in enumerate(args.words, 1):
        print(f"[{i}/{len(args.words)}] Processing '{word}'...")
        audio_data = generate_pronunciation(word, args.voice, args.base_url)
        save_audio(audio_data, word, output_dir)
        print()
    
    print(f"✨ Done! Generated pronunciation for {len(args.words)} word(s)")


if __name__ == "__main__":
    main()

