# WebSocket API Documentation

## Words Explanation WebSocket Endpoint

The `/words-explanation-v2` WebSocket endpoint provides real-time streaming of word explanations, implementing the same business logic as the REST API `/words-explanation` endpoint but with WebSocket communication for better real-time experience.

### Endpoint

```
ws://localhost:8000/api/v1/words-explanation-v2
```

### Request Format

Send a JSON message with the following structure:

```json
{
    "text": "Your text here with difficult words",
    "important_words_location": [
        {
            "word": "serendipitous",
            "index": 4,
            "length": 13
        },
        {
            "word": "manuscript", 
            "index": 35,
            "length": 10
        }
    ]
}
```

### Response Format

The server will send individual word explanations as they become available:

```json
{
    "word_info": {
        "location": {
            "word": "serendipitous",
            "index": 4,
            "length": 13
        },
        "word": "serendipitous",
        "meaning": "occurring or discovered by chance in a happy or beneficial way",
        "examples": [
            "The serendipitous meeting led to a lifelong friendship.",
            "Her serendipitous discovery of the old book changed everything."
        ]
    }
}
```

### Completion Message

When all word explanations are sent, the server sends a completion message:

```json
{
    "status": "completed",
    "message": "All word explanations have been sent"
}
```

### Error Messages

If an error occurs, the server sends an error message:

```json
{
    "error_code": "VALIDATION_001",
    "error_message": "Invalid request data: Field required"
}
```

### Error Codes

- `VALIDATION_001`: Invalid request data format
- `STREAM_001`: Error during word explanation generation
- `WEBSOCKET_001`: General WebSocket error

### Usage Examples

#### Python Client

```python
import asyncio
import json
import websockets

async def test_websocket():
    async with websockets.connect("ws://localhost:8000/api/v1/words-explanation-v2") as websocket:
        request_data = {
            "text": "Your text here",
            "important_words_location": [
                {"word": "example", "index": 0, "length": 7}
            ]
        }
        
        await websocket.send(json.dumps(request_data))
        
        async for message in websocket:
            data = json.loads(message)
            if "word_info" in data:
                print(f"Word: {data['word_info']['word']}")
                print(f"Meaning: {data['word_info']['meaning']}")
            elif data.get("status") == "completed":
                print("All explanations received!")
                break
```

#### JavaScript Client

```javascript
const websocket = new WebSocket('ws://localhost:8000/api/v1/words-explanation-v2');

websocket.onopen = function(event) {
    const requestData = {
        text: "Your text here",
        important_words_location: [
            {word: "example", index: 0, length: 7}
        ]
    };
    websocket.send(JSON.stringify(requestData));
};

websocket.onmessage = function(event) {
    const data = JSON.parse(event.data);
    if (data.word_info) {
        console.log(`Word: ${data.word_info.word}`);
        console.log(`Meaning: ${data.word_info.meaning}`);
    } else if (data.status === 'completed') {
        console.log('All explanations received!');
    }
};
```

### Rate Limiting

The WebSocket endpoint uses the same rate limiting as the REST API. Rate limits are applied per client IP address.

### Connection Management

- The WebSocket connection will be automatically closed after sending all word explanations
- Clients should handle connection disconnection gracefully
- The server will close the connection if an error occurs during processing

### Testing

Use the provided example clients to test the WebSocket endpoint:

1. **Python client**: `python example_websocket_client.py`
2. **Web client**: Open `example_websocket_client.html` in a browser

Make sure the server is running on `localhost:8000` before testing.
