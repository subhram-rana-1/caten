"""API routes for v2 endpoints of the FastAPI application."""

import json
import os
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Request, HTTPException, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.responses import StreamingResponse, Response
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
    shouldAllowSimplifyMore: bool = Field(..., description="Whether more simplification attempts are allowed")


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
    initial_context: Optional[str] = Field(default=None, max_length=100000, description="Initial context or background information that the AI should be aware of")


class AskResponse(BaseModel):
    """Response model for ask API."""
    
    chat_history: List[ChatMessage] = Field(..., description="Updated chat history including the new Q&A")


class PronunciationRequest(BaseModel):
    """Request model for word pronunciation API."""
    
    word: str = Field(..., min_length=1, max_length=100, description="Word to generate pronunciation for")
    voice: Optional[str] = Field(default="nova", description="Voice to use (alloy, echo, fable, onyx, nova, shimmer). Default is 'nova' for sweet-toned American female voice")


class VoiceToTextResponse(BaseModel):
    """Response model for voice-to-text API."""
    
    text: str = Field(..., description="Transcribed text from the audio")


class TranslateRequest(BaseModel):
    """Request model for translate API."""
    
    targetLangugeCode: str = Field(..., min_length=2, max_length=2, description="ISO 639-1 language code (e.g., 'EN', 'ES', 'FR', 'DE', 'HI')")
    texts: List[str] = Field(..., min_items=1, description="List of texts to translate")


class TranslateResponse(BaseModel):
    """Response model for translate API."""
    
    targetLangugeCode: str = Field(..., description="Target language code")
    translatedTexts: List[str] = Field(..., description="List of translated texts")


class SummariseRequest(BaseModel):
    """Request model for summarise API."""
    
    text: str = Field(..., min_length=1, max_length=50000, description="Text to summarize (can contain newline characters)")


class SummariseResponse(BaseModel):
    """Response model for summarise API."""
    
    summary: str = Field(..., description="Short, insightful summary of the input text")


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
                            "examples": word_info.examples,
                            "languageCode": word_info.languageCode
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
    summary="Simplify text with context (v2) - SSE",
    description="Generate simplified versions of texts using OpenAI API with previous context via Server-Sent Events"
)
async def simplify_v2(
    request: Request,
    body: List[SimplifyRequest]
):
    """Simplify multiple texts with context from previous simplifications using SSE."""
    client_id = await get_client_id(request)
    await rate_limiter.check_rate_limit(client_id, "simplify")
    
    async def generate_simplifications():
        """Generate SSE stream of simplified texts."""
        try:
            for text_obj in body:
                # Generate simplified text using OpenAI
                simplified_text = await openai_service.simplify_text(
                    text_obj.text, 
                    text_obj.previousSimplifiedTexts
                )
                
                # Calculate if more simplification attempts are allowed
                should_allow_simplify_more = len(text_obj.previousSimplifiedTexts) < settings.max_simplification_attempts
                
                result = SimplifyResponse(
                    textStartIndex=text_obj.textStartIndex,
                    textLength=text_obj.textLength,
                    text=text_obj.text,
                    previousSimplifiedTexts=text_obj.previousSimplifiedTexts,
                    simplifiedText=simplified_text,
                    shouldAllowSimplifyMore=should_allow_simplify_more
                )
                
                # Send SSE event for this individual simplification
                event_data = f"data: {json.dumps(result.model_dump())}\n\n"
                yield event_data
            
            # Send final completion event
            yield "data: [DONE]\n\n"
            
        except Exception as e:
            logger.error("Error in simplify v2 stream", error=str(e))
            error_event = {
                "error_code": "STREAM_002",
                "error_message": str(e)
            }
            yield f"data: {json.dumps(error_event)}\n\n"
    
    logger.info("Starting text simplifications v2 stream", 
               text_objects_count=len(body))
    
    return StreamingResponse(
        generate_simplifications(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )


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


@router.post(
    "/pronunciation",
    summary="Generate word pronunciation audio (v2)",
    description="Generate pronunciation audio for a single word using OpenAI TTS with a sweet-toned American female voice"
)
async def get_pronunciation(
    request: Request,
    body: PronunciationRequest
):
    """Generate pronunciation audio for a word."""
    client_id = await get_client_id(request)
    await rate_limiter.check_rate_limit(client_id, "pronunciation")
    
    try:
        # Validate voice parameter
        valid_voices = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]
        if body.voice and body.voice not in valid_voices:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid voice. Must be one of: {', '.join(valid_voices)}"
            )
        
        # Generate pronunciation audio
        audio_bytes = await openai_service.generate_pronunciation_audio(
            body.word,
            body.voice or "nova"
        )
        
        logger.info("Successfully generated pronunciation audio",
                   word=body.word,
                   voice=body.voice,
                   audio_size=len(audio_bytes))
        
        # Return audio file
        return Response(
            content=audio_bytes,
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": f'inline; filename="{body.word}_pronunciation.mp3"',
                "Cache-Control": "public, max-age=86400"  # Cache for 24 hours
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to generate pronunciation", word=body.word, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to generate pronunciation: {str(e)}")


