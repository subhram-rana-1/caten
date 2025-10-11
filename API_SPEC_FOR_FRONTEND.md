# API Specification for Frontend Integration - Word Pronunciation API

## Overview

This API generates audio pronunciation for words using OpenAI's Text-to-Speech. The audio is returned as an MP3 file that can be played directly in the browser.

---

## Base URL

```
http://localhost:8000
```

For production, replace with your actual domain.

---

## API Endpoint

### Generate Word Pronunciation

**Endpoint:** `/api/v2/pronunciation`

**Method:** `POST`

**Content-Type:** `application/json`

**Description:** Generates and returns an MP3 audio file with the pronunciation of a given word.

---

## Request Format

### Headers

```
Content-Type: application/json
```

### Request Body

```json
{
  "word": "string",      // Required: The word to pronounce (1-100 characters)
  "voice": "string"      // Optional: Voice name (default: "nova")
}
```

### Request Body Schema

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `word` | string | **Yes** | - | The word to generate pronunciation for. Length: 1-100 characters. |
| `voice` | string | No | `"nova"` | Voice to use for pronunciation. See voice options below. |

### Voice Options

| Voice Value | Description | Gender | Accent | Recommended For |
|-------------|-------------|--------|--------|-----------------|
| `"nova"` | Sweet-toned, clear | Female | American | **Default** - Best for general use |
| `"shimmer"` | Soft, gentle | Female | American | Alternative female voice |
| `"alloy"` | Neutral, balanced | Neutral | American | Gender-neutral option |
| `"echo"` | Natural | Male | American | Male voice option |
| `"fable"` | Professional | Male | British | British accent |
| `"onyx"` | Deep, authoritative | Male | American | Deep male voice |

---

## Response Format

### Success Response (200 OK)

**Content-Type:** `audio/mpeg`

**Response Body:** Binary MP3 audio data

**Headers:**
```
Content-Type: audio/mpeg
Content-Disposition: inline; filename="{word}_pronunciation.mp3"
Cache-Control: public, max-age=86400
```

**Audio Specifications:**
- Format: MP3
- Bitrate: 128 kbps
- Quality: High-definition (TTS-1-HD model)
- Volume: Boosted by 8 dB for clarity
- Size: Typically 5-20 KB per word

### Error Responses

#### 400 Bad Request
```json
{
  "detail": "Invalid voice. Must be one of: alloy, echo, fable, onyx, nova, shimmer"
}
```

#### 422 Validation Error
```json
{
  "detail": [
    {
      "loc": ["body", "word"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
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

---

## Frontend Implementation Guide

### JavaScript/TypeScript Implementation

```typescript
/**
 * Generate and play pronunciation audio for a word
 * @param word - The word to pronounce
 * @param voice - Voice to use (optional, defaults to "nova")
 * @returns Promise<void>
 */
async function playPronunciation(word: string, voice: string = 'nova'): Promise<void> {
  try {
    const response = await fetch('http://localhost:8000/api/v2/pronunciation', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ word, voice })
    });
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    
    // Get audio as blob
    const audioBlob = await response.blob();
    
    // Create URL and play
    const audioUrl = URL.createObjectURL(audioBlob);
    const audio = new Audio(audioUrl);
    audio.volume = 1.0; // Maximum volume
    
    await audio.play();
    
    // Clean up after playback
    audio.onended = () => {
      URL.revokeObjectURL(audioUrl);
    };
    
  } catch (error) {
    console.error('Failed to play pronunciation:', error);
    throw error;
  }
}
```

### React Component Example

```typescript
import React, { useState } from 'react';

interface PronunciationButtonProps {
  word: string;
  voice?: 'nova' | 'shimmer' | 'alloy' | 'echo' | 'fable' | 'onyx';
}

export const PronunciationButton: React.FC<PronunciationButtonProps> = ({ 
  word, 
  voice = 'nova' 
}) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handlePlay = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch('http://localhost:8000/api/v2/pronunciation', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ word, voice })
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to generate audio');
      }

      const audioBlob = await response.blob();
      const audioUrl = URL.createObjectURL(audioBlob);
      const audio = new Audio(audioUrl);
      audio.volume = 1.0;
      
      await audio.play();
      
      audio.onended = () => URL.revokeObjectURL(audioUrl);
      
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      console.error('Pronunciation error:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <button 
        onClick={handlePlay} 
        disabled={loading}
        style={{
          padding: '8px 16px',
          cursor: loading ? 'not-allowed' : 'pointer',
          opacity: loading ? 0.6 : 1
        }}
      >
        {loading ? '⏳ Loading...' : '🔊 Pronounce'}
      </button>
      {error && <div style={{ color: 'red', marginTop: '8px' }}>{error}</div>}
    </div>
  );
};
```

### Vue.js Component Example

```vue
<template>
  <div>
    <button @click="playPronunciation" :disabled="loading">
      {{ loading ? '⏳ Loading...' : '🔊 Pronounce' }}
    </button>
    <div v-if="error" class="error">{{ error }}</div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';

