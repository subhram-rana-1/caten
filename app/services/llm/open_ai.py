"""OpenAI service for LLM operations with improved error handling and diagnostics."""

import asyncio
import base64
import json
import re

import httpx
from typing import List, Dict, Any, Optional
from openai import AsyncOpenAI
import structlog
from PIL import Image
import io
from pydub import AudioSegment

from app.config import settings
from app.exceptions import LLMServiceError

logger = structlog.get_logger()


def get_language_name(language_code: Optional[str]) -> Optional[str]:
    """Convert language code to full language name for prompts.

    Args:
        language_code: ISO 639-1 language code (e.g., 'EN', 'FR', 'ES', 'DE', 'HI')

    Returns:
        Full language name (e.g., 'English', 'French', 'Spanish') or None if code is invalid/None
    """
    if not language_code:
        return None

    language_map = {
        "EN": "English",
        "ES": "Spanish",
        "FR": "French",
        "DE": "German",
        "HI": "Hindi",
        "JA": "Japanese",
        "ZH": "Chinese",
        "AR": "Arabic",
        "IT": "Italian",
        "PT": "Portuguese",
        "RU": "Russian",
        "KO": "Korean",
        "NL": "Dutch",
        "PL": "Polish",
        "TR": "Turkish",
        "VI": "Vietnamese",
        "TH": "Thai",
        "ID": "Indonesian",
        "CS": "Czech",
        "SV": "Swedish",
        "DA": "Danish",
        "NO": "Norwegian",
        "FI": "Finnish",
        "EL": "Greek",
        "HE": "Hebrew",
        "UK": "Ukrainian",
        "RO": "Romanian",
        "HU": "Hungarian",
    }

    return language_map.get(language_code.upper())


