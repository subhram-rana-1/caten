"""API routes for the FastAPI application."""

import json
import os
from typing import List
from fastapi import APIRouter, UploadFile, File, Request, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
import structlog

from app.config import settings
from app.models import (
    ImageToTextResponse,
    ImportantWordsRequest,
    ImportantWordsResponse,
    WordsExplanationRequest,
    WordsExplanationResponse,
    MoreExplanationsRequest,
    MoreExplanationsResponse,
    WordInfo,
    RandomParagraphResponse
)
from app.services.image_service import image_service
from app.services.text_service import text_service
from app.services.llm.open_ai import openai_service
from app.services.rate_limiter import rate_limiter
from app.exceptions import FileValidationError, ValidationError

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1", tags=["API"])


async def get_client_id(request: Request) -> str:
    """Get client identifier for rate limiting."""
    # Use IP address as client ID (in production, you might use authenticated user ID)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host


@router.post(
    "/image-to-text",
    response_model=ImageToTextResponse,
    summary="Extract text from image",
    description="Extract readable paragraph-like text from an uploaded image (jpeg, jpg, png, heic)"
)
async def image_to_text(
    request: Request,
    file: UploadFile = File(..., description="Image file to extract text from")
):
    """Extract text from an uploaded image."""
    client_id = await get_client_id(request)
    await rate_limiter.check_rate_limit(client_id, "image-to-text")
    
    if not file.filename:
        raise FileValidationError("No file uploaded")
    
    # Read file data
    file_data = await file.read()
    
    # Validate and process image
    processed_image_data, image_format = image_service.validate_image_file(file_data, file.filename)
    
    # Extract text using LLM
    extracted_text = await openai_service.extract_text_from_image(processed_image_data, image_format)
    
    logger.info("Successfully extracted text from image", filename=file.filename, text_length=len(extracted_text))
    
    return ImageToTextResponse(text=extracted_text)


@router.post(
    "/important-words-from-text",
    response_model=ImportantWordsResponse,
    summary="Get important words from text",
    description="Identify top 10 most important/difficult words in a paragraph"
)
async def important_words_from_text(
    request: Request,
    body: ImportantWordsRequest
):
    """Extract important words from text."""
    client_id = await get_client_id(request)
    await rate_limiter.check_rate_limit(client_id, "important-words-from-text")
    
    # Extract important words
    word_with_locations = await text_service.extract_important_words(body.text)
    
    logger.info("Successfully extracted important words", text_length=len(body.text), words_count=len(word_with_locations))
    
    return ImportantWordsResponse(
        text=body.text,
        important_words_location=word_with_locations
    )


