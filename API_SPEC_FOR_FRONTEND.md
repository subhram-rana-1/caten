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

---

# Voice-to-Text API Specification

## Overview

This API transcribes audio files to text using OpenAI's Whisper model. It accepts various audio formats and returns the transcribed text.

---

## API Endpoint

### Convert Voice to Text

**Endpoint:** `/api/v2/voice-to-text`

**Method:** `POST`

**Content-Type:** `multipart/form-data`

**Description:** Transcribes an audio file to text using OpenAI Whisper model.

---

## Request Format

### Headers

```
Content-Type: multipart/form-data
```

### Request Body

The request should contain a single file upload field:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `audio_file` | file | **Yes** | Audio file to transcribe. Max size: 25MB. |

### Supported Audio Formats

- MP3 (`.mp3`)
- MP4 (`.mp4`)
- MPEG (`.mpeg`)
- MPGA (`.mpga`)
- M4A (`.m4a`)
- WAV (`.wav`)
- WebM (`.webm`)

### File Size Limits

- **Maximum file size:** 25MB
- Files larger than 25MB will be rejected with a 400 error

---

## Response Format

### Success Response (200 OK)

**Content-Type:** `application/json`

```json
{
  "text": "This is the transcribed text from the audio file."
}
```

### Response Schema

| Field | Type | Description |
|-------|------|-------------|
| `text` | string | The transcribed text from the audio file |

---

## Error Responses

### 400 Bad Request - Invalid Audio Format

```json
{
  "detail": "Invalid audio format. Supported formats: mp3, mp4, mpeg, mpga, m4a, wav, webm"
}
```

### 400 Bad Request - File Too Large

```json
{
  "detail": "Audio file too large (30.50MB). Maximum size is 25MB."
}
```

### 422 Validation Error

```json
{
  "detail": [
    {
      "loc": ["body", "audio_file"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

### 429 Too Many Requests

```json
{
  "error_code": "RATE_LIMIT_001",
  "error_message": "Rate limit exceeded. Maximum 60 requests per minute allowed."
}
```

### 500 Internal Server Error

```json
{
  "detail": "Failed to transcribe audio: [error details]"
}
```

---

## Frontend Implementation Guide

### JavaScript/TypeScript Implementation

```typescript
/**
 * Transcribe audio file to text
 * @param audioFile - The audio file to transcribe (File object)
 * @returns Promise with transcribed text
 */
async function transcribeAudio(audioFile: File): Promise<string> {
  try {
    // Create FormData and append the audio file
    const formData = new FormData();
    formData.append('audio_file', audioFile);
    
    const response = await fetch('http://localhost:8000/api/v2/voice-to-text', {
      method: 'POST',
      body: formData
      // Note: Don't set Content-Type header - browser will set it automatically with boundary
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || `HTTP ${response.status}: ${response.statusText}`);
    }
    
    const result = await response.json();
    return result.text;
    
  } catch (error) {
    console.error('Failed to transcribe audio:', error);
    throw error;
  }
}
```

### React Component Example

```typescript
import React, { useState, useRef } from 'react';

interface VoiceToTextProps {
  onTranscription?: (text: string) => void;
}

