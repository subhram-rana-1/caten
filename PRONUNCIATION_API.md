# Word Pronunciation API (V2)

## Overview

The Pronunciation API generates high-quality audio pronunciation for any word using OpenAI's Text-to-Speech (TTS) technology. This API is perfect for language learning applications, vocabulary tools, and accessibility features.

## Endpoint

```
POST /api/v2/pronunciation
```

## Features

- 🎵 High-quality audio pronunciation using OpenAI TTS
- 🗣️ Multiple voice options including sweet-toned American female voice
- 🚀 Fast response times with efficient streaming
- 💾 Returns MP3 audio that can be played immediately or downloaded
- 🔒 Rate-limited for fair usage
- 📦 Cacheable responses (24-hour cache)

## Request

### Headers
```
Content-Type: application/json
```

### Body Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `word` | string | Yes | - | The word to generate pronunciation for (1-100 characters) |
| `voice` | string | No | `"nova"` | Voice to use for pronunciation |

### Available Voices

| Voice | Description | Best For |
|-------|-------------|----------|
| `nova` | Sweet-toned American female | **Default** - Perfect for language learning |
| `shimmer` | Soft American female | Alternative female voice |
| `alloy` | Neutral voice | Gender-neutral option |
| `echo` | American male | Male voice option |
| `fable` | British male | British accent |
| `onyx` | Deep American male | Professional/authoritative tone |

### Example Request

```json
{
  "word": "pronunciation",
  "voice": "nova"
}
```

### cURL Example

```bash
curl -X POST http://localhost:8000/api/v2/pronunciation \
  -H "Content-Type: application/json" \
  -d '{"word": "hello", "voice": "nova"}' \
  --output hello_pronunciation.mp3
```

## Response

### Success Response

**Status Code:** `200 OK`

**Content-Type:** `audio/mpeg`

**Headers:**
- `Content-Disposition: inline; filename="{word}_pronunciation.mp3"`
- `Cache-Control: public, max-age=86400`

The response body contains the MP3 audio data that can be:
- Played directly in browsers using `<audio>` element
- Downloaded as a file
- Streamed to audio players

### Error Responses

#### 400 Bad Request
```json
{
  "detail": "Invalid voice. Must be one of: alloy, echo, fable, onyx, nova, shimmer"
}
```

#### 429 Too Many Requests
```json
{
  "error_code": "RATE_LIMIT_001",
  "error_message": "Rate limit exceeded. Maximum 60 requests per minute allowed."
}
```

#### 500 Internal Server Error
```json
{
  "detail": "Failed to generate pronunciation: [error details]"
}
```

## Rate Limiting

- **Limit:** 60 requests per minute per client IP
- **Endpoint Identifier:** `pronunciation`
- Rate limits are enforced using Redis-based tracking

## Usage Examples

### JavaScript/HTML

```javascript
async function playPronunciation(word) {
  const response = await fetch('http://localhost:8000/api/v2/pronunciation', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      word: word,
      voice: 'nova'
    })
  });
  
  const audioBlob = await response.blob();
  const audioUrl = URL.createObjectURL(audioBlob);
  
  const audio = new Audio(audioUrl);
  audio.play();
}

// Usage
playPronunciation('hello');
```

### Python

```python
import requests

def get_pronunciation(word, voice='nova'):
    url = 'http://localhost:8000/api/v2/pronunciation'
    response = requests.post(
        url,
        json={'word': word, 'voice': voice}
    )
    
    # Save to file
    with open(f'{word}_pronunciation.mp3', 'wb') as f:
        f.write(response.content)
    
    return response.content

# Usage
get_pronunciation('hello')
```

### Using the Test Client

We provide a ready-to-use Python test client:

```bash
# Basic usage
python test_pronunciation_client.py hello

# With specific voice
python test_pronunciation_client.py beautiful --voice shimmer

# Multiple words
python test_pronunciation_client.py hello world beautiful

# Save to specific directory
python test_pronunciation_client.py hello --output ./audio_files
```