@router.post(
    "/words-explanation",
    summary="Get word explanations with streaming",
    description="Provide contextual meaning + 2 simplified example sentences for each important word via Server-Sent Events"
)
async def words_explanation(
    request: Request,
    body: WordsExplanationRequest
):
    """Stream word explanations as they become available."""
    client_id = await get_client_id(request)
    await rate_limiter.check_rate_limit(client_id, "words-explanation")
    
    async def generate_explanations():
        """Generate SSE stream of word explanations."""
        try:
            async for word_info in text_service.get_words_explanations_stream(body.text, body.important_words_location):
                # Create response with only the current word info
                single_word_response = {
                    "word_info": word_info.model_dump()
                }

                # Send SSE event for this individual word
                event_data = f"data: {json.dumps(single_word_response)}\n\n"
                yield event_data
            
            # Send final completion event
            yield "data: [DONE]\n\n"
            
        except Exception as e:
            logger.error("Error in words explanation stream", error=str(e))
            error_event = {
                "error_code": "STREAM_001",
                "error_message": str(e)
            }
            yield f"data: {json.dumps(error_event)}\n\n"
    
    logger.info("Starting word explanations stream", text_length=len(body.text), words_count=len(body.important_words_location))
    
    return StreamingResponse(
        generate_explanations(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )


@router.websocket("/words-explanation-v2")
async def words_explanation_websocket(websocket: WebSocket):
    """WebSocket endpoint for streaming word explanations."""
    await websocket.accept()
    
    try:
        # Receive the request data
        data = await websocket.receive_text()
        request_data = json.loads(data)
        
        # Validate request data
        try:
            words_request = WordsExplanationRequest(**request_data)
        except Exception as e:
            error_response = {
                "error_code": "VALIDATION_001",
                "error_message": f"Invalid request data: {str(e)}"
            }
            await websocket.send_text(json.dumps(error_response))
            await websocket.close()
            return
        
        # Get client IP for rate limiting (WebSocket doesn't have Request object)
        client_ip = websocket.client.host if websocket.client else "unknown"
        await rate_limiter.check_rate_limit(client_ip, "words-explanation")
        
        logger.info("Starting WebSocket word explanations stream", 
                   text_length=len(words_request.text), 
                   words_count=len(words_request.important_words_location),
                   client_ip=client_ip)
        
        # Stream word explanations as they become available
        try:
            async for word_info in text_service.get_words_explanations_stream(
                words_request.text, 
                words_request.important_words_location
            ):
                # Create response with only the current word info
                single_word_response = {
                    "word_info": word_info.model_dump()
                }
                
                # Send WebSocket message for this individual word
                await websocket.send_text(json.dumps(single_word_response))
            
            # Send final completion message
            completion_response = {
                "status": "completed",
                "message": "All word explanations have been sent"
            }
            await websocket.send_text(json.dumps(completion_response))
            
        except Exception as e:
            logger.error("Error in WebSocket words explanation stream", error=str(e))
            error_response = {
                "error_code": "STREAM_001",
                "error_message": str(e)
            }
            await websocket.send_text(json.dumps(error_response))
    
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error("WebSocket error", error=str(e))
        try:
            error_response = {
                "error_code": "WEBSOCKET_001",
                "error_message": f"WebSocket error: {str(e)}"
            }
            await websocket.send_text(json.dumps(error_response))
        except:
            pass  # Client might have already disconnected
    finally:
        try:
            await websocket.close()
        except:
            pass  # Connection might already be closed


@router.post(
    "/get-more-explanations",
    response_model=MoreExplanationsResponse,
    summary="Get more examples for a word",
    description="Generate 2 additional, simpler example sentences for a given word"
)
async def get_more_explanations(
    request: Request,
    body: MoreExplanationsRequest
):
    """Generate additional examples for a word."""
    client_id = await get_client_id(request)
    await rate_limiter.check_rate_limit(client_id, "get-more-explanations")
    
    # Generate more examples
    all_examples = await text_service.get_more_examples(body.word, body.meaning, body.examples)
    
    logger.info("Successfully generated more examples", word=body.word, total_examples=len(all_examples))

    # f
    return MoreExplanationsResponse(
        word=body.word,
        meaning=body.meaning,
        examples=all_examples
    )


@router.get(
    "/get-random-paragraph",
    response_model=RandomParagraphResponse,
    summary="Generate random paragraph for vocabulary learning",
    description="Generate a random paragraph with configurable word count and difficulty level to help users improve vocabulary skills"
)
async def get_random_paragraph(request: Request):
    """Generate a random paragraph with difficult words for vocabulary learning."""
    client_id = await get_client_id(request)
    await rate_limiter.check_rate_limit(client_id, "get-random-paragraph")
    
    # Generate random paragraph using LLM
    generated_text = await openai_service.generate_random_paragraph(
        word_count=settings.random_paragraph_word_count,
        difficulty_percentage=settings.random_paragraph_difficulty_percentage
    )
    
    logger.info("Successfully generated random paragraph", 
               word_count=len(generated_text.split()),
               difficulty_percentage=settings.random_paragraph_difficulty_percentage)
    
    return RandomParagraphResponse(text=generated_text)


@router.get(
    "/health/llm",
    summary="Check LLM API health",
    description="Test OpenAI API connection and return detailed diagnostics"
)
async def llm_health_check(request: Request):
    """Check OpenAI API connection and return detailed diagnostics."""
    try:
        # Test OpenAI connection
        is_connected = await openai_service.test_connection()

        # Get configuration info (without exposing sensitive data)
        api_key_configured = bool(settings.openai_api_key)
        api_key_format_valid = (
            settings.openai_api_key.startswith('sk-')
            if settings.openai_api_key else False
        )

        # Create response with diagnostics
        response_data = {
            "status": "healthy" if is_connected else "unhealthy",
            "openai_connection": is_connected,
            "diagnostics": {
                "api_key_configured": api_key_configured,
                "api_key_format_valid": api_key_format_valid,
                "api_key_length": len(settings.openai_api_key) if settings.openai_api_key else 0,
                "api_key_preview": f"{settings.openai_api_key[:10]}...{settings.openai_api_key[-4:]}" if settings.openai_api_key and len(settings.openai_api_key) > 14 else "***",
                "models_configured": {
                    "gpt4_turbo": settings.gpt4_turbo_model,
                    "gpt4o": settings.gpt4o_model
                },
                "timeout_settings": {
                    "connection_timeout": 30.0,
                    "read_timeout": 90.0
                },
                "environment_vars_loaded": {
                    "openai_api_key": "OPENAI_API_KEY" in os.environ,
                    "gpt4_turbo_model": "GPT4_TURBO_MODEL" in os.environ,
                    "gpt4o_model": "GPT4O_MODEL" in os.environ
                }
            }
        }

        if is_connected:
            logger.info("LLM health check passed")
        else:
            logger.error("LLM health check failed")

        return response_data

    except Exception as e:
        logger.error("LLM health check error", error=str(e))
        return {
            "status": "error",
            "error": str(e),
            "error_type": type(e).__name__
        }