class OpenAIService:
    """Service for interacting with OpenAI models."""

    def __init__(self):
        try:
            # Check if API key is available
            if not settings.openai_api_key:
                logger.error("OpenAI API key is not set")
                raise LLMServiceError("OpenAI API key is not configured")

            # Validate API key format
            if not settings.openai_api_key.startswith('sk-'):
                logger.error("Invalid OpenAI API key format - should start with 'sk-'")
                raise LLMServiceError("Invalid OpenAI API key format")

            # Log key information (partial, for debugging)
            key_start = settings.openai_api_key[:10] if len(settings.openai_api_key) > 10 else "***"
            key_end = settings.openai_api_key[-4:] if len(settings.openai_api_key) > 4 else "***"
            logger.info(f"Initializing OpenAI client with API key: {key_start}...{key_end}")

            # Create HTTP client with SSL verification disabled for testing
            http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(60.0),
                verify=True,
                follow_redirects=True,
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5)
            )

            # Create the OpenAI client with custom HTTP client
            self.client = AsyncOpenAI(
                api_key=settings.openai_api_key,
                timeout=60.0,
                max_retries=2,
                http_client=http_client,
            )
            logger.info("OpenAI client initialized successfully with custom HTTP client")

        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {str(e)}")
            raise LLMServiceError(f"Failed to initialize OpenAI client: {str(e)}")

    async def test_connection(self) -> bool:
        """Test the OpenAI API connection."""
        try:
            logger.info("Testing OpenAI API connection...")

            # Simple test call to verify connection
            response = await self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=5,
                temperature=0
            )

            logger.info("OpenAI API connection test successful")
            return True

        except Exception as e:
            logger.error(f"OpenAI API connection test failed: {str(e)}")
            logger.error(f"Error type: {type(e).__name__}")

            # Log specific error details
            if hasattr(e, 'response'):
                logger.error(f"Response status: {e.response.status_code if e.response else 'No response'}")
            if hasattr(e, 'request'):
                logger.error(f"Request URL: {e.request.url if e.request else 'No request'}")

            return False

    async def extract_text_from_image(self, image_data: bytes, image_format: str) -> str:
        """Extract text from image using GPT-4 Turbo with Vision."""
        try:
            # Convert image to base64
            base64_image = base64.b64encode(image_data).decode('utf-8')

            # Prepare the message with image
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": """Extract all readable text from this image. The image might be a screenshot, scanned document, or similar. 
                            
                            Requirements:
                            - Return only the extracted text, no additional commentary
                            - Handle tilted/rotated images (±5°, 90°, 180°, etc.)
                            - Adjust for transparent overlays if text is still readable
                            - If no readable text is detected or the image is invalid, return 'NO_TEXT_DETECTED'
                            - Only process images that look like screenshots, scanned pages, or documents with text
                            - Organize the text in paragraph format when possible"""
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/{image_format};base64,{base64_image}"
                            }
                        }
                    ]
                }
            ]

            response = await self._make_api_call(
                model=settings.gpt4_turbo_model,
                messages=messages,
                max_tokens=settings.max_tokens,
                temperature=settings.temperature
            )

            extracted_text = response.choices[0].message.content.strip()

            if extracted_text == "NO_TEXT_DETECTED":
                raise LLMServiceError("No readable text detected in the image")

            logger.info("Successfully extracted text from image", text_length=len(extracted_text))
            return extracted_text

        except Exception as e:
            logger.error("Failed to extract text from image", error=str(e))
            if isinstance(e, LLMServiceError):
                raise
            raise LLMServiceError(f"Failed to process image: {str(e)}")

    async def get_important_words(self, text: str, language_code: Optional[str] = None) -> List[str]:
        """Get top 10 most important/difficult words from text in the order they appear."""
        try:
            # Build language requirement section (for response format, not content language)
            language_note = ""
            if language_code:
                language_name = get_language_name(language_code)
                if language_name:
                    language_note = f"\n\nNote: The text is in {language_name} ({language_code})."

            prompt = f"""
            Analyze the following text and identify the top 10 most important and contextually significant words.
            {language_note}

            Requirements:
            - Remove obvious stopwords (a, the, to, and, or, but, etc.)
            - Focus on content-heavy, contextually important words
            - Return words in order of decreasing importance
            - For each word, find its exact starting character index in the original text (0-based indexing)
            - The index must be calculated **based on the original raw character positions** in the text, including punctuation and whitespace
            - Also include the word's length in characters
            - Return the result as a JSON array with 10 objects, each containing: 'word', 'index', and 'length'

            Text:
            \"\"\"{text}\"\"\"

            Important:
            - All words must be present in the original text
            - If fewer than 10 important words are found, return as many as possible
            - Ensure the index corresponds to the first occurrence of the word in the text
            - If a word appears multiple times, use the index of its first occurrence
            - Do not approximate or guess the index — it must match the position in the original text exactly
            - Return only the JSON array. No explanation, no code blocks, no markdown formatting
            """

            response = await self._make_api_call(
                model=settings.gpt4o_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=settings.max_tokens,
                temperature=0.3
            )

            result = response.choices[0].message.content.strip()

            try:
                if result.startswith("```"):
                    result = re.sub(r"^```(?:json)?\n|\n```$", "", result.strip())

                words_data = json.loads(result)
                if not isinstance(words_data, list):
                    raise ValueError("Expected JSON array")

                # Validate entries
                validated_words = []
                for word_info in words_data[:10]:
                    if all(key in word_info for key in ['word', 'index', 'length']):
                        start_idx = word_info['index']
                        length = word_info['length']
                        if 0 <= start_idx < len(text) and start_idx + length <= len(text):
                            validated_words.append({
                                'word': word_info['word'],
                                'index': start_idx
                            })

                # Sort by index to ensure order of appearance in original text
                validated_words.sort(key=lambda w: w['index'])

                # Return only the words in order
                ordered_words = [w['word'].lower() for w in validated_words]

                logger.info("Successfully extracted important words", count=len(ordered_words))
                return ordered_words

            except json.JSONDecodeError as e:
                logger.error("Failed to parse LLM response as JSON", error=str(e), response=result)
                raise LLMServiceError("Failed to parse important words response")

        except Exception as e:
            logger.error("Failed to get important words", error=str(e))
            if isinstance(e, LLMServiceError):
                raise
            raise LLMServiceError(f"Failed to analyze text for important words: {str(e)}")

    async def get_word_explanation(self, word: str, context: str, language_code: Optional[str] = None) -> Dict[str, Any]:
        """Get explanation and examples for a single word in context."""
        try:
            # Build language requirement section
            language_requirement = ""
            if language_code:
                language_name = get_language_name(language_code)
                if language_name:
                    language_requirement = f"""
            CRITICAL LANGUAGE REQUIREMENT:
            - You MUST respond STRICTLY in {language_name} ({language_code})
            - The meaning and examples MUST be in {language_name} ONLY
            - Do NOT use any other language - ONLY {language_name}
            - This is MANDATORY and NON-NEGOTIABLE"""
                else:
                    language_requirement = f"""
            CRITICAL LANGUAGE REQUIREMENT:
            - You MUST respond STRICTLY in the language specified by code: {language_code.upper()}
            - The meaning and examples MUST be in this language ONLY
            - Do NOT use any other language"""
            else:
                language_requirement = """
            CRITICAL LANGUAGE REQUIREMENT:
            - You MUST detect the language of the input context and respond in the EXACT SAME LANGUAGE
            - If the context is in English, provide meaning and examples in English
            - If the context is in Hindi, provide meaning and examples in Hindi
            - If the context is in Spanish, provide meaning and examples in Spanish
            - This applies to ALL languages - always match the input language
            - Do NOT default to English - always match the language of the input context"""

            prompt = f"""Provide a simplified explanation and exactly 2 example sentences for the word "{word}" in the given context.

            Context: "{context}"
            Word: "{word}"
            {language_requirement}
            
            Requirements:
            - Provide a simple, clear meaning of the word as used in this context
            - Create exactly 2 simple example sentences showing how to use the word
            - Keep explanations accessible for language learners
            - Return the result as JSON with keys: 'meaning' and 'examples' (array of 2 strings)
            
            Return only the JSON object, no additional text."""

            response = await self._make_api_call(
                model=settings.gpt4o_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=settings.max_tokens,
                temperature=settings.temperature
            )

            result = response.choices[0].message.content.strip()

            # Parse the JSON response
            try:
                # Strip Markdown code block (e.g., ```json\n...\n```)
                if result.startswith("```"):
                    result = re.sub(r"^```(?:json)?\n|\n```$", "", result.strip())

                explanation_data = json.loads(result)
                if not all(key in explanation_data for key in ['meaning', 'examples']):
                    raise ValueError("Missing required keys")

                if not isinstance(explanation_data['examples'], list) or len(explanation_data['examples']) != 2:
                    raise ValueError("Examples must be a list of exactly 2 items")

                logger.info("Successfully got word explanation", word=word)
                return explanation_data

            except json.JSONDecodeError as e:
                logger.error("Failed to parse word explanation response", error=str(e), response=result)
                raise LLMServiceError("Failed to parse word explanation response")

        except Exception as e:
            logger.error("Failed to get word explanation", word=word, error=str(e))
            if isinstance(e, LLMServiceError):
                raise
            raise LLMServiceError(f"Failed to get explanation for word '{word}': {str(e)}")

    async def get_more_examples(self, word: str, meaning: str, existing_examples: List[str]) -> List[str]:
        """Generate 2 additional, simpler example sentences for a word."""
        try:
            existing_examples_text = "\n".join(f"- {ex}" for ex in existing_examples)

            prompt = f"""Generate exactly 2 additional, even simpler example sentences for the word "{word}".

            Word: "{word}"
            Meaning: "{meaning}"
            
            Existing examples:
            {existing_examples_text}
            
            CRITICAL LANGUAGE REQUIREMENT:
            - You MUST detect the language of the existing examples and respond in the EXACT SAME LANGUAGE
            - If the existing examples are in English, provide new examples in English
            - If the existing examples are in Hindi, provide new examples in Hindi
            - If the existing examples are in Spanish, provide new examples in Spanish
            - This applies to ALL languages - always match the language of the existing examples
            - Do NOT default to English - always match the language of the input
            
            Requirements:
            - Create exactly 2 NEW example sentences (different from existing ones)
            - Since the existing examples were hard to understand, make them simpler and more accessible
            - Show clear usage of the word in context
            - Keep sentences easy to understand
            - Return as a JSON array of exactly 2 strings
            
            Return only the JSON array, no additional text."""

            response = await self._make_api_call(
                model=settings.gpt4o_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=settings.max_tokens,
                temperature=settings.temperature
            )

            result = response.choices[0].message.content.strip()
            logger.debug("Raw response from OpenAI", result=result)

            # Strip Markdown code block (e.g., ```json\n...\n```)
            if result.startswith("```"):
                result = re.sub(r"^```(?:json)?\n|\n```$", "", result.strip())

            # Parse the JSON response
            new_examples = json.loads(result)

            if not isinstance(new_examples, list) or len(new_examples) != 2:
                logger.warning("Invalid response format from OpenAI", result=result)
                raise ValueError("Expected JSON array of exactly 2 items")

            logger.info("Successfully generated more examples", word=word)
            return new_examples

        except Exception as e:
            logger.error("Failed to get more examples", word=word, error=str(e))
            if isinstance(e, LLMServiceError):
                raise
            raise LLMServiceError(f"Failed to generate more examples for word '{word}': {str(e)}")

    async def generate_random_paragraph(self, word_count: int, difficulty_percentage: int) -> str:
        """Generate a random paragraph with specified word count and difficulty level."""
        try:
            prompt = f"""Generate a random paragraph with approximately {word_count} words where {difficulty_percentage}% of the words are difficult to understand (advanced vocabulary).

            Requirements:
            - Target approximately {word_count} words (don't worry about exact count)
            - {difficulty_percentage}% of words should be challenging/advanced vocabulary
            - The remaining {100 - difficulty_percentage}% should be common, easy words
            - Create a coherent, meaningful paragraph (not just a list of words)
            - Choose a random topic (science, literature, history, technology, etc.)
            - Make it educational and engaging for vocabulary learning
            - Return only the paragraph text, no additional commentary or formatting
            - Focus on natural flow and coherence rather than exact word count
            
            The paragraph should help users improve their vocabulary skills by encountering challenging words in context."""

            response = await self._make_api_call(
                model=settings.gpt4o_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=settings.max_tokens,
                temperature=0.8  # Higher temperature for more creative/random content
            )

            generated_text = response.choices[0].message.content.strip()
            
            # Count actual words for logging purposes only
            word_count_actual = len(generated_text.split())

            logger.info("Successfully generated random paragraph", 
                       word_count=word_count_actual, difficulty_percentage=difficulty_percentage)
            return generated_text

        except Exception as e:
            logger.error("Failed to generate random paragraph", error=str(e))
            if isinstance(e, LLMServiceError):
                raise
            raise LLMServiceError(f"Failed to generate random paragraph: {str(e)}")

    async def generate_random_paragraph_with_topics(self, topics: List[str], word_count: int, difficulty_percentage: int) -> str:
        """Generate a random paragraph with specified topics/keywords, word count and difficulty level."""
        try:
            # Build topics section for the prompt
            topics_section = ""
            if topics:
                topics_list = ", ".join(f'"{topic}"' for topic in topics)
                topics_section = f"""
            Topics/Keywords to include: {topics_list}
            - Incorporate these topics naturally into the paragraph
            - Use them as themes or central concepts
            - Make sure the paragraph revolves around these topics"""
            else:
                topics_section = """
            - Choose any random topic (science, literature, history, technology, nature, etc.)
            - Make it interesting and educational"""

            prompt = f"""Generate a random paragraph with approximately {word_count} words where {difficulty_percentage}% of the words are difficult to understand (advanced vocabulary).
            {topics_section}

            Requirements:
            - Target approximately {word_count} words (don't worry about exact count)
            - {difficulty_percentage}% of words should be challenging/advanced vocabulary
            - The remaining {100 - difficulty_percentage}% should be common, easy words
            - Create a coherent, meaningful paragraph (not just a list of words)
            - Make it educational and engaging for vocabulary learning
            - Return only the paragraph text, no additional commentary or formatting
            - Focus on natural flow and coherence rather than exact word count
            
            The paragraph should help users improve their vocabulary skills by encountering challenging words in context."""

            response = await self._make_api_call(
                model=settings.gpt4o_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=settings.max_tokens,
                temperature=0.8  # Higher temperature for more creative/random content
            )

            generated_text = response.choices[0].message.content.strip()
            
            # Count actual words for logging purposes only
            word_count_actual = len(generated_text.split())

            logger.info("Successfully generated random paragraph with topics", 
                       word_count=word_count_actual, 
                       difficulty_percentage=difficulty_percentage,
                       topics_count=len(topics),
                       topics=topics)
            return generated_text

        except Exception as e:
            logger.error("Failed to generate random paragraph with topics", error=str(e))
            if isinstance(e, LLMServiceError):
                raise
            raise LLMServiceError(f"Failed to generate random paragraph with topics: {str(e)}")

    async def _make_api_call(self, **kwargs):
        """Make an API call with robust error handling and retry logic."""
        max_retries = 3
        retry_delay = 2  # seconds

        for attempt in range(max_retries):
            try:
                logger.info("Making OpenAI API call", attempt=attempt + 1, max_retries=max_retries)

                response = await self.client.chat.completions.create(**kwargs)

                logger.info("OpenAI API call successful", response_id=response.id, attempt=attempt + 1)
                return response

            except Exception as api_error:
                print(f'api_error -----------> {api_error}')

                error_type = type(api_error).__name__
                error_msg = str(api_error)

                logger.error("OpenAI API call failed",
                            error=error_msg,
                            error_type=error_type,
                            attempt=attempt + 1)

                # Log additional error details
                if hasattr(api_error, 'response') and api_error.response:
                    logger.error(f"API Response status: {api_error.response.status_code}")
                    logger.error(f"API Response headers: {dict(api_error.response.headers)}")

                if hasattr(api_error, 'request') and api_error.request:
                    logger.error(f"Request URL: {api_error.request.url}")

                # Don't retry on certain error types
                if error_type in ['AuthenticationError', 'PermissionDeniedError', 'BadRequestError']:
                    logger.error(f"Non-retryable error: {error_type}")
                    raise LLMServiceError(f"API Error: {error_msg}")

                if attempt == max_retries - 1:
                    raise LLMServiceError(f"Connection error after {max_retries} attempts: {error_msg}")

                # Wait before retrying, except on the last attempt
                if attempt < max_retries - 1:
                    logger.info(f"Retrying in {retry_delay} seconds...", attempt=attempt + 1)
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff

    async def simplify_text(self, text: str, previous_simplified_texts: List[str], language_code: Optional[str] = None) -> str:
        """Simplify text using OpenAI with context from previous simplifications."""
        try:
            # Build context from previous simplifications
            context_section = ""
            if previous_simplified_texts:
                context_section = f"""
            Previous simplified versions for reference:
            {chr(10).join(f"- {simplified}" for simplified in previous_simplified_texts)}
            
            These previous versions are still too complex. Create a MUCH simpler version with:
            - Even shorter sentences (5-8 words maximum)
            - Even simpler words (basic vocabulary only)
            - More broken-up sentence structure
            - Avoid any complex phrases or grammar
            """
            else:
                context_section = """
            This is the first simplification attempt. Make it EXTREMELY simple with very short sentences and basic words.
            """

            # Build language requirement section
            if language_code:
                language_name = get_language_name(language_code)
                if language_name:
                    language_requirement = f"""
            CRITICAL LANGUAGE REQUIREMENT:
            - You MUST respond STRICTLY in {language_name} ({language_code})
            - The simplified text MUST be in {language_name} ONLY
            - Do NOT use any other language - ONLY {language_name}
            - This is MANDATORY and NON-NEGOTIABLE"""
                else:
                    language_requirement = f"""
            CRITICAL LANGUAGE REQUIREMENT:
            - You MUST respond STRICTLY in the language specified by code: {language_code.upper()}
            - The simplified text MUST be in this language ONLY
            - Do NOT use any other language"""
            else:
                language_requirement = """
            CRITICAL LANGUAGE REQUIREMENT:
            - You MUST detect the language of the input text and respond in the EXACT SAME LANGUAGE
            - If the input is in English, respond in English
            - If the input is in Hindi, respond in Hindi
            - If the input is in Spanish, respond in Spanish
            - This applies to ALL languages - always match the input language
            - Do NOT default to English - always match the language of the input text"""

            prompt = f"""Simplify the following text to make it EXTREMELY easy to understand. Use the simplest possible language and sentence structure.

            {context_section}

            Original text:
            "{text}"
            {language_requirement}

            CRITICAL REQUIREMENTS:
            - Use ONLY basic, everyday words (like "big" instead of "enormous", "old" instead of "ancient")
            - Write in VERY short, simple sentences (maximum 8-10 words per sentence)
            - Use simple sentence patterns: Subject + Verb + Object
            - Avoid complex grammar, clauses, and fancy words
            - Break long ideas into multiple short sentences
            - Use common words that a 10-year-old would understand
            - If previous simplified versions exist, make this one MUCH simpler with even shorter sentences
            - Replace complex phrases with simple ones (e.g., "as if" → "like", "in order to" → "to")
            - Use active voice instead of passive voice
            - Return only the simplified text, no additional commentary

            Simplified text:"""

            response = await self._make_api_call(
                model=settings.gpt4o_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=settings.max_tokens,
                temperature=0.3
            )

            simplified_text = response.choices[0].message.content.strip()
            
            logger.info("Successfully simplified text", 
                       original_length=len(text),
                       simplified_length=len(simplified_text),
                       has_previous_context=bool(previous_simplified_texts))
            
            return simplified_text

        except Exception as e:
            logger.error("Failed to simplify text", error=str(e))
            if isinstance(e, LLMServiceError):
                raise
            raise LLMServiceError(f"Failed to simplify text: {str(e)}")

    async def simplify_text_stream(self, text: str, previous_simplified_texts: List[str], language_code: Optional[str] = None):
        """Simplify text with streaming using OpenAI with context from previous simplifications.

        Yields chunks of simplified text as they are generated by OpenAI.
        """
        try:
            # Build context from previous simplifications
            context_section = ""
            if previous_simplified_texts:
                context_section = f"""
            Previous simplified versions for reference:
            {chr(10).join(f"- {simplified}" for simplified in previous_simplified_texts)}
            
            These previous versions are still too complex. Create a MUCH simpler version with:
            - Even shorter sentences (5-8 words maximum)
            - Even simpler words (basic vocabulary only)
            - More broken-up sentence structure
            - Avoid any complex phrases or grammar
            """
            else:
                context_section = """
            This is the first simplification attempt. Make it EXTREMELY simple with very short sentences and basic words.
            """

            # Build language requirement section
            if language_code:
                language_name = get_language_name(language_code)
                if language_name:
                    language_requirement = f"""
            CRITICAL LANGUAGE REQUIREMENT:
            - You MUST respond STRICTLY in {language_name} ({language_code})
            - The simplified text MUST be in {language_name} ONLY
            - Do NOT use any other language - ONLY {language_name}
            - This is MANDATORY and NON-NEGOTIABLE"""
                else:
                    language_requirement = f"""
            CRITICAL LANGUAGE REQUIREMENT:
            - You MUST respond STRICTLY in the language specified by code: {language_code.upper()}
            - The simplified text MUST be in this language ONLY
            - Do NOT use any other language"""
            else:
                language_requirement = """
            CRITICAL LANGUAGE REQUIREMENT:
            - You MUST detect the language of the input text and respond in the EXACT SAME LANGUAGE
            - If the input is in English, respond in English
            - If the input is in Hindi, respond in Hindi
            - If the input is in Spanish, respond in Spanish
            - This applies to ALL languages - always match the input language
            - Do NOT default to English - always match the language of the input text"""

            prompt = f"""Simplify the following text to make it EXTREMELY easy to understand. Use the simplest possible language and sentence structure.

            {context_section}

            Original text:
            "{text}"
            {language_requirement}

            CRITICAL REQUIREMENTS:
            - Use ONLY basic, everyday words (like "big" instead of "enormous", "old" instead of "ancient")
            - Write in VERY short, simple sentences (maximum 8-10 words per sentence)
            - Use simple sentence patterns: Subject + Verb + Object
            - Avoid complex grammar, clauses, and fancy words
            - Break long ideas into multiple short sentences
            - Use common words that a 10-year-old would understand
            - If previous simplified versions exist, make this one MUCH simpler with even shorter sentences
            - Replace complex phrases with simple ones (e.g., "as if" → "like", "in order to" → "to")
            - Use active voice instead of passive voice
            - Return only the simplified text, no additional commentary

            Simplified text:"""

            # Create streaming response
            stream = await self.client.chat.completions.create(
                model=settings.gpt4o_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=settings.max_tokens,
                temperature=0.3,
                stream=True
            )

            # Yield chunks as they arrive
            async for chunk in stream:
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if delta and delta.content:
                        yield delta.content

            logger.info("Successfully streamed simplified text",
                       original_length=len(text),
                       has_previous_context=bool(previous_simplified_texts))

        except Exception as e:
            logger.error("Failed to stream simplified text", error=str(e))
            if isinstance(e, LLMServiceError):
                raise
            raise LLMServiceError(f"Failed to stream simplified text: {str(e)}")

    async def generate_contextual_answer(self, question: str, chat_history: List, initial_context: Optional[str] = None, language_code: Optional[str] = None) -> str:
        """Generate contextual answer using chat history for ongoing conversations."""
        try:
            # Build messages from chat history
            messages = []
            
            # Build language requirement section
            if language_code:
                language_name = get_language_name(language_code)
                if language_name:
                    language_requirement = f"""
CRITICAL LANGUAGE REQUIREMENT:
- You MUST respond STRICTLY in {language_name} ({language_code})
- Your answer MUST be in {language_name} ONLY
- Do NOT use any other language - ONLY {language_name}
- This is MANDATORY and NON-NEGOTIABLE"""
                else:
                    language_requirement = f"""
CRITICAL LANGUAGE REQUIREMENT:
- You MUST respond STRICTLY in the language specified by code: {language_code.upper()}
- Your answer MUST be in this language ONLY
- Do NOT use any other language"""
            else:
                language_requirement = """
CRITICAL LANGUAGE REQUIREMENT:
- You MUST detect the language of the user's question and respond in the EXACT SAME LANGUAGE
- If the user asks in English, respond in English
- If the user asks in Hindi, respond in Hindi
- If the user asks in Spanish, respond in Spanish
- This applies to ALL languages - always match the user's input language
- The language of your response should dynamically change based on each question's language
- Do NOT default to English - always match the language of the current question"""
            
            # Add system message for context
            system_content = f"""You are a helpful AI assistant that provides clear, accurate, and contextual answers. Use the conversation history to maintain context and provide relevant responses.

{language_requirement}"""

            # Add initial context if provided
            if initial_context:
                system_content += f"\n\nInitial Context: {initial_context}\n\nPlease use this context to provide more informed and relevant answers to questions about this topic."
            
            messages.append({
                "role": "system", 
                "content": system_content
            })
            
            # Add chat history
            for message in chat_history:
                messages.append({
                    "role": message.role,
                    "content": message.content
                })
            
            # Add current question
            messages.append({
                "role": "user",
                "content": question
            })

            response = await self._make_api_call(
                model=settings.gpt4o_model,
                messages=messages,
                max_tokens=settings.max_tokens,
                temperature=0.7
            )

            answer = response.choices[0].message.content.strip()
            
            logger.info("Successfully generated contextual answer", 
                       question_length=len(question),
                       chat_history_length=len(chat_history),
                       answer_length=len(answer),
                       has_initial_context=bool(initial_context))
            
            return answer

        except Exception as e:
            logger.error("Failed to generate contextual answer", error=str(e))
            if isinstance(e, LLMServiceError):
                raise
            raise LLMServiceError(f"Failed to generate contextual answer: {str(e)}")

    async def generate_contextual_answer_stream(self, question: str, chat_history: List, initial_context: Optional[str] = None, language_code: Optional[str] = None):
        """Generate contextual answer with streaming using chat history for ongoing conversations.

        Yields chunks of text as they are generated by OpenAI.
        """
        try:
            # Build messages from chat history
            messages = []

            # Build language requirement section
            if language_code:
                language_name = get_language_name(language_code)
                if language_name:
                    language_requirement = f"""
CRITICAL LANGUAGE REQUIREMENT:
- You MUST respond STRICTLY in {language_name} ({language_code})
- Your answer MUST be in {language_name} ONLY
- Do NOT use any other language - ONLY {language_name}
- This is MANDATORY and NON-NEGOTIABLE"""
                else:
                    language_requirement = f"""
CRITICAL LANGUAGE REQUIREMENT:
- You MUST respond STRICTLY in the language specified by code: {language_code.upper()}
- Your answer MUST be in this language ONLY
- Do NOT use any other language"""
            else:
                language_requirement = """
CRITICAL LANGUAGE REQUIREMENT:
- You MUST detect the language of the user's question and respond in the EXACT SAME LANGUAGE
- If the user asks in English, respond in English
- If the user asks in Hindi, respond in Hindi
- If the user asks in Spanish, respond in Spanish
- This applies to ALL languages - always match the user's input language
- The language of your response should dynamically change based on each question's language
- Do NOT default to English - always match the language of the current question"""

            # Add system message for context
            system_content = f"""You are a helpful AI assistant that provides clear, accurate, and contextual answers. Use the conversation history to maintain context and provide relevant responses.

{language_requirement}"""

            # Add initial context if provided
            if initial_context:
                system_content += f"\n\nInitial Context: {initial_context}\n\nPlease use this context to provide more informed and relevant answers to questions about this topic."

            messages.append({
                "role": "system",
                "content": system_content
            })

            # Add chat history
            for message in chat_history:
                messages.append({
                    "role": message.role,
                    "content": message.content
                })

            # Add current question
            messages.append({
                "role": "user",
                "content": question
            })

            # Create streaming response
            stream = await self.client.chat.completions.create(
                model=settings.gpt4o_model,
                messages=messages,
                max_tokens=settings.max_tokens,
                temperature=0.7,
                stream=True
            )

            # Yield chunks as they arrive
            async for chunk in stream:
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if delta and delta.content:
                        yield delta.content

            logger.info("Successfully streamed contextual answer",
                       question_length=len(question),
                       chat_history_length=len(chat_history),
                       has_initial_context=bool(initial_context))

        except Exception as e:
            logger.error("Failed to stream contextual answer", error=str(e))
            if isinstance(e, LLMServiceError):
                raise
            raise LLMServiceError(f"Failed to stream contextual answer: {str(e)}")

    async def generate_topic_name(self, text: str) -> str:
        """Generate a concise topic name (ideally 3 words) for the given text."""
        try:
            prompt = f"""Analyze the following text and generate a concise topic name that captures its main subject or theme.

            Text:
            "{text}"

            Requirements:
            - Generate a topic name that is ideally 3 words or less
            - Use descriptive, meaningful words that capture the essence of the content
            - Make it concise but informative
            - Use title case (capitalize first letter of each word)
            - Avoid generic terms like "text", "content", "document"
            - Focus on the main subject, theme, or domain of the text
            - Return only the topic name, no additional text or explanation

            Examples of good topic names:
            - "Machine Learning"
            - "Climate Change"
            - "Ancient History"
            - "Financial Markets"
            - "Space Exploration"
            - "Medical Research"
            - "Art History"
            - "Renewable Energy"

            Topic name:"""

            response = await self._make_api_call(
                model=settings.gpt4o_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=50,  # Short response needed
                temperature=0.3
            )

            topic_name = response.choices[0].message.content.strip()
            
            # Clean up the response - remove any extra text and ensure proper formatting
            topic_name = topic_name.replace('"', '').replace("'", '').strip()
            
            # Ensure it's not too long (max 3 words)
            words = topic_name.split()
            if len(words) > 3:
                topic_name = ' '.join(words[:3])
            
            logger.info("Successfully generated topic name", 
                       text_length=len(text),
                       topic_name=topic_name)
            
            return topic_name

        except Exception as e:
            logger.error("Failed to generate topic name", error=str(e))
            if isinstance(e, LLMServiceError):
                raise
            raise LLMServiceError(f"Failed to generate topic name: {str(e)}")

    async def detect_text_language_code(self, text: str) -> str:
        """Detect the language of text and return ISO 639-1 language code (e.g., 'EN', 'ES', 'DE')."""
        try:
            # Limit text to first 500 chars for efficiency
            text_sample = text[:500] if len(text) > 500 else text
            
            prompt = f"""Detect the language of the following text and return ONLY the ISO 639-1 language code in uppercase (e.g., "EN" for English, "ES" for Spanish, "DE" for German, "FR" for French, "HI" for Hindi, "JA" for Japanese, "ZH" for Chinese, "AR" for Arabic, "IT" for Italian, "PT" for Portuguese, "RU" for Russian, "KO" for Korean, etc.).

Text: "{text_sample}"

CRITICAL REQUIREMENTS:
- Return ONLY the ISO 639-1 language code in UPPERCASE (e.g., "EN", "ES", "DE", "FR", "HI", "JA", "ZH", "AR", "IT", "PT", "RU", "KO")
- Do NOT return any additional text, explanation, or formatting
- Be accurate in language detection for ALL languages
- If the text contains multiple languages or is unclear, return the primary language code
- Return only the language code, nothing else
- Use standard ISO 639-1 two-letter codes in uppercase

Language code:"""

            response = await self._make_api_call(
                model=settings.gpt4o_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=10,
                temperature=0.1
            )

            language_code = response.choices[0].message.content.strip().upper()
            # Clean up the response - remove quotes and ensure uppercase
            language_code = language_code.replace('"', '').replace("'", '').strip().upper()
            
            # Validate it's a 2-letter code
            if len(language_code) != 2:
                logger.warning("Invalid language code format, defaulting to EN", code=language_code)
                return "EN"
            
            logger.info("Detected text language code", text_preview=text[:50], language_code=language_code)
            return language_code

        except Exception as e:
            logger.warning("Failed to detect text language code, defaulting to EN", error=str(e))
            return "EN"  # Default to English

    async def _detect_word_language(self, word: str) -> str:
        """Detect the language of a word using LLM to ensure proper pronunciation."""
        try:
            prompt = f"""Detect the language of the following word and return ONLY the language name in English (e.g., "English", "Hindi", "Spanish", "French", "German", "Japanese", "Chinese", "Arabic", "Italian", "Portuguese", "Russian", "Korean", etc.).

Word: "{word}"

CRITICAL REQUIREMENTS:
- Return ONLY the language name in English (e.g., "English", "Hindi", "Spanish", "German", "French")
- Do NOT return any additional text, explanation, or formatting
- Be accurate in language detection for ALL languages
- If the word contains multiple languages or is unclear, return the primary language
- Return only the language name, nothing else

Language:"""

            response = await self._make_api_call(
                model=settings.gpt4o_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=20,
                temperature=0.1
            )

            detected_language = response.choices[0].message.content.strip()
            # Clean up the response
            detected_language = detected_language.replace('"', '').replace("'", '').strip()
            
            logger.info("Detected word language", word=word, language=detected_language)
            return detected_language

        except Exception as e:
            logger.warning("Failed to detect word language, proceeding with default", word=word, error=str(e))
            return "Unknown"  # Fallback to let TTS auto-detect

    async def _prepare_word_for_pronunciation(self, word: str, language: str) -> str:
        """Prepare word for pronunciation by ensuring proper formatting for the detected language."""
        try:
            # Clean and normalize the word first
            cleaned_word = word.strip()
            
            # If language is English or Unknown, return word as-is (but normalized)
            if language.lower() in ["english", "unknown"]:
                return cleaned_word
            
            # For non-English languages, verify and ensure proper formatting
            # Use LLM to check if the word is properly formatted for pronunciation in that language
            prompt = f"""Verify and prepare the following word for text-to-speech pronunciation in {language} language.

Word: "{cleaned_word}"
Language: {language}

CRITICAL REQUIREMENTS:
- If the word is already correctly formatted for {language} pronunciation, return it EXACTLY as-is
- If the word is missing essential diacritics, accents, or special characters for {language}, add them
- Preserve ALL special characters, diacritics, and accents that are essential for correct pronunciation in {language}
- For languages with special characters (Spanish: ñ, á, é, í, ó, ú; German: ü, ö, ä, ß; French: é, è, ê, ç, etc.), ensure they are present and correct
- Do NOT translate the word - only ensure proper formatting for pronunciation
- Do NOT change the word if it's already correct
- Do NOT add explanations or additional text
- Return ONLY the word (formatted if needed), nothing else

Word for pronunciation:"""

            response = await self._make_api_call(
                model=settings.gpt4o_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=50,
                temperature=0.1
            )

            formatted_word = response.choices[0].message.content.strip()
            # Clean up the response - remove quotes if present
            formatted_word = formatted_word.replace('"', '').replace("'", '').strip()
            
            # If the formatted word is empty or seems wrong, fall back to original
            if not formatted_word or len(formatted_word) == 0:
                logger.warning("Formatted word is empty, using original", word=word, language=language)
                return cleaned_word
            
            # Validate that the formatted word is reasonable (not too different from original)
            # If it's completely different, it might be a translation error
            if abs(len(formatted_word) - len(cleaned_word)) > len(cleaned_word) * 0.5:
                logger.warning("Formatted word seems too different, using original", 
                             original=cleaned_word, formatted=formatted_word, language=language)
                return cleaned_word
            
            logger.info("Prepared word for pronunciation", 
                       original_word=cleaned_word, 
                       formatted_word=formatted_word, 
                       language=language)
            return formatted_word

        except Exception as e:
            logger.warning("Failed to prepare word for pronunciation, using original", 
                          word=word, language=language, error=str(e))
            return word.strip()  # Fallback to original word

    async def generate_pronunciation_audio(self, word: str, voice: str = "nova", boost_volume_db: float = 8.0) -> bytes:
        """Generate pronunciation audio for a word using OpenAI TTS with volume boost.
        
        Args:
            word: The word to generate pronunciation for (can be in any language)
            voice: The voice to use (alloy, echo, fable, onyx, nova, shimmer)
                  Default is 'nova' for a sweet-toned American female voice
            boost_volume_db: Volume boost in decibels (default: 8.0 dB for better audibility)
        
        Returns:
            Audio data as bytes (MP3 format) with boosted volume
        """
        try:
            logger.info("Generating pronunciation audio", word=word, voice=voice, volume_boost=boost_volume_db)
            
            # Detect the language of the word to ensure proper pronunciation
            detected_language = await self._detect_word_language(word)
            logger.info("Word language detected for pronunciation", word=word, language=detected_language)
            
            # Prepare the word for pronunciation based on detected language
            # This ensures proper formatting for non-English languages
            pronunciation_word = await self._prepare_word_for_pronunciation(word, detected_language)
            
            # Validate that we have a word to pronounce
            if not pronunciation_word or len(pronunciation_word.strip()) == 0:
                logger.error("Empty pronunciation word after preparation", original_word=word)
                raise LLMServiceError("Cannot generate pronunciation for empty word")
            
            # Use OpenAI's text-to-speech API with HD model for better quality
            # For non-English languages, the prepared word format helps TTS understand the correct pronunciation
            response = await self.client.audio.speech.create(
                model="tts-1-hd",  # HD model for better quality
                voice=voice,
                input=pronunciation_word,
                response_format="mp3"
            )
            
            # Get the audio content
            original_audio_bytes = response.content
            
            # Validate that audio was generated
            if not original_audio_bytes or len(original_audio_bytes) == 0:
                logger.error("Empty audio response from TTS", word=word, pronunciation_word=pronunciation_word, language=detected_language)
                raise LLMServiceError("TTS returned empty audio data")
            
            # Boost volume using pydub
            try:
                # Load audio from bytes
                audio = AudioSegment.from_mp3(io.BytesIO(original_audio_bytes))
                
                # Increase volume by specified dB
                boosted_audio = audio + boost_volume_db
                
                # Export back to MP3 bytes
                output_buffer = io.BytesIO()
                boosted_audio.export(output_buffer, format="mp3", bitrate="128k")
                audio_bytes = output_buffer.getvalue()
                
                logger.info("Successfully generated and boosted pronunciation audio", 
                           word=word, 
                           voice=voice,
                           original_size=len(original_audio_bytes),
                           boosted_size=len(audio_bytes),
                           volume_boost_db=boost_volume_db)
                
                return audio_bytes
                
            except Exception as boost_error:
                logger.warning("Failed to boost audio volume, returning original", 
                             error=str(boost_error))
                # If volume boosting fails, return original audio
                return original_audio_bytes
            
        except Exception as e:
            logger.error("Failed to generate pronunciation audio", word=word, error=str(e))
            if isinstance(e, LLMServiceError):
                raise
            raise LLMServiceError(f"Failed to generate pronunciation for word '{word}': {str(e)}")

    async def transcribe_audio(self, audio_bytes: bytes, filename: str, translate: bool = False) -> str:
        """Transcribe audio to text using OpenAI Whisper API.
        
        Args:
            audio_bytes: Audio file data as bytes
            filename: Original filename (for format detection)
            translate: If True, translates non-English audio to English. If False, transcribes in original language.
        
        Returns:
            Transcribed text (in original language or English if translate=True)
        """
        try:
            logger.info("Transcribing audio using Whisper", 
                       filename=filename, 
                       audio_size=len(audio_bytes),
                       translate=translate)
            
            # Create a file-like object from bytes
            audio_file = io.BytesIO(audio_bytes)
            audio_file.name = filename  # Set the name for format detection
            
            if translate:
                # Use translations endpoint to translate to English
                response = await self.client.audio.translations.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format="text"
                )
            else:
                # Use transcriptions endpoint to transcribe in original language
                response = await self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format="text"
                )
            
            # Extract the transcribed text
            transcribed_text = response.strip() if isinstance(response, str) else response.text.strip()
            
            logger.info("Successfully transcribed audio", 
                       filename=filename,
                       text_length=len(transcribed_text),
                       translate=translate)
            
            return transcribed_text
            
        except Exception as e:
            logger.error("Failed to transcribe audio", 
                        filename=filename, 
                        error=str(e))
            if isinstance(e, LLMServiceError):
                raise
            raise LLMServiceError(f"Failed to transcribe audio: {str(e)}")

    async def translate_texts(self, texts: List[str], target_language_code: str) -> List[str]:
        """Translate multiple texts to the target language using OpenAI.
        
        Args:
            texts: List of texts to translate
            target_language_code: ISO 639-1 language code (e.g., 'EN', 'ES', 'FR', 'DE', 'HI', 'JA', 'ZH')
        
        Returns:
            List of translated texts in the same order as input
        """
        try:
            if not texts:
                return []
            
            # Map language codes to full language names for better translation
            language_map = {
                "EN": "English",
                "ES": "Spanish",
                "FR": "French",
                "DE": "German",
                "HI": "Hindi",
                "JA": "Japanese",
                "ZH": "Chinese",
                "AR": "Arabic",
                "IT": "Italian",
                "PT": "Portuguese",
                "RU": "Russian",
                "KO": "Korean",
                "NL": "Dutch",
                "PL": "Polish",
                "TR": "Turkish",
                "VI": "Vietnamese",
                "TH": "Thai",
                "ID": "Indonesian",
                "CS": "Czech",
                "SV": "Swedish",
                "DA": "Danish",
                "NO": "Norwegian",
                "FI": "Finnish",
                "EL": "Greek",
                "HE": "Hebrew",
                "UK": "Ukrainian",
                "RO": "Romanian",
                "HU": "Hungarian",
            }
            
            target_language = language_map.get(target_language_code.upper(), target_language_code.upper())
            
            # Create a prompt that translates all texts at once
            texts_list = "\n".join([f"{i+1}. {text}" for i, text in enumerate(texts)])
            
            prompt = f"""Translate the following texts to {target_language}. 

Texts to translate:
{texts_list}

CRITICAL REQUIREMENTS:
- Translate each text accurately to {target_language}
- Preserve the meaning and context of each text
- Maintain the same order as the input texts
- Return ONLY a JSON array of translated texts in the same order
- Each element in the array should be the translated version of the corresponding input text
- Do NOT include any additional text, explanations, or formatting
- Return the result as a JSON array: ["translated text 1", "translated text 2", ...]

Translated texts (JSON array only):"""

            response = await self._make_api_call(
                model=settings.gpt4o_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=settings.max_tokens,
                temperature=0.3
            )

            result = response.choices[0].message.content.strip()
            
            # Parse the JSON response
            try:
                # Strip Markdown code block if present
                if result.startswith("```"):
                    result = re.sub(r"^```(?:json)?\n|\n```$", "", result.strip())
                
                translated_texts = json.loads(result)
                
                if not isinstance(translated_texts, list):
                    raise ValueError("Expected JSON array")
                
                # Ensure we have the same number of translations as inputs
                if len(translated_texts) != len(texts):
                    logger.warning(
                        "Translation count mismatch", 
                        input_count=len(texts),
                        output_count=len(translated_texts)
                    )
                    # If we got fewer translations, pad with empty strings
                    # If we got more, truncate
                    if len(translated_texts) < len(texts):
                        translated_texts.extend([""] * (len(texts) - len(translated_texts)))
                    else:
                        translated_texts = translated_texts[:len(texts)]
                
                logger.info(
                    "Successfully translated texts",
                    input_count=len(texts),
                    target_language=target_language,
                    target_language_code=target_language_code
                )
                
                return translated_texts
                
            except json.JSONDecodeError as e:
                logger.error("Failed to parse translation response as JSON", error=str(e), response=result)
                raise LLMServiceError("Failed to parse translation response")
                
        except Exception as e:
            logger.error("Failed to translate texts", error=str(e), target_language_code=target_language_code)
            if isinstance(e, LLMServiceError):
                raise
            raise LLMServiceError(f"Failed to translate texts: {str(e)}")

    async def summarise_text(self, text: str, language_code: Optional[str] = None) -> str:
        """Generate a short, insightful summary of the given text using OpenAI.
        
        Args:
            text: The text to summarize (can contain newline characters)
            language_code: Optional language code. If provided, summary will be strictly in this language.

        Returns:
            A concise, insightful summary of the input text
        """
        try:
            # Build language requirement section
            if language_code:
                language_name = get_language_name(language_code)
                if language_name:
                    language_requirement = f"""
CRITICAL LANGUAGE REQUIREMENT:
- You MUST respond STRICTLY in {language_name} ({language_code})
- The summary MUST be in {language_name} ONLY
- Do NOT use any other language - ONLY {language_name}
- This is MANDATORY and NON-NEGOTIABLE

"""
                else:
                    language_requirement = f"""
CRITICAL LANGUAGE REQUIREMENT:
- You MUST respond STRICTLY in the language specified by code: {language_code.upper()}
- The summary MUST be in this language ONLY
- Do NOT use any other language

"""
            else:
                language_requirement = ""

            prompt = f"""Analyze the following text and generate a short, insightful summary that captures the main ideas and key points.

Text:
{text}
{language_requirement}CRITICAL REQUIREMENTS:
- Generate a concise summary that captures the essence and main ideas of the text
- Keep it brief but insightful - focus on the most important information
- Preserve the core meaning and key concepts
- Make it clear and easy to understand
- If the text contains multiple paragraphs or sections, synthesize them into a coherent summary
- Handle newline characters and multi-paragraph text appropriately
- Return only the summary text, no additional commentary or formatting
- The summary should be significantly shorter than the original text while retaining key information

Summary:"""

            response = await self._make_api_call(
                model=settings.gpt4o_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=settings.max_tokens,
                temperature=0.3
            )

            summary = response.choices[0].message.content.strip()
            
            logger.info("Successfully generated summary", 
                       original_length=len(text),
                       summary_length=len(summary))
            
            return summary

        except Exception as e:
            logger.error("Failed to generate summary", error=str(e))
            if isinstance(e, LLMServiceError):
                raise
            raise LLMServiceError(f"Failed to generate summary: {str(e)}")

    async def summarise_text_stream(self, text: str, language_code: Optional[str] = None):
        """Generate a short, insightful summary of the given text with streaming.

        Args:
            text: The text to summarize (can contain newline characters)
            language_code: Optional language code. If provided, summary will be strictly in this language.

        Yields:
            Chunks of the summary text as they are generated by OpenAI.
        """
        try:
            # Build language requirement section
            if language_code:
                language_name = get_language_name(language_code)
                if language_name:
                    language_requirement = f"""
CRITICAL LANGUAGE REQUIREMENT:
- You MUST respond STRICTLY in {language_name} ({language_code})
- The summary MUST be in {language_name} ONLY
- Do NOT use any other language - ONLY {language_name}
- This is MANDATORY and NON-NEGOTIABLE

"""
                else:
                    language_requirement = f"""
CRITICAL LANGUAGE REQUIREMENT:
- You MUST respond STRICTLY in the language specified by code: {language_code.upper()}
- The summary MUST be in this language ONLY
- Do NOT use any other language

"""
            else:
                language_requirement = ""

            prompt = f"""Analyze the following text and generate a short, insightful summary that captures the main ideas and key points.

Text:
{text}
{language_requirement}CRITICAL REQUIREMENTS:
- Generate a concise summary that captures the essence and main ideas of the text
- Keep it brief but insightful - focus on the most important information
- Preserve the core meaning and key concepts
- Make it clear and easy to understand
- If the text contains multiple paragraphs or sections, synthesize them into a coherent summary
- Handle newline characters and multi-paragraph text appropriately
- Return only the summary text, no additional commentary or formatting
- The summary should be significantly shorter than the original text while retaining key information

Summary:"""

            # Create streaming response
            stream = await self.client.chat.completions.create(
                model=settings.gpt4o_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=settings.max_tokens,
                temperature=0.3,
                stream=True
            )

            # Yield chunks as they arrive
            async for chunk in stream:
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if delta and delta.content:
                        yield delta.content

            logger.info("Successfully streamed summary",
                       original_length=len(text))

        except Exception as e:
            logger.error("Failed to stream summary", error=str(e))
            if isinstance(e, LLMServiceError):
                raise
            raise LLMServiceError(f"Failed to stream summary: {str(e)}")

    async def close(self):
        """Close the HTTP client."""
        if hasattr(self.client, '_client') and hasattr(self.client._client, 'aclose'):
            await self.client._client.aclose()
            logger.info("OpenAI HTTP client closed")


# Global service instance
openai_service = OpenAIService()