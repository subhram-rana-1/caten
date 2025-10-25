# Voice-to-Text API Documentation

## Overview

The Voice-to-Text API converts audio files to text using OpenAI's Whisper model. This powerful speech recognition API supports multiple audio formats and provides accurate transcriptions.

## Features

- 🎤 **Multiple Audio Formats**: Supports MP3, WAV, M4A, WebM, MP4, MPEG, MPGA
- 🌐 **Language Support**: Automatic language detection (supports 50+ languages)
- 📁 **Large File Support**: Up to 25MB per audio file
- ⚡ **Fast Processing**: Powered by OpenAI Whisper
- 🔒 **Secure**: Rate-limited and validated

## API Endpoint

```
POST /api/v2/voice-to-text
```

## Request

### Headers
```
Content-Type: multipart/form-data
```

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `audio_file` | file | Yes | Audio file to transcribe (max 25MB) |

### Supported Audio Formats

- MP3 (`.mp3`)
- MP4 (`.mp4`)
- MPEG (`.mpeg`)
- MPGA (`.mpga`)
- M4A (`.m4a`)
- WAV (`.wav`)
- WebM (`.webm`)

## Response

### Success Response (200 OK)

```json
{
  "text": "This is the transcribed text from the audio file."
}
```

### Error Responses

#### 400 Bad Request - Invalid Format
```json
{
  "detail": "Invalid audio format. Supported formats: mp3, mp4, mpeg, mpga, m4a, wav, webm"
}
```

#### 400 Bad Request - File Too Large
```json
{
  "detail": "Audio file too large (30.50MB). Maximum size is 25MB."
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
  "detail": "Failed to transcribe audio: [error details]"
}
```

## Usage Examples

### cURL

```bash
# Basic usage
curl -X POST http://localhost:8000/api/v2/voice-to-text \
  -F "audio_file=@/path/to/audio.mp3"

# With verbose output
curl -v -X POST http://localhost:8000/api/v2/voice-to-text \
  -F "audio_file=@recording.wav"
```

### Python

```python
import httpx

async def transcribe_audio(audio_file_path: str) -> str:
    """Transcribe an audio file to text."""
    url = "http://localhost:8000/api/v2/voice-to-text"
    
    with open(audio_file_path, "rb") as f:
        files = {"audio_file": f}
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, files=files)
            
            if response.status_code == 200:
                return response.json()["text"]
            else:
                raise Exception(f"Error: {response.json()['detail']}")

# Usage
text = await transcribe_audio("audio.mp3")
print(f"Transcribed: {text}")
```

### JavaScript/TypeScript

```typescript
async function transcribeAudio(audioFile: File): Promise<string> {
  const formData = new FormData();
  formData.append('audio_file', audioFile);
  
  const response = await fetch('http://localhost:8000/api/v2/voice-to-text', {
    method: 'POST',
    body: formData
  });
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail);
  }
  
  const result = await response.json();
  return result.text;
}

// Usage with file input
const fileInput = document.getElementById('audioInput') as HTMLInputElement;
const file = fileInput.files[0];
const text = await transcribeAudio(file);
console.log('Transcribed:', text);
```

### React Component

```typescript
import React, { useState } from 'react';

export const VoiceToTextConverter: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [text, setText] = useState('');
  const [error, setError] = useState('');

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setLoading(true);
    setError('');
    setText('');

    try {
      const formData = new FormData();
      formData.append('audio_file', file);

      const response = await fetch('http://localhost:8000/api/v2/voice-to-text', {
        method: 'POST',
        body: formData
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail);
      }

      const result = await response.json();
      setText(result.text);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <input
        type="file"
        accept="audio/*"
        onChange={handleFileChange}
        disabled={loading}
      />
      {loading && <p>Transcribing...</p>}
      {error && <p style={{color: 'red'}}>{error}</p>}
      {text && <p>{text}</p>}
    </div>
  );
};
```

## Testing

### Using the HTML Test Client

1. Start the FastAPI server:
   ```bash
   python -m uvicorn app.main:app --reload
   ```

2. Open `test_voice_to_text.html` in your browser

3. Either:
   - Upload an audio file by clicking or drag-and-drop
   - Record audio directly from your microphone

4. Click "Transcribe Audio" to convert to text

### Using the Python Test Script

```bash
# Place an audio file named 'test_audio.mp3' in the project directory
python test_voice_to_text_api.py
```

## Rate Limiting

