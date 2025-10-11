# 🎵 Word Pronunciation API

> Generate high-quality audio pronunciation for any word using OpenAI's Text-to-Speech with a sweet-toned American female voice.

## 🚀 Quick Start (30 seconds)

```bash
# 1. Start the server
python app/main.py

# 2. Test it (choose one):

# Option A: Web interface (easiest)
open test_pronunciation_api.html

# Option B: Command line
python test_pronunciation_client.py hello

# Option C: cURL
curl -X POST http://localhost:8000/api/v2/pronunciation \
  -H "Content-Type: application/json" \
  -d '{"word": "hello", "voice": "nova"}' \
  --output hello.mp3 && mpv hello.mp3
```

## 📋 API Overview

**Endpoint:** `POST /api/v2/pronunciation`

**Request:**
```json
{
  "word": "pronunciation",
  "voice": "nova"
}
```

**Response:** MP3 audio file (5-20 KB)

**Default Voice:** Nova (sweet-toned American female) 🎤

## 🗣️ Available Voices

| Voice | Type | Accent | Description |
|-------|------|--------|-------------|
| **nova** ⭐ | Female | American | Sweet-toned, clear (Default) |
| shimmer | Female | American | Soft, gentle |
| alloy | Neutral | American | Balanced, versatile |
| echo | Male | American | Natural male voice |
| fable | Male | British | British English accent |
| onyx | Male | American | Deep, authoritative |

## 📖 Documentation

| Document | Purpose |
|----------|---------|
| **[PRONUNCIATION_API.md](PRONUNCIATION_API.md)** | Complete API reference, integration examples |
| **[PRONUNCIATION_API_SUMMARY.md](PRONUNCIATION_API_SUMMARY.md)** | Quick start guide, testing instructions |
| **[IMPLEMENTATION_COMPLETE.md](IMPLEMENTATION_COMPLETE.md)** | Technical details, implementation summary |

## 🧪 Testing Tools

### 1. Web Interface (Recommended)
```bash
open test_pronunciation_api.html
```
- Beautiful UI with quick test buttons
- Live audio playback
- Download functionality
- Voice selection dropdown

### 2. Python CLI
```bash
# Basic usage
python test_pronunciation_client.py hello

# Multiple words
python test_pronunciation_client.py hello world beautiful

# Different voice
python test_pronunciation_client.py serendipity --voice shimmer

# Save to directory
python test_pronunciation_client.py hello --output ./audio/
```

### 3. API Docs
Visit http://localhost:8000/docs after starting the server

## 💻 Integration Examples

### JavaScript
```javascript
async function pronounce(word) {
  const res = await fetch('http://localhost:8000/api/v2/pronunciation', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({word, voice: 'nova'})
  });
  const blob = await res.blob();
  new Audio(URL.createObjectURL(blob)).play();
}
```

### Python
```python
import requests

def get_audio(word):
    r = requests.post('http://localhost:8000/api/v2/pronunciation',
                      json={'word': word, 'voice': 'nova'})
    return r.content
```

### React Component
```jsx
function PronounceButton({word}) {
  const play = async () => {
    const res = await fetch('http://localhost:8000/api/v2/pronunciation', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({word, voice: 'nova'})
    });
    const blob = await res.blob();
    new Audio(URL.createObjectURL(blob)).play();
  };
  return <button onClick={play}>🔊 Pronounce</button>;
}
```

## ⚙️ Features

- ✅ High-quality OpenAI TTS
- ✅ Multiple voice options
- ✅ MP3 format (universal support)
- ✅ Fast response (~1-2s)
- ✅ Rate limiting (60/min)
- ✅ 24-hour cache headers
- ✅ CORS enabled
- ✅ Error handling
- ✅ Logging & monitoring

## 📊 Rate Limiting

- **Limit:** 60 requests per minute per IP
- **Resets:** Every 60 seconds
- **Headers:** Standard rate limit headers included
- **Tip:** Implement client-side caching for common words

## 🎯 Use Cases