interface Props {
  word: string;
  voice?: 'nova' | 'shimmer' | 'alloy' | 'echo' | 'fable' | 'onyx';
}

const props = withDefaults(defineProps<Props>(), {
  voice: 'nova'
});

const loading = ref(false);
const error = ref<string | null>(null);

const playPronunciation = async () => {
  loading.value = true;
  error.value = null;

  try {
    const response = await fetch('http://localhost:8000/api/v2/pronunciation', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        word: props.word, 
        voice: props.voice 
      })
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || 'Failed to generate audio');
    }

    const audioBlob = await response.blob();
    const audioUrl = URL.createObjectURL(audioBlob);
    const audio = new Audio(audioUrl);
    audio.volume = 1.0;
    
    await audio.play();
    audio.onended = () => URL.revokeObjectURL(audioUrl);
    
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Unknown error';
  } finally {
    loading.value = false;
  }
};
</script>

<style scoped>
.error {
  color: red;
  margin-top: 8px;
}
</style>
```

### Angular Service Example

```typescript
import { Injectable } from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';

export type VoiceType = 'nova' | 'shimmer' | 'alloy' | 'echo' | 'fable' | 'onyx';

@Injectable({
  providedIn: 'root'
})
export class PronunciationService {
  private readonly API_URL = 'http://localhost:8000/api/v2/pronunciation';

  constructor(private http: HttpClient) {}

  async playPronunciation(word: string, voice: VoiceType = 'nova'): Promise<void> {
    try {
      const blob = await firstValueFrom(
        this.http.post(this.API_URL, { word, voice }, { 
          responseType: 'blob' 
        })
      );

      const audioUrl = URL.createObjectURL(blob);
      const audio = new Audio(audioUrl);
      audio.volume = 1.0;
      
      await audio.play();
      
      audio.onended = () => URL.revokeObjectURL(audioUrl);
      
    } catch (error) {
      if (error instanceof HttpErrorResponse) {
        console.error('HTTP Error:', error.status, error.message);
      }
      throw error;
    }
  }

  async downloadPronunciation(word: string, voice: VoiceType = 'nova'): Promise<void> {
    const blob = await firstValueFrom(
      this.http.post(this.API_URL, { word, voice }, { 
        responseType: 'blob' 
      })
    );

    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `${word}_pronunciation.mp3`;
    link.click();
    URL.revokeObjectURL(url);
  }
}
```

---

## Advanced Features

### 1. Audio Caching

Implement client-side caching to avoid repeated API calls:

```typescript
class PronunciationCache {
  private cache = new Map<string, Blob>();

  async getPronunciation(word: string, voice: string = 'nova'): Promise<Blob> {
    const key = `${word}-${voice}`;
    
    if (this.cache.has(key)) {
      return this.cache.get(key)!;
    }

    const response = await fetch('http://localhost:8000/api/v2/pronunciation', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ word, voice })
    });

    if (!response.ok) throw new Error('Failed to fetch pronunciation');

    const blob = await response.blob();
    this.cache.set(key, blob);
    
    return blob;
  }

  clear() {
    this.cache.clear();
  }
}

// Usage
const cache = new PronunciationCache();
const audioBlob = await cache.getPronunciation('hello');
```

### 2. Preloading

Preload pronunciations for better UX:

```typescript
async function preloadPronunciations(words: string[], voice: string = 'nova') {
  const promises = words.map(word =>
    fetch('http://localhost:8000/api/v2/pronunciation', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ word, voice })
    }).then(r => r.blob())
  );

  return Promise.all(promises);
}

// Usage
await preloadPronunciations(['hello', 'world', 'beautiful']);
```

### 3. Download Functionality

```typescript
async function downloadPronunciation(word: string, voice: string = 'nova') {
  const response = await fetch('http://localhost:8000/api/v2/pronunciation', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ word, voice })
  });

  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  
  const link = document.createElement('a');
  link.href = url;
  link.download = `${word}_pronunciation.mp3`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  
  URL.revokeObjectURL(url);
}
```

### 4. Queue Management (Rate Limiting)

```typescript
class RequestQueue {
  private queue: Array<() => Promise<void>> = [];
  private processing = false;
  private readonly delayMs: number;

  constructor(requestsPerMinute: number = 50) {
    this.delayMs = 60000 / requestsPerMinute;
  }

  async add(fn: () => Promise<void>) {
    this.queue.push(fn);
    if (!this.processing) {
      this.process();
    }
  }

