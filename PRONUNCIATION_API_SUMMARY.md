# 🎵 Word Pronunciation API - Quick Start

## What's New?

A brand new V2 API endpoint that generates pronunciation audio for any word using OpenAI's Text-to-Speech technology with a **sweet-toned American female voice** (Nova).

## Quick Test

### Option 1: HTML Test Page (Easiest)

1. Start the server:
   ```bash
   python app/main.py
   ```

2. Open in browser:
   ```
   test_pronunciation_api.html
   ```

3. Enter a word and click "Generate Pronunciation" 🎵

### Option 2: Python Script

```bash
# Single word
python test_pronunciation_client.py hello

# Multiple words with specific voice
python test_pronunciation_client.py hello world beautiful --voice shimmer

# Get help
python test_pronunciation_client.py --help
```

### Option 3: cURL

```bash
curl -X POST http://localhost:8000/api/v2/pronunciation \
  -H "Content-Type: application/json" \
  -d '{"word": "hello", "voice": "nova"}' \
  --output hello.mp3

# Play the audio
mpv hello.mp3
```

## API Endpoint

```
POST /api/v2/pronunciation
```

### Request Body

```json
{
  "word": "pronunciation",
  "voice": "nova"  // optional, default is "nova"
}
```

### Response

Returns MP3 audio file that can be played immediately or saved.

## Available Voices

- **nova** (default) - Sweet-toned American female ⭐ Recommended
- **shimmer** - Soft American female
- **alloy** - Neutral voice
- **echo** - Male voice
- **fable** - British male
- **onyx** - Deep male

## Files Added

1. **Backend Implementation:**
   - `app/services/llm/open_ai.py` - Added `generate_pronunciation_audio()` method
   - `app/routes/v2_api.py` - Added `/api/v2/pronunciation` endpoint

2. **Testing Tools:**
   - `test_pronunciation_api.html` - Interactive HTML test page
   - `test_pronunciation_client.py` - Command-line Python client

3. **Documentation:**
   - `PRONUNCIATION_API.md` - Complete API documentation
   - `PRONUNCIATION_API_SUMMARY.md` - This quick start guide

## Code Changes Summary

### 1. OpenAI Service (`app/services/llm/open_ai.py`)

Added new method to generate TTS audio:

```python
async def generate_pronunciation_audio(self, word: str, voice: str = "nova") -> bytes:
    """Generate pronunciation audio for a word using OpenAI TTS."""
    response = await self.client.audio.speech.create(
        model="tts-1",
        voice=voice,
        input=word,
        response_format="mp3"
    )
    return response.content
```

### 2. V2 API Endpoint (`app/routes/v2_api.py`)

Added new POST endpoint:

```python
@router.post("/pronunciation")
async def get_pronunciation(request: Request, body: PronunciationRequest):
    """Generate pronunciation audio for a word."""
    audio_bytes = await openai_service.generate_pronunciation_audio(
        body.word,
        body.voice or "nova"
    )
    return Response(
        content=audio_bytes,
        media_type="audio/mpeg",
        headers={
            "Content-Disposition": f'inline; filename="{body.word}_pronunciation.mp3"',
            "Cache-Control": "public, max-age=86400"
        }
    )
```

## Integration Example

### JavaScript/React

```javascript
async function playWord(word) {
  const response = await fetch('http://localhost:8000/api/v2/pronunciation', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ word, voice: 'nova' })
  });
  
  const audioBlob = await response.blob();
  const audio = new Audio(URL.createObjectURL(audioBlob));
  audio.play();
}
```

### Python

```python
import requests

response = requests.post(
    'http://localhost:8000/api/v2/pronunciation',
    json={'word': 'hello', 'voice': 'nova'}
)

with open('hello.mp3', 'wb') as f:
    f.write(response.content)
```

## Features

✅ High-quality OpenAI TTS  
✅ 6 different voices (including sweet female American)  
✅ Fast response (~1-2 seconds)  
✅ MP3 format (universal compatibility)  
✅ Rate limiting (60 req/min)  
✅ 24-hour cache headers  
✅ CORS enabled  
✅ Error handling  
✅ Logging and monitoring  

## Testing Checklist

- [ ] Start the server: `python app/main.py`
- [ ] Test with HTML page: Open `test_pronunciation_api.html`
- [ ] Test with Python client: `python test_pronunciation_client.py hello`
- [ ] Test with cURL: Save audio file and play it
- [ ] Try different voices
- [ ] Check API docs: http://localhost:8000/docs

## Next Steps

1. **Start the Server:**
   ```bash
   python app/main.py
   ```

2. **Test the Endpoint:**
   - Open `test_pronunciation_api.html` in browser
   - Try different words and voices
   - Download audio files

3. **Integrate into Your App:**
   - See `PRONUNCIATION_API.md` for detailed integration examples
   - Check React/Vue/JavaScript examples
   - Review best practices and caching strategies

## Troubleshooting

**Server won't start?**
- Check if OpenAI API key is set in environment variables
- Ensure all dependencies are installed: `pip install -r requirements.txt`

**Audio not playing?**
- Check browser console for errors
- Verify CORS is working (should see successful OPTIONS request)
- Ensure server is running on port 8000

**Rate limit errors?**
- Default is 60 requests/minute
- Wait a minute or increase limit in config
- Implement client-side caching

## API Documentation

For complete API documentation, see `PRONUNCIATION_API.md`.

For testing the existing words-explanation API with audio, see `test_audio_pronunciation.html`.

---

**Enjoy generating pronunciations! 🎉**