export const VoiceToTextUploader: React.FC<VoiceToTextProps> = ({ onTranscription }) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [transcribedText, setTranscribedText] = useState<string>('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    // Validate file size (25MB limit)
    const maxSize = 25 * 1024 * 1024; // 25MB in bytes
    if (file.size > maxSize) {
      setError(`File too large (${(file.size / 1024 / 1024).toFixed(2)}MB). Maximum size is 25MB.`);
      return;
    }

    // Validate file type
    const validExtensions = ['mp3', 'mp4', 'mpeg', 'mpga', 'm4a', 'wav', 'webm'];
    const extension = file.name.split('.').pop()?.toLowerCase();
    if (!extension || !validExtensions.includes(extension)) {
      setError('Invalid audio format. Please upload an audio file.');
      return;
    }

    setLoading(true);
    setError(null);
    setTranscribedText('');

    try {
      const formData = new FormData();
      formData.append('audio_file', file);

      const response = await fetch('http://localhost:8000/api/v2/voice-to-text', {
        method: 'POST',
        body: formData
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to transcribe audio');
      }

      const result = await response.json();
      setTranscribedText(result.text);
      
      if (onTranscription) {
        onTranscription(result.text);
      }

    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="voice-to-text-uploader">
      <input
        ref={fileInputRef}
        type="file"
        accept=".mp3,.mp4,.mpeg,.mpga,.m4a,.wav,.webm,audio/*"
        onChange={handleFileChange}
        disabled={loading}
        style={{ display: 'none' }}
      />
      
      <button 
        onClick={() => fileInputRef.current?.click()}
        disabled={loading}
        className="upload-button"
      >
        {loading ? 'Transcribing...' : 'Upload Audio File'}
      </button>

      {loading && (
        <div className="loading-indicator">
          <p>Transcribing audio, please wait...</p>
        </div>
      )}

      {error && (
        <div className="error-message">
          <p>Error: {error}</p>
        </div>
      )}

      {transcribedText && (
        <div className="transcription-result">
          <h3>Transcription:</h3>
          <p>{transcribedText}</p>
        </div>
      )}
    </div>
  );
};
```

### Vanilla JavaScript Example

```html
<!DOCTYPE html>
<html>
<head>
  <title>Voice to Text Converter</title>
  <style>
    .container {
      max-width: 600px;
      margin: 50px auto;
      padding: 20px;
      font-family: Arial, sans-serif;
    }
    .file-input-wrapper {
      margin: 20px 0;
    }
    .upload-btn {
      padding: 10px 20px;
      background-color: #4CAF50;
      color: white;
      border: none;
      cursor: pointer;
      border-radius: 4px;
    }
    .upload-btn:disabled {
      background-color: #cccccc;
      cursor: not-allowed;
    }
    .result-box {
      margin-top: 20px;
      padding: 15px;
      border: 1px solid #ddd;
      border-radius: 4px;
      background-color: #f9f9f9;
    }
    .error {
      color: red;
      margin-top: 10px;
    }
    .loading {
      color: #666;
      font-style: italic;
    }
  </style>
</head>
<body>
  <div class="container">
    <h1>Voice to Text Converter</h1>
    
    <div class="file-input-wrapper">
      <input type="file" id="audioFile" accept="audio/*,.mp3,.mp4,.mpeg,.mpga,.m4a,.wav,.webm">
      <button id="uploadBtn" class="upload-btn">Transcribe Audio</button>
    </div>
    
    <div id="status"></div>
    <div id="result" class="result-box" style="display:none;"></div>
  </div>

  <script>
    const audioFileInput = document.getElementById('audioFile');
    const uploadBtn = document.getElementById('uploadBtn');
    const statusDiv = document.getElementById('status');
    const resultDiv = document.getElementById('result');

    uploadBtn.addEventListener('click', async () => {
      const file = audioFileInput.files[0];
      
      if (!file) {
        statusDiv.innerHTML = '<p class="error">Please select an audio file first.</p>';
        return;
      }

      // Validate file size
      const maxSize = 25 * 1024 * 1024; // 25MB
      if (file.size > maxSize) {
        statusDiv.innerHTML = `<p class="error">File too large (${(file.size / 1024 / 1024).toFixed(2)}MB). Maximum size is 25MB.</p>`;
        return;
      }

      // Show loading state
      uploadBtn.disabled = true;
      statusDiv.innerHTML = '<p class="loading">Transcribing audio...</p>';
      resultDiv.style.display = 'none';

      try {
        const formData = new FormData();
        formData.append('audio_file', file);

        const response = await fetch('http://localhost:8000/api/v2/voice-to-text', {
          method: 'POST',
          body: formData
        });

        if (!response.ok) {
          const error = await response.json();
          throw new Error(error.detail || 'Failed to transcribe audio');
        }

        const result = await response.json();
        
        // Display result
        statusDiv.innerHTML = '<p style="color: green;">✓ Transcription completed!</p>';
        resultDiv.style.display = 'block';
        resultDiv.innerHTML = `<h3>Transcription:</h3><p>${result.text}</p>`;

      } catch (error) {
        statusDiv.innerHTML = `<p class="error">Error: ${error.message}</p>`;
        resultDiv.style.display = 'none';
      } finally {
        uploadBtn.disabled = false;
      }
    });
  </script>
</body>
</html>
```

### Vue.js 3 Composition API Example

```vue
<template>
  <div class="voice-to-text">
    <h2>Voice to Text Converter</h2>
    
    <input
      ref="fileInput"
      type="file"
      accept="audio/*,.mp3,.mp4,.mpeg,.mpga,.m4a,.wav,.webm"
      @change="handleFileUpload"
      :disabled="loading"
    />
    
    <div v-if="loading" class="loading">
      <p>Transcribing audio...</p>
    </div>
    
    <div v-if="error" class="error">
      <p>{{ error }}</p>
    </div>
    
    <div v-if="transcribedText" class="result">
      <h3>Transcription:</h3>
      <p>{{ transcribedText }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';

const fileInput = ref<HTMLInputElement>();
const loading = ref(false);
const error = ref<string>('');
const transcribedText = ref<string>('');

const handleFileUpload = async (event: Event) => {
  const target = event.target as HTMLInputElement;
  const file = target.files?.[0];
  
  if (!file) return;
  
  // Validate file size
  const maxSize = 25 * 1024 * 1024; // 25MB
  if (file.size > maxSize) {
    error.value = `File too large (${(file.size / 1024 / 1024).toFixed(2)}MB). Maximum size is 25MB.`;
    return;
  }
  
  loading.value = true;
  error.value = '';
  transcribedText.value = '';
  
  try {
    const formData = new FormData();
    formData.append('audio_file', file);
    
    const response = await fetch('http://localhost:8000/api/v2/voice-to-text', {
      method: 'POST',
      body: formData
    });
    
    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || 'Failed to transcribe audio');
    }
    
    const result = await response.json();
    transcribedText.value = result.text;
    
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'An error occurred';
  } finally {
    loading.value = false;
  }
};
</script>

