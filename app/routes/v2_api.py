"""API routes for v2 endpoints of the FastAPI application."""

import json
import os
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Request, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
import structlog

from app.config import settings
from app.models import (
    WordWithLocation,
    WordInfo
)
from app.services.text_service import text_service
from app.services.llm.open_ai import openai_service
from app.services.rate_limiter import rate_limiter
from app.exceptions import FileValidationError, ValidationError
from pydantic import BaseModel, Field

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v2", tags=["API v2"])


# V2-specific models
class WordsExplanationV2Request(BaseModel):
    """Request model for v2 words explanation with textStartIndex."""
    
    textStartIndex: int = Field(..., ge=0, description="Starting index of the text in the original document")
    text: str = Field(..., min_length=1, max_length=10000, description="Input text to analyze")
    important_words_location: List[WordWithLocation] = Field(..., min_items=1, max_items=10, description="List of important word locations")


class WordsExplanationV2Response(BaseModel):
    """Response model for v2 words explanation."""
    
    word_info: WordInfo = Field(..., description="Word information with textStartIndex")


class SimplifyRequest(BaseModel):
    """Request model for text simplification."""
    
    textStartIndex: int = Field(..., ge=0, description="Starting index of the text in the original document")
    textLength: int = Field(..., gt=0, description="Length of the text")
    text: str = Field(..., min_length=1, max_length=10000, description="Text to simplify")
    previousSimplifiedTexts: List[str] = Field(default=[], description="Previous simplified versions for context")


class SimplifyResponse(BaseModel):
    """Response model for text simplification."""
    
    textStartIndex: int = Field(..., description="Starting index of the text in the original document")
    textLength: int = Field(..., description="Length of the text")
    text: str = Field(..., description="Original text")
    previousSimplifiedTexts: List[str] = Field(..., description="Previous simplified versions")
    simplifiedText: str = Field(..., description="New simplified text")


class ImportantWordsV2Request(BaseModel):
    """Request model for v2 important words with textStartIndex."""
    
    textStartIndex: int = Field(..., ge=0, description="Starting index of the text in the original document")
    text: str = Field(..., min_length=1, max_length=10000, description="Input text to analyze")


class ImportantWordsV2Response(BaseModel):
    """Response model for v2 important words."""
    
    textStartIndex: int = Field(..., description="Starting index of the text in the original document")
    text: str = Field(..., description="Original input text")
    important_words_location: List[WordWithLocation] = Field(..., description="List of important word locations")


class ChatMessage(BaseModel):
    """Model for chat message in ask API."""
    
    role: str = Field(..., description="Role of the message sender (user/assistant)")
    content: str = Field(..., description="Content of the message")


class AskRequest(BaseModel):
    """Request model for ask API."""
    
    question: str = Field(..., min_length=1, max_length=2000, description="User's question")
    chat_history: List[ChatMessage] = Field(default=[], description="Previous chat history for context")
    initial_context: Optional[str] = Field(default=None, max_length=10000, description="Initial context or background information that the AI should be aware of")


class AskResponse(BaseModel):
    """Response model for ask API."""
    
    chat_history: List[ChatMessage] = Field(..., description="Updated chat history including the new Q&A")


async def get_client_id(request: Request) -> str:
    """Get client identifier for rate limiting."""
    # Use IP address as client ID (in production, you might use authenticated user ID)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host


