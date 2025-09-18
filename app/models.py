"""Pydantic models for request/response validation."""

from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class ErrorResponse(BaseModel):
    """Standard error response model."""
    
    error_code: str = Field(..., description="Error code identifier")
    error_message: str = Field(..., description="Human-readable error message")


class WordWithLocation(BaseModel):
    """Model for word location in text."""

    word: str = Field(..., description="The actual word")
    index: int = Field(..., ge=0, description="Starting index of the word in the text")
    length: int = Field(..., gt=0, description="Length of the word")


class ImportantWordsRequest(BaseModel):
    """Request model for getting important words from text."""
    
    text: str = Field(..., min_length=1, max_length=10000, description="Input text to analyze")


class ImportantWordsResponse(BaseModel):
    """Response model for important words extraction."""
    
    text: str = Field(..., description="Original input text")
    important_words_location: List[WordWithLocation] = Field(..., description="List of important word locations")


class WordInfo(BaseModel):
    """Model for word information including meaning and examples."""
    
    location: WordWithLocation = Field(..., description="Word location in original text")
    word: str = Field(..., description="The actual word")
    meaning: str = Field(..., description="Simplified meaning of the word")
    examples: List[str] = Field(..., min_items=2, max_items=2, description="Two example sentences")


class WordsExplanationRequest(BaseModel):
    """Request model for getting word explanations."""
    
    text: str = Field(..., min_length=1, max_length=10000, description="Original text")
    important_words_location: List[WordWithLocation] = Field(..., min_items=1, max_items=10, description="List of important word locations")


class WordsExplanationResponse(BaseModel):
    """Response model for word explanations."""
    
    text: str = Field(..., description="Original input text")
    words_info: List[WordInfo] = Field(..., description="List of word information")


class MoreExplanationsRequest(BaseModel):
    """Request model for getting more explanations."""
    
    word: str = Field(..., min_length=1, max_length=100, description="The word to get more examples for")
    meaning: str = Field(..., min_length=1, max_length=1000, description="Current meaning of the word")
    examples: List[str] = Field(..., min_items=2, max_items=2, description="Current example sentences")


class MoreExplanationsResponse(BaseModel):
    """Response model for more explanations."""
    
    word: str = Field(..., description="The word")
    meaning: str = Field(..., description="The meaning of the word")
    examples: List[str] = Field(..., min_items=4, max_items=4, description="Four example sentences (2 original + 2 new)")


class ImageToTextResponse(BaseModel):
    """Response model for image to text conversion."""
    
    text: str = Field(..., description="Extracted text from the image")


class HealthCheckResponse(BaseModel):
    """Response model for health check."""
    
    status: str = Field(..., description="Service status")
    version: str = Field(..., description="API version")
    timestamp: str = Field(..., description="Current timestamp")