- **Default limit**: 60 requests per minute per client
- Rate limit is based on client IP address
- Exceeding the limit returns a 429 error

## Technical Details

### Implementation

The API uses:
- **OpenAI Whisper**: State-of-the-art speech recognition model
- **FastAPI**: High-performance async web framework
- **Multipart file upload**: Efficient binary file handling

### File Size Considerations

- **Maximum file size**: 25MB (OpenAI Whisper API limit)
- For longer recordings, consider:
  - Compressing audio to lower bitrate
  - Splitting audio into smaller chunks
  - Using a lower sample rate (e.g., 16kHz)

### Performance

- Typical transcription time: 5-15 seconds for 1-minute audio
- Processing time depends on:
  - Audio file size
  - Audio duration
  - OpenAI API response time
  - Network latency

## Best Practices

1. **Audio Quality**
   - Use clear audio with minimal background noise
   - 16kHz or higher sample rate recommended
   - Mono or stereo audio both supported

2. **File Format**
   - MP3 and WAV are most reliable
   - Avoid heavily compressed formats
   - Test with different formats if accuracy is low

3. **Error Handling**
   - Always validate file size before upload
   - Implement retry logic for network errors
   - Show clear error messages to users

4. **User Experience**
   - Show loading indicator during transcription
   - Display file size and format before upload
   - Allow cancellation for long-running requests

## Common Use Cases

### 1. Voice Notes
```typescript
// Record and transcribe voice notes
async function recordAndTranscribe() {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  const mediaRecorder = new MediaRecorder(stream);
  const chunks: Blob[] = [];
  
  mediaRecorder.ondataavailable = (e) => chunks.push(e.data);
  mediaRecorder.onstop = async () => {
    const blob = new Blob(chunks, { type: 'audio/webm' });
    const file = new File([blob], 'recording.webm');
    const text = await transcribeAudio(file);
    console.log('Transcription:', text);
  };
  
  mediaRecorder.start();
  // Stop after 5 seconds
  setTimeout(() => mediaRecorder.stop(), 5000);
}
```

### 2. Interview Transcription
```python
# Transcribe interview recordings
async def transcribe_interview(audio_path: str) -> dict:
    text = await transcribe_audio(audio_path)
    
    return {
        "transcript": text,
        "word_count": len(text.split()),
        "timestamp": datetime.now().isoformat()
    }
```

### 3. Meeting Notes
```typescript
// Transcribe meeting recordings and save as notes
async function transcribeMeeting(audioFile: File) {
  const text = await transcribeAudio(audioFile);
  
  // Save to local storage or send to backend
  localStorage.setItem('meeting-notes', JSON.stringify({
    date: new Date().toISOString(),
    transcript: text
  }));
  
  return text;
}
```

## Troubleshooting

### Audio not transcribing
- Check audio file format is supported
- Verify file size is under 25MB
- Ensure audio contains speech (not just music/noise)
- Try converting to MP3 or WAV format

### Rate limit errors
- Wait 60 seconds before retrying
- Implement exponential backoff
- Consider caching transcriptions

### Server connection errors
- Verify server is running: `curl http://localhost:8000/health`
- Check firewall settings
- Ensure correct API endpoint URL

### Poor transcription quality
- Use higher quality audio (less compression)
- Reduce background noise
- Speak clearly and at moderate pace
- Use external microphone for recordings

## API Versioning

This is a **v2 API endpoint**. It includes:
- Improved error handling
- Better validation
- Consistent response format
- Rate limiting

## Security Considerations

1. **File Validation**
   - File type validation by extension
   - File size limits enforced
   - No executable files accepted

2. **Rate Limiting**
   - Prevents abuse
   - Per-client IP restrictions
   - Configurable limits

3. **Data Privacy**
   - Audio files not stored permanently
   - Transcriptions processed in memory
   - No data retention

## Related APIs

- **Text-to-Speech (Pronunciation)**: `/api/v2/pronunciation`
- **Words Explanation**: `/api/v2/words-explanation`
- **Text Simplification**: `/api/v2/simplify`

## Support

For issues or questions:
1. Check the API documentation
2. Review error messages carefully
3. Test with the provided HTML client
4. Check server logs for detailed errors

## Changelog

### Version 2.0
- Initial release of voice-to-text API
- Support for multiple audio formats
- Integration with OpenAI Whisper
- Comprehensive error handling
- Rate limiting implementation

## License

Part of the Caten API project.