@router.post(
    "/words-explanation",
    summary="Get word explanations with streaming (v2)",
    description="Provide contextual meaning + 2 simplified example sentences for each important word via Server-Sent Events. Accepts array of text objects with textStartIndex."
)
async def words_explanation_v2(
    request: Request,
    body: List[WordsExplanationV2Request]
):
    """Stream word explanations as they become available for multiple text objects."""
    client_id = await get_client_id(request)
    await rate_limiter.check_rate_limit(client_id, "words-explanation")
    
    async def generate_explanations():
        """Generate SSE stream of word explanations."""
        try:
            for text_obj in body:
                # Process each text object
                async for word_info in text_service.get_words_explanations_stream(
                    text_obj.text, 
                    text_obj.important_words_location
                ):
                    # Create response with textStartIndex
                    response_data = {
                        "word_info": {
                            "textStartIndex": text_obj.textStartIndex,
                            "location": word_info.location.model_dump(),
                            "word": word_info.word,
                            "meaning": word_info.meaning,
                            "examples": word_info.examples
                        }
                    }
                    
                    # Send SSE event for this individual word
                    event_data = f"data: {json.dumps(response_data)}\n\n"
                    yield event_data
            
            # Send final completion event
            yield "data: [DONE]\n\n"
            
        except Exception as e:
            logger.error("Error in words explanation v2 stream", error=str(e))
            error_event = {
                "error_code": "STREAM_001",
                "error_message": str(e)
            }
            yield f"data: {json.dumps(error_event)}\n\n"
    
    logger.info("Starting word explanations v2 stream", 
               text_objects_count=len(body),
               total_words=sum(len(obj.important_words_location) for obj in body))
    
    return StreamingResponse(
        generate_explanations(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )


@router.post(
    "/simplify",
    response_model=List[SimplifyResponse],
    summary="Simplify text with context (v2)",
    description="Generate simplified versions of texts using OpenAI API with previous context"
)
async def simplify_v2(
    request: Request,
    body: List[SimplifyRequest]
):
    """Simplify multiple texts with context from previous simplifications."""
    client_id = await get_client_id(request)
    await rate_limiter.check_rate_limit(client_id, "simplify")
    
    try:
        results = []
        
        for text_obj in body:
            # Generate simplified text using OpenAI
            simplified_text = await openai_service.simplify_text(
                text_obj.text, 
                text_obj.previousSimplifiedTexts
            )
            
            result = SimplifyResponse(
                textStartIndex=text_obj.textStartIndex,
                textLength=text_obj.textLength,
                text=text_obj.text,
                previousSimplifiedTexts=text_obj.previousSimplifiedTexts,
                simplifiedText=simplified_text
            )
            results.append(result)
        
        logger.info("Successfully simplified texts", count=len(results))
        return results
        
    except Exception as e:
        logger.error("Failed to simplify texts", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to simplify texts: {str(e)}")


@router.post(
    "/important-words-from-text",
    response_model=ImportantWordsV2Response,
    summary="Get important words from text (v2)",
    description="Identify top 10 most important/difficult words in a paragraph with textStartIndex"
)
async def important_words_from_text_v2(
    request: Request,
    body: ImportantWordsV2Request
):
    """Extract important words from text with textStartIndex."""
    client_id = await get_client_id(request)
    await rate_limiter.check_rate_limit(client_id, "important-words-from-text")
    
    # Extract important words using existing service
    word_with_locations = await text_service.extract_important_words(body.text)
    
    logger.info("Successfully extracted important words v2", 
               text_length=len(body.text), 
               words_count=len(word_with_locations),
               textStartIndex=body.textStartIndex)
    
    return ImportantWordsV2Response(
        textStartIndex=body.textStartIndex,
        text=body.text,
        important_words_location=word_with_locations
    )


@router.post(
    "/ask",
    response_model=AskResponse,
    summary="Contextual Q&A (v2)",
    description="Ask questions with full chat history context and optional initial context for ongoing conversations. Provide initial context to give the AI background information about a topic."
)
async def ask_v2(
    request: Request,
    body: AskRequest
):
    """Handle contextual Q&A with chat history."""
    client_id = await get_client_id(request)
    await rate_limiter.check_rate_limit(client_id, "ask")
    
    try:
        # Generate answer using OpenAI with chat history and initial context
        answer = await openai_service.generate_contextual_answer(
            body.question, 
            body.chat_history,
            body.initial_context
        )
        
        # Update chat history
        updated_history = body.chat_history.copy()
        updated_history.append(ChatMessage(role="user", content=body.question))
        updated_history.append(ChatMessage(role="assistant", content=answer))
        
        logger.info("Successfully generated contextual answer", 
                   question_length=len(body.question),
                   chat_history_length=len(updated_history))
        
        return AskResponse(
            chat_history=updated_history
        )
        
    except Exception as e:
        logger.error("Failed to generate contextual answer", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to generate answer: {str(e)}")
