# 🤖 Prompt for AI Coding Agent - Word Pronunciation App

Copy and paste this entire prompt to your AI coding agent:

---

## Task

Build a web application that allows users to hear the pronunciation of words using a backend API.

## API Endpoint

**URL:** `POST http://localhost:8000/api/v2/pronunciation`

**Request Body:**
```json
{
  "word": "hello",
  "voice": "nova"
}
```

**Response:** MP3 audio file (binary data)

**Content-Type:** Send `application/json`, receive `audio/mpeg`

## Request Parameters

| Parameter | Type | Required | Default | Options |
|-----------|------|----------|---------|---------|
| `word` | string | Yes | - | Any word (1-100 chars) |
| `voice` | string | No | "nova" | "nova", "shimmer", "alloy", "echo", "fable", "onyx" |

## Voice Options

- **nova** - Sweet American female voice (default, recommended)
- **shimmer** - Soft American female voice
- **alloy** - Neutral voice
- **echo** - American male voice
- **fable** - British male voice
- **onyx** - Deep American male voice

## Required Features

1. **Input Field** - User enters a word
2. **Voice Selector** - Dropdown with 6 voice options (default: "nova")
3. **Play Button** - Fetches audio and plays it
4. **Loading State** - Show when fetching audio
5. **Error Handling** - Display errors to user

## Optional Features

- Download button to save MP3 file
- Preload common words for instant playback
- Cache previously fetched pronunciations
- Auto-play after generation
- Volume control

## Implementation Code

### JavaScript (Vanilla)

```javascript
async function playPronunciation(word, voice = 'nova') {
  try {
    const response = await fetch('http://localhost:8000/api/v2/pronunciation', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ word, voice })
    });

    if (!response.ok) throw new Error('Failed to generate audio');

    const audioBlob = await response.blob();
    const audioUrl = URL.createObjectURL(audioBlob);
    const audio = new Audio(audioUrl);
    audio.volume = 1.0;
    await audio.play();
    audio.onended = () => URL.revokeObjectURL(audioUrl);
  } catch (error) {
    console.error('Error:', error);
    alert('Failed to play pronunciation');
  }
}
```

### React Component

```jsx
import React, { useState } from 'react';

function PronunciationApp() {
  const [word, setWord] = useState('');
  const [voice, setVoice] = useState('nova');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const voices = [
    { value: 'nova', label: 'Nova (Sweet Female)' },
    { value: 'shimmer', label: 'Shimmer (Soft Female)' },
    { value: 'alloy', label: 'Alloy (Neutral)' },
    { value: 'echo', label: 'Echo (Male)' },
    { value: 'fable', label: 'Fable (British Male)' },
    { value: 'onyx', label: 'Onyx (Deep Male)' }
  ];

  const handlePlay = async () => {
    if (!word) {
      setError('Please enter a word');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const response = await fetch('http://localhost:8000/api/v2/pronunciation', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ word, voice })
      });

      if (!response.ok) {
        throw new Error('Failed to generate audio');
      }

      const audioBlob = await response.blob();
      const audioUrl = URL.createObjectURL(audioBlob);
      const audio = new Audio(audioUrl);
      audio.volume = 1.0;
      await audio.play();
      audio.onended = () => URL.revokeObjectURL(audioUrl);
    } catch (err) {
      setError('Failed to play pronunciation. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: '600px', margin: '50px auto', padding: '20px' }}>
      <h1>🔊 Word Pronunciation</h1>
      
      <div style={{ marginBottom: '20px' }}>
        <label>
          Enter a word:
          <input
            type="text"
            value={word}
            onChange={(e) => setWord(e.target.value)}
            placeholder="e.g., beautiful"
            style={{
              width: '100%',
              padding: '10px',
              fontSize: '16px',
              marginTop: '5px'
            }}
          />
        </label>
      </div>

      <div style={{ marginBottom: '20px' }}>
        <label>
          Select voice:
          <select
            value={voice}
            onChange={(e) => setVoice(e.target.value)}
            style={{
              width: '100%',
              padding: '10px',
              fontSize: '16px',
              marginTop: '5px'
            }}
          >
            {voices.map(v => (
              <option key={v.value} value={v.value}>{v.label}</option>
            ))}
          </select>
        </label>
      </div>

      <button
        onClick={handlePlay}
        disabled={loading}
        style={{
          width: '100%',
          padding: '12px',
          fontSize: '18px',
          backgroundColor: loading ? '#ccc' : '#667eea',
          color: 'white',
          border: 'none',
          borderRadius: '6px',
          cursor: loading ? 'not-allowed' : 'pointer'
        }}
      >
        {loading ? '⏳ Loading...' : '🔊 Play Pronunciation'}
      </button>

      {error && (
        <div style={{ color: 'red', marginTop: '10px' }}>
          {error}
        </div>
      )}
    </div>
  );
}

export default PronunciationApp;
```

