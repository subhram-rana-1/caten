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

from app.config import settings
from app.exceptions import LLMServiceError

logger = structlog.get_logger()


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

    async def get_important_words(self, text: str) -> List[str]:
        """Get top 10 most important/difficult words from text in the order they appear."""
        try:
            prompt = f"""
            Analyze the following text and identify the top 10 most important and contextually significant words.

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

    async def get_word_explanation(self, word: str, context: str) -> Dict[str, Any]:
        """Get explanation and examples for a single word in context."""
        try:
            prompt = f"""Provide a simplified explanation and exactly 2 example sentences for the word "{word}" in the given context.

            Context: "{context}"
            Word: "{word}"
            
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

    async def simplify_text(self, text: str, previous_simplified_texts: List[str]) -> str:
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

            prompt = f"""Simplify the following text to make it EXTREMELY easy to understand. Use the simplest possible language and sentence structure.

            {context_section}

            Original text:
            "{text}"

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

    async def generate_contextual_answer(self, question: str, chat_history: List, initial_context: Optional[str] = None) -> str:
        """Generate contextual answer using chat history for ongoing conversations."""
        try:
            # Build messages from chat history
            messages = []
            
            # Add system message for context
            system_content = "You are a helpful AI assistant that provides clear, accurate, and contextual answers. Use the conversation history to maintain context and provide relevant responses."
            
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

    async def close(self):
        """Close the HTTP client."""
        if hasattr(self.client, '_client') and hasattr(self.client._client, 'aclose'):
            await self.client._client.aclose()
            logger.info("OpenAI HTTP client closed")


# Global service instance
openai_service = OpenAIService()