  private async process() {
    this.processing = true;
    
    while (this.queue.length > 0) {
      const fn = this.queue.shift()!;
      await fn();
      await new Promise(resolve => setTimeout(resolve, this.delayMs));
    }
    
    this.processing = false;
  }
}

// Usage
const queue = new RequestQueue(50); // 50 requests per minute

queue.add(async () => {
  await playPronunciation('hello');
});
```

---

## Rate Limiting Details

- **Limit:** 60 requests per minute per IP address
- **Window:** Rolling 60-second window
- **Identifier:** Client IP address (or X-Forwarded-For header)
- **Response:** HTTP 429 when exceeded

**Best Practices:**
1. Implement client-side caching
2. Add request queuing
3. Show loading states to users
4. Handle rate limit errors gracefully

---

## CORS Configuration

The API has CORS enabled for all origins:

```
Access-Control-Allow-Origin: *
Access-Control-Allow-Methods: POST, OPTIONS
Access-Control-Allow-Headers: Content-Type
```

No special CORS handling needed in your frontend.

---

## Error Handling Best Practices

```typescript
async function playPronunciationSafe(word: string, voice: string = 'nova') {
  try {
    const response = await fetch('http://localhost:8000/api/v2/pronunciation', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ word, voice })
    });

    // Handle different error types
    if (response.status === 429) {
      throw new Error('Too many requests. Please wait a moment and try again.');
    }

    if (response.status === 400) {
      const error = await response.json();
      throw new Error(`Invalid request: ${error.detail}`);
    }

    if (response.status === 500) {
      throw new Error('Server error. Please try again later.');
    }

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    const audioBlob = await response.blob();
    const audioUrl = URL.createObjectURL(audioBlob);
    const audio = new Audio(audioUrl);
    audio.volume = 1.0;
    
    await audio.play();
    
    audio.onended = () => URL.revokeObjectURL(audioUrl);
    
  } catch (error) {
    if (error instanceof TypeError) {
      console.error('Network error:', error);
      throw new Error('Network error. Please check your connection.');
    }
    
    throw error;
  }
}
```

---

## Testing

### Test with cURL

```bash
# Basic test
curl -X POST http://localhost:8000/api/v2/pronunciation \
  -H "Content-Type: application/json" \
  -d '{"word": "hello", "voice": "nova"}' \
  --output hello.mp3

# Test with different voice
curl -X POST http://localhost:8000/api/v2/pronunciation \
  -H "Content-Type: application/json" \
  -d '{"word": "beautiful", "voice": "shimmer"}' \
  --output beautiful.mp3
```

### Test with Postman

1. Method: POST
2. URL: `http://localhost:8000/api/v2/pronunciation`
3. Headers: `Content-Type: application/json`
4. Body (raw JSON):
```json
{
  "word": "hello",
  "voice": "nova"
}
```
5. Send and download the audio file

---

## TypeScript Type Definitions

```typescript
// Request types
export interface PronunciationRequest {
  word: string;
  voice?: 'nova' | 'shimmer' | 'alloy' | 'echo' | 'fable' | 'onyx';
}

// Error response types
export interface ErrorResponse {
  detail: string;
}

export interface RateLimitError {
  error_code: string;
  error_message: string;
}

export interface ValidationError {
  detail: Array<{
    loc: string[];
    msg: string;
    type: string;
  }>;
}

// API service
export class PronunciationAPI {
  constructor(private baseUrl: string = 'http://localhost:8000') {}

  async getPronunciation(
    word: string, 
    voice: PronunciationRequest['voice'] = 'nova'
  ): Promise<Blob> {
    const response = await fetch(`${this.baseUrl}/api/v2/pronunciation`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ word, voice })
    });

    if (!response.ok) {
      const error: ErrorResponse = await response.json();
      throw new Error(error.detail);
    }

    return response.blob();
  }
}
```

---

## Summary for AI Agent

**Task:** Build a frontend application that allows users to:
1. Enter a word
2. Select a voice (optional)
3. Click a button to hear the pronunciation
4. Download the audio file (optional feature)

**API Details:**
- **Endpoint:** `POST http://localhost:8000/api/v2/pronunciation`
- **Request:** `{ "word": "string", "voice": "nova" }`
- **Response:** MP3 audio blob
- **Content-Type:** `application/json` (request), `audio/mpeg` (response)

**Key Features to Implement:**
1. Input field for word
2. Dropdown for voice selection
3. Play button with loading state
4. Error handling for rate limits and validation
5. Audio playback with HTML5 Audio API
6. Optional: Download button
7. Optional: Caching for performance
8. Optional: Preload common words

**Use the code examples above** to implement the functionality in your preferred framework (React, Vue, Angular, or vanilla JS).