@router.post(
    "/voice-to-text",
    response_model=VoiceToTextResponse,
    summary="Convert voice audio to text (v2)",
    description="Transcribe audio file to text using OpenAI Whisper. Automatically detects language. Supports various audio formats (mp3, mp4, mpeg, mpga, m4a, wav, webm). Use translate=true to translate non-English audio to English."
)
async def voice_to_text(
    request: Request,
    audio_file: UploadFile = File(..., description="Audio file to transcribe"),
    translate: bool = False
):
    """Convert voice audio to text using OpenAI Whisper.
    
    Args:
        audio_file: Audio file to transcribe
        translate: If True, translates non-English audio to English. If False (default), transcribes in original language.
    """
    client_id = await get_client_id(request)
    await rate_limiter.check_rate_limit(client_id, "voice-to-text")
    
    try:
        # Validate file type
        allowed_extensions = ["mp3", "mp4", "mpeg", "mpga", "m4a", "wav", "webm"]
        file_extension = audio_file.filename.split(".")[-1].lower() if audio_file.filename else ""
        
        if file_extension not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid audio format. Supported formats: {', '.join(allowed_extensions)}"
            )
        
        # Validate file size (max 25MB for Whisper API)
        audio_bytes = await audio_file.read()
        file_size_mb = len(audio_bytes) / (1024 * 1024)
        
        if file_size_mb > 25:
            raise HTTPException(
                status_code=400,
                detail=f"Audio file too large ({file_size_mb:.2f}MB). Maximum size is 25MB."
            )
        
        logger.info("Processing voice-to-text request",
                   filename=audio_file.filename,
                   file_size_mb=file_size_mb,
                   file_extension=file_extension,
                   translate=translate)
        
        # Transcribe audio using OpenAI Whisper
        transcribed_text = await openai_service.transcribe_audio(
            audio_bytes, 
            audio_file.filename,
            translate=translate
        )
        
        logger.info("Successfully transcribed audio",
                   filename=audio_file.filename,
                   text_length=len(transcribed_text),
                   translate=translate)
        
        return VoiceToTextResponse(text=transcribed_text)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to transcribe audio", 
                   filename=audio_file.filename if audio_file else "unknown",
                   error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to transcribe audio: {str(e)}")


@router.post(
    "/translate",
    response_model=TranslateResponse,
    summary="Translate texts to target language (v2)",
    description="Translate multiple texts to a target language using OpenAI. Supports various language codes (EN, ES, FR, DE, HI, JA, ZH, etc.)"
)
async def translate_v2(
    request: Request,
    body: TranslateRequest
):
    """Translate texts to the target language."""
    client_id = await get_client_id(request)
    await rate_limiter.check_rate_limit(client_id, "translate")
    
    try:
        # Validate target language code format (should be 2 uppercase letters)
        if not body.targetLangugeCode.isalpha() or len(body.targetLangugeCode) != 2:
            raise HTTPException(
                status_code=400,
                detail="Invalid target language code. Must be a 2-letter ISO 639-1 code (e.g., 'EN', 'ES', 'FR')"
            )
        
        # Validate texts are not empty
        if not body.texts or any(not text.strip() for text in body.texts):
            raise HTTPException(
                status_code=400,
                detail="Texts cannot be empty"
            )
        
        # Translate texts using OpenAI
        translated_texts = await openai_service.translate_texts(
            body.texts,
            body.targetLangugeCode.upper()
        )
        
        logger.info(
            "Successfully translated texts",
            target_language_code=body.targetLangugeCode,
            texts_count=len(body.texts),
            translated_count=len(translated_texts)
        )
        
        return TranslateResponse(
            targetLangugeCode=body.targetLangugeCode.upper(),
            translatedTexts=translated_texts
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to translate texts", 
                   target_language_code=body.targetLangugeCode,
                   texts_count=len(body.texts) if body.texts else 0,
                   error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to translate texts: {str(e)}")


@router.post(
    "/summarise",
    response_model=SummariseResponse,
    summary="Summarise text (v2)",
    description="Generate a short, insightful summary of the input text using OpenAI. The summary will be returned in the dominant language of the input text. If the text contains multiple languages, the summary will be in the language that appears most frequently (e.g., if 80% is German and 20% is English, the summary will be in German). The input text can contain newline characters."
)
async def summarise_v2(
    request: Request,
    body: SummariseRequest
):
    print(f'body ----> {body}')

    """Generate a short, insightful summary of the input text."""
    client_id = await get_client_id(request)
    await rate_limiter.check_rate_limit(client_id, "summerise")
    
    try:
        # Validate text is not empty
        if not body.text or not body.text.strip():
            raise HTTPException(
                status_code=400,
                detail="Text cannot be empty"
            )
        
        # Generate summary using OpenAI
        summary = await openai_service.summarise_text(body.text)
        
        logger.info(
            "Successfully generated summary",
            text_length=len(body.text),
            summary_length=len(summary)
        )
        
        return SummariseResponse(summary=summary)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to generate summary", 
                   text_length=len(body.text) if body.text else 0,
                   error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to generate summary: {str(e)}")