- 📚 Language learning apps
- 📖 E-readers with TTS
- ♿ Accessibility features
- 🎓 Educational platforms
- 📱 Dictionary applications
- 🗣️ Speech training tools
- 🎮 Interactive learning games
- 📝 Note-taking apps with pronunciation

## 🔧 Technical Details

**Model:** OpenAI TTS-1 (optimized for speed)  
**Format:** MP3 (audio/mpeg)  
**Quality:** High-quality, clear pronunciation  
**Size:** 5-20 KB per word  
**Latency:** 1-2 seconds typical  
**Cache:** 24-hour browser cache  

## 🛠️ Setup Requirements

1. **Environment Variable:**
   ```bash
   export OPENAI_API_KEY='your-openai-api-key'
   ```

2. **Dependencies:**
   Already in `requirements.txt`:
   - openai
   - fastapi
   - pydantic

3. **Start Server:**
   ```bash
   python app/main.py
   ```

## 📁 File Structure

```
pronunciation-api/
├── app/
│   ├── routes/
│   │   └── v2_api.py              # API endpoint
│   └── services/
│       └── llm/
│           └── open_ai.py         # TTS service
├── test_pronunciation_api.html    # Web test UI
├── test_pronunciation_client.py   # CLI test tool
├── PRONUNCIATION_API.md           # Full API docs
├── PRONUNCIATION_API_SUMMARY.md   # Quick guide
└── IMPLEMENTATION_COMPLETE.md     # Tech details
```

## 🐛 Troubleshooting

**Server won't start:**
- Check OpenAI API key is set
- Run: `pip install -r requirements.txt`

**Audio not playing:**
- Check browser console for errors
- Verify CORS is working
- Ensure server is on port 8000

**Rate limit errors:**
- Wait 60 seconds
- Implement caching
- Consider batching requests

**Quality issues:**
- Voice quality depends on OpenAI TTS
- Try different voices
- Consider using TTS-1-HD model (code change needed)

## 💡 Best Practices

1. **Cache Aggressively**
   ```javascript
   const cache = new Map();
   async function getCached(word) {
     if (!cache.has(word)) {
       cache.set(word, await fetchPronunciation(word));
     }
     return cache.get(word);
   }
   ```

2. **Preload Common Words**
   ```javascript
   const common = ['hello', 'world', 'thank', 'you'];
   common.forEach(word => getCached(word));
   ```

3. **Handle Errors**
   ```javascript
   try {
     await playPronunciation(word);
   } catch (err) {
     console.error('Pronunciation failed:', err);
     // Show fallback UI
   }
   ```

4. **Rate Limit Client-Side**
   ```javascript
   const queue = new RateLimiter(50); // 50/min client-side
   await queue.schedule(() => pronounce(word));
   ```

## 📈 Performance Tips

- Cache audio blobs in memory/localStorage
- Preload pronunciations for visible words
- Use service workers for offline support
- Implement request debouncing
- Batch similar requests when possible

## 🎓 Learning Resources

- [OpenAI TTS Documentation](https://platform.openai.com/docs/guides/text-to-speech)
- [FastAPI Response Types](https://fastapi.tiangolo.com/advanced/custom-response/)
- [Web Audio API](https://developer.mozilla.org/en-US/docs/Web/API/Web_Audio_API)

## 🤝 Contributing

Found a bug or have a suggestion? 
- Check existing issues
- Create a new issue with details
- Or submit a pull request

## 📜 License

Same as the main Caten project.

---

## 🎉 You're Ready!

The pronunciation API is fully functional and ready to use. Pick your testing method and give it a try!

**Need help?** Check the full documentation in [PRONUNCIATION_API.md](PRONUNCIATION_API.md)

**Want to dive deep?** Read [IMPLEMENTATION_COMPLETE.md](IMPLEMENTATION_COMPLETE.md)

**Quick start?** Read [PRONUNCIATION_API_SUMMARY.md](PRONUNCIATION_API_SUMMARY.md)

---

Made with ❤️ using OpenAI's TTS API