<style scoped>
.voice-to-text {
  max-width: 600px;
  margin: 0 auto;
  padding: 20px;
}

.error {
  color: red;
  margin-top: 10px;
}

.loading {
  color: #666;
  font-style: italic;
  margin-top: 10px;
}

.result {
  margin-top: 20px;
  padding: 15px;
  border: 1px solid #ddd;
  border-radius: 4px;
  background-color: #f9f9f9;
}
</style>
```

---

## TypeScript Types

```typescript
// Request (FormData)
interface VoiceToTextRequest {
  audio_file: File;
}

// Response
interface VoiceToTextResponse {
  text: string;
}

// Error Response
interface ErrorResponse {
  detail: string;
}
```

---

## Complete API Client Example

```typescript
class VoiceAPIClient {
  private baseUrl: string;

  constructor(baseUrl: string = 'http://localhost:8000') {
    this.baseUrl = baseUrl;
  }

  /**
   * Transcribe audio file to text
   */
  async transcribeAudio(audioFile: File): Promise<string> {
    // Validate file size
    const maxSize = 25 * 1024 * 1024; // 25MB
    if (audioFile.size > maxSize) {
      throw new Error(`File too large (${(audioFile.size / 1024 / 1024).toFixed(2)}MB). Maximum size is 25MB.`);
    }

    // Validate file type
    const validExtensions = ['mp3', 'mp4', 'mpeg', 'mpga', 'm4a', 'wav', 'webm'];
    const extension = audioFile.name.split('.').pop()?.toLowerCase();
    if (!extension || !validExtensions.includes(extension)) {
      throw new Error('Invalid audio format. Supported formats: ' + validExtensions.join(', '));
    }

    const formData = new FormData();
    formData.append('audio_file', audioFile);

    const response = await fetch(`${this.baseUrl}/api/v2/voice-to-text`, {
      method: 'POST',
      body: formData
    });

    if (!response.ok) {
      const error: ErrorResponse = await response.json();
      throw new Error(error.detail);
    }

    const result: VoiceToTextResponse = await response.json();
    return result.text;
  }