### Vue Component

```vue
<template>
  <div class="pronunciation-app">
    <h1>🔊 Word Pronunciation</h1>
    
    <div class="input-group">
      <label>Enter a word:</label>
      <input 
        v-model="word" 
        placeholder="e.g., beautiful"
        @keyup.enter="playPronunciation"
      />
    </div>

    <div class="input-group">
      <label>Select voice:</label>
      <select v-model="voice">
        <option value="nova">Nova (Sweet Female)</option>
        <option value="shimmer">Shimmer (Soft Female)</option>
        <option value="alloy">Alloy (Neutral)</option>
        <option value="echo">Echo (Male)</option>
        <option value="fable">Fable (British Male)</option>
        <option value="onyx">Onyx (Deep Male)</option>
      </select>
    </div>

    <button @click="playPronunciation" :disabled="loading">
      {{ loading ? '⏳ Loading...' : '🔊 Play Pronunciation' }}
    </button>

    <div v-if="error" class="error">{{ error }}</div>
  </div>
</template>

<script setup>
import { ref } from 'vue';

const word = ref('');
const voice = ref('nova');
const loading = ref(false);
const error = ref('');

const playPronunciation = async () => {
  if (!word.value) {
    error.value = 'Please enter a word';
    return;
  }

  loading.value = true;
  error.value = '';

  try {
    const response = await fetch('http://localhost:8000/api/v2/pronunciation', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        word: word.value, 
        voice: voice.value 
      })
    });

    if (!response.ok) throw new Error('Failed to generate audio');

    const audioBlob = await response.blob();
    const audioUrl = URL.createObjectURL(audioBlob);
    const audio = new Audio(audioUrl);
    audio.volume = 1.0;
    await audio.play();
    audio.onended = () => URL.revokeObjectURL(audioUrl);
  } catch (err) {
    error.value = 'Failed to play pronunciation. Please try again.';
  } finally {
    loading.value = false;
  }
};
</script>

<style scoped>
.pronunciation-app {
  max-width: 600px;
  margin: 50px auto;
  padding: 20px;
}

.input-group {
  margin-bottom: 20px;
}

label {
  display: block;
  margin-bottom: 5px;
  font-weight: bold;
}

input, select {
  width: 100%;
  padding: 10px;
  font-size: 16px;
  border: 2px solid #ddd;
  border-radius: 6px;
}

button {
  width: 100%;
  padding: 12px;
  font-size: 18px;
  background-color: #667eea;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
}

button:disabled {
  background-color: #ccc;
  cursor: not-allowed;
}

.error {
  color: red;
  margin-top: 10px;
}
</style>
```

## Error Handling

Handle these HTTP status codes:

- **200** - Success, play the audio
- **400** - Invalid request (show error message)
- **422** - Validation error (show field errors)
- **429** - Rate limit exceeded (show "too many requests")
- **500** - Server error (show "try again later")

## Styling Suggestions

1. Clean, modern UI with gradient colors
2. Large, clear input fields
3. Prominent play button
4. Visual feedback for loading state
5. Error messages in red
6. Responsive design for mobile

## Example UI Flow

1. User enters "beautiful" in input field
2. User selects "nova" voice (default)
3. User clicks "Play Pronunciation"
4. Button shows loading state (⏳)
5. Audio plays automatically
6. Button returns to normal state
7. User can play again or try new word

## Testing

Test these scenarios:
- Empty word input (should show error)
- Valid word with different voices
- Network error (should handle gracefully)
- Rapid multiple clicks (should queue or prevent)

## Additional Instructions

- Use modern CSS (flexbox/grid)
- Make it responsive
- Add hover effects on buttons
- Include a nice color scheme
- Add keyboard shortcuts (Enter to play)
- Consider adding a download button
- Show success feedback after playing

## API Rate Limit

- 60 requests per minute per IP
- Show friendly message if limit exceeded
- Consider client-side rate limiting

---

## Summary

Build a simple, elegant web app where users can:
1. Type a word
2. Choose a voice
3. Click to hear pronunciation
4. Repeat with different words/voices

The API does all the heavy lifting - you just need to:
- Collect user input
- Make POST request
- Play the returned audio blob
- Handle errors gracefully

Good luck! 🚀