### Using the Test HTML Page

Open `test_pronunciation_api.html` in your browser to test the API with a user-friendly interface:

1. Enter any word
2. Select a voice
3. Click "Generate Pronunciation"
4. Listen to the audio
5. Download if needed

## Integration Examples

### React Component

```jsx
import React, { useState } from 'react';

function PronunciationButton({ word }) {
  const [loading, setLoading] = useState(false);
  
  const playPronunciation = async () => {
    setLoading(true);
    try {
      const response = await fetch('http://localhost:8000/api/v2/pronunciation', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ word, voice: 'nova' })
      });
      
      const audioBlob = await response.blob();
      const audioUrl = URL.createObjectURL(audioBlob);
      const audio = new Audio(audioUrl);
      await audio.play();
    } catch (error) {
      console.error('Failed to play pronunciation:', error);
    } finally {
      setLoading(false);
    }
  };
  
  return (
    <button onClick={playPronunciation} disabled={loading}>
      {loading ? '⏳' : '🔊'} Play
    </button>
  );
}
```

### Vue.js Component

```vue
<template>
  <button @click="playPronunciation" :disabled="loading">
    {{ loading ? '⏳' : '🔊' }} Play
  </button>
</template>

<script>
export default {
  props: ['word'],
  data() {
    return {
      loading: false
    }
  },
  methods: {
    async playPronunciation() {
      this.loading = true;
      try {
        const response = await fetch('http://localhost:8000/api/v2/pronunciation', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ word: this.word, voice: 'nova' })
        });
        
        const audioBlob = await response.blob();
        const audioUrl = URL.createObjectURL(audioBlob);
        const audio = new Audio(audioUrl);
        await audio.play();
      } catch (error) {
        console.error('Failed to play pronunciation:', error);
      } finally {
        this.loading = false;
      }
    }
  }
}
</script>
```

## Performance Considerations

- **Audio Quality:** Uses OpenAI's `tts-1` model for fast responses
- **File Size:** Typical MP3 files are 5-20 KB per word
- **Response Time:** Usually 500ms - 2s depending on word length
- **Caching:** Responses are cached for 24 hours (recommended to implement client-side caching)

## Best Practices

1. **Cache Audio Files:** Store frequently used pronunciations locally to reduce API calls
2. **Handle Errors Gracefully:** Always implement fallback UI for failed requests
3. **Preload Common Words:** For better UX, preload pronunciations for common vocabulary
4. **Use Appropriate Voice:** Select voice based on your target audience and context
5. **Rate Limit Management:** Implement client-side rate limiting to avoid hitting limits

## Common Use Cases

- 📚 **Language Learning Apps:** Help users learn correct pronunciation
- 📖 **E-Readers:** Add audio pronunciation to difficult words
- ♿ **Accessibility Tools:** Text-to-speech for visually impaired users
- 🎓 **Educational Platforms:** Vocabulary building and pronunciation practice
- 📱 **Dictionary Apps:** Enhance word definitions with audio
- 🗣️ **Speech Training:** Pronunciation reference for speech therapy

## Troubleshooting

### Audio Not Playing
- Check browser audio permissions
- Verify the MIME type is `audio/mpeg`
- Ensure CORS headers are properly configured

### Rate Limit Errors
- Implement request queuing
- Add exponential backoff retry logic
- Consider caching frequently requested words

### Poor Audio Quality
- Use `tts-1-hd` model for higher quality (requires code modification)
- Ensure proper audio playback on client side
- Check network bandwidth

## Future Enhancements

Potential features for future versions:
- Multiple language support
- Phonetic transcription alongside audio
- Slow pronunciation mode for learning
- Batch pronunciation requests
- Custom pronunciation speed
- Regional accent variations

## Support

For issues, questions, or feature requests, please refer to the main project README or create an issue in the repository.

## Version History

- **v2.0** (Current) - Initial release of pronunciation API
  - OpenAI TTS integration
  - 6 voice options
  - MP3 format output
  - Rate limiting
  - 24-hour cache

