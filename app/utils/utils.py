from typing import List, Dict
from fastapi import Request


def get_start_index_and_length_for_words_from_text(
        text: str,
        words: List[str]
) -> List[Dict]:
    result = []
    start_pos = 0

    for word in words:
        # Find the word starting from the current search position
        index = text.find(word, start_pos)
        if index == -1:
            pass  # ignore if wrong word was generated

        result.append({
            "word": word,
            "index": index,
            "length": len(word)
        })

        # Move search start beyond this word to avoid matching earlier occurrences again
        start_pos = index + len(word)

    return result


def get_client_ip(request: Request) -> str:
    """Extract client IP address from request headers.
    
    Checks headers in order:
    1. X-Forwarded-For (for proxied requests)
    2. X-Real-IP (alternative proxy header)
    3. request.client.host (direct connection)
    
    Args:
        request: FastAPI Request object
        
    Returns:
        Client IP address as string
    """
    # Check X-Forwarded-For header (most common for proxied requests)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # X-Forwarded-For can contain multiple IPs, take the first one
        return forwarded_for.split(",")[0].strip()
    
    # Check X-Real-IP header (alternative proxy header)
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    
    # Fall back to direct client connection
    if request.client:
        return request.client.host
    
    # Last resort fallback
    return "unknown"