  /**
   * Transcribe audio from URL
   */
  async transcribeAudioFromUrl(audioUrl: string): Promise<string> {
    // Fetch the audio file
    const audioResponse = await fetch(audioUrl);
    const audioBlob = await audioResponse.blob();
    
    // Create a File object from the blob
    const filename = audioUrl.split('/').pop() || 'audio.mp3';
    const audioFile = new File([audioBlob], filename, { type: audioBlob.type });
    
    return this.transcribeAudio(audioFile);
  }

  /**
   * Transcribe audio from MediaRecorder
   */
  async transcribeRecording(audioBlob: Blob, filename: string = 'recording.webm'): Promise<string> {
    const audioFile = new File([audioBlob], filename, { type: audioBlob.type });
    return this.transcribeAudio(audioFile);
  }
}
```

---

## Usage Examples

### Example 1: File Upload

```typescript
const client = new VoiceAPIClient();

// Handle file input change
document.getElementById('audioInput')?.addEventListener('change', async (e) => {
  const file = (e.target as HTMLInputElement).files?.[0];
  if (file) {
    try {
      const text = await client.transcribeAudio(file);
      console.log('Transcribed text:', text);
    } catch (error) {
      console.error('Transcription failed:', error);
    }
  }
});
```

### Example 2: Voice Recording

```typescript
// Record audio from microphone
let mediaRecorder: MediaRecorder;
let audioChunks: Blob[] = [];

async function startRecording() {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  mediaRecorder = new MediaRecorder(stream);
  
  mediaRecorder.ondataavailable = (event) => {
    audioChunks.push(event.data);
  };
  
  mediaRecorder.start();
}

async function stopRecordingAndTranscribe() {
  return new Promise((resolve, reject) => {
    mediaRecorder.onstop = async () => {
      const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
      audioChunks = [];
      
      try {
        const client = new VoiceAPIClient();
        const text = await client.transcribeRecording(audioBlob);
        resolve(text);
      } catch (error) {
        reject(error);
      }
    };
    
    mediaRecorder.stop();
  });
}
```

### Example 3: Drag and Drop

```typescript
const dropZone = document.getElementById('dropZone');

dropZone?.addEventListener('dragover', (e) => {
  e.preventDefault();
  dropZone.classList.add('drag-over');
});

dropZone?.addEventListener('drop', async (e) => {
  e.preventDefault();
  dropZone.classList.remove('drag-over');
  
  const file = e.dataTransfer?.files[0];
  if (file) {
    try {
      const client = new VoiceAPIClient();
      const text = await client.transcribeAudio(file);
      console.log('Transcribed text:', text);
    } catch (error) {
      console.error('Transcription failed:', error);
    }
  }
});
```

---

## Summary for AI Agent

**Task:** Build a frontend application that allows users to:
1. Upload an audio file or record audio from microphone
2. Transcribe the audio to text using the API
3. Display the transcribed text
4. Handle errors and loading states

**API Details:**
- **Endpoint:** `POST http://localhost:8000/api/v2/voice-to-text`
- **Request:** FormData with `audio_file` field
- **Response:** `{ "text": "transcribed text" }`
- **Content-Type:** `multipart/form-data` (request), `application/json` (response)
- **Max file size:** 25MB
- **Supported formats:** mp3, mp4, mpeg, mpga, m4a, wav, webm

**Key Features to Implement:**
1. File upload input with drag-and-drop support
2. Optional: Voice recording with MediaRecorder API
3. File validation (size and format)
4. Loading indicator during transcription
5. Error handling for validation and API errors
6. Display transcribed text in a readable format
7. Optional: Copy to clipboard functionality
8. Optional: Download transcription as text file

**Use the code examples above** to implement the functionality in your preferred framework (React, Vue, Angular, or vanilla JS).


