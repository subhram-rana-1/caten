"""Web search service for performing web searches and returning structured results."""

import asyncio
import time
from typing import List, Dict, Any, Optional, AsyncGenerator
from duckduckgo_search import DDGS
import structlog

logger = structlog.get_logger()


class WebSearchService:
    """Service for performing web searches using DuckDuckGo."""

    # Language to DuckDuckGo region code mapping
    # DuckDuckGo uses region codes that combine country and language (e.g., "us-en" for US English)
    LANGUAGE_TO_REGION = {
        "en": "us-en",  # English (US)
        "es": "es-es",  # Spanish (Spain)
        "fr": "fr-fr",  # French (France)
        "de": "de-de",  # German (Germany)
        "it": "it-it",  # Italian (Italy)
        "pt": "pt-pt",  # Portuguese (Portugal)
        "ru": "ru-ru",  # Russian (Russia)
        "ja": "jp-jp",  # Japanese (Japan)
        "zh": "cn-zh",  # Chinese (China)
        "ko": "kr-kr",  # Korean (Korea)
        "ar": "sa-ar",  # Arabic (Saudi Arabia)
        "hi": "in-hi",  # Hindi (India)
        "nl": "nl-nl",  # Dutch (Netherlands)
        "pl": "pl-pl",  # Polish (Poland)
        "tr": "tr-tr",  # Turkish (Turkey)
        "vi": "vn-vi",  # Vietnamese (Vietnam)
        "th": "th-th",  # Thai (Thailand)
        "id": "id-id",  # Indonesian (Indonesia)
        "cs": "cz-cs",  # Czech (Czech Republic)
        "sv": "se-sv",  # Swedish (Sweden)
        "da": "dk-da",  # Danish (Denmark)
        "no": "no-no",  # Norwegian (Norway)
        "fi": "fi-fi",  # Finnish (Finland)
    }

    def __init__(self):
        """Initialize the web search service."""
        logger.info("Initializing web search service")

    def _get_region_from_language(self, language: Optional[str], region: Optional[str]) -> str:
        """Get DuckDuckGo region code from language or use provided region.
        
        Args:
            language: Language code (e.g., 'en', 'es', 'fr')
            region: Explicit region code (takes precedence if provided)
        
        Returns:
            DuckDuckGo region code
        """
        # If explicit region is provided, use it
        if region and region != "wt-wt":
            return region
        
        # If language is provided, map it to region code
        if language:
            language_lower = language.lower()
            # Handle full language codes like "en-US" -> "en"
            if "-" in language_lower:
                language_lower = language_lower.split("-")[0]
            
            mapped_region = self.LANGUAGE_TO_REGION.get(language_lower)
            if mapped_region:
                return mapped_region
        
        # Default to English (US) if language is None or not found
        return "us-en"

    async def _perform_search_with_retry(
        self,
        query: str,
        max_results: int,
        region: str,
        max_retries: int = 3,
        retry_delay: float = 0.5
    ) -> List[Dict[str, Any]]:
        """Perform search with retry logic to handle inconsistent results.
        
        Args:
            query: Search query string
            max_results: Maximum number of results
            region: DuckDuckGo region code
            max_retries: Maximum number of retry attempts
            retry_delay: Initial delay between retries (exponential backoff)
        
        Returns:
            List of search results
        """
        def _perform_search():
            with DDGS() as ddgs:
                return list(ddgs.text(
                    query,
                    max_results=max_results,
                    region=region
                ))
        
        last_exception = None
        for attempt in range(max_retries):
            try:
                loop = asyncio.get_event_loop()
                results = await loop.run_in_executor(None, _perform_search)
                
                # If we got results, return them
                if results and len(results) > 0:
                    logger.info(
                        "Search successful",
                        query=query,
                        results_count=len(results),
                        attempt=attempt + 1
                    )
                    return results
                
                # If no results and not last attempt, retry
                if attempt < max_retries - 1:
                    delay = retry_delay * (2 ** attempt)  # Exponential backoff
                    logger.warning(
                        "Search returned 0 results, retrying",
                        query=query,
                        attempt=attempt + 1,
                        max_retries=max_retries,
                        delay=delay
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.warning(
                        "Search returned 0 results after all retries",
                        query=query,
                        attempts=max_retries
                    )
                    return results  # Return empty results
                    
            except Exception as e:
                last_exception = e
                if attempt < max_retries - 1:
                    delay = retry_delay * (2 ** attempt)
                    logger.warning(
                        "Search error, retrying",
                        query=query,
                        error=str(e),
                        attempt=attempt + 1,
                        max_retries=max_retries,
                        delay=delay
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        "Search failed after all retries",
                        query=query,
                        error=str(e),
                        attempts=max_retries
                    )
                    raise
        
        # Should not reach here, but just in case
        if last_exception:
            raise last_exception
        return []

    async def search(
        self,
        query: str,
        max_results: int = 10,
        region: Optional[str] = None,
        language: Optional[str] = None
    ) -> Dict[str, Any]:
        """Perform a web search and return structured results.
        
        Args:
            query: Search query string
            max_results: Maximum number of results to return (default: 10)
            region: Search region code (optional, overrides language if provided)
            language: Language code for search results (e.g., 'en', 'es', 'fr'). Defaults to 'en' if None.
        
        Returns:
            Dictionary containing search metadata and results in Google-like format
        """
        start_time = time.time()
        
        try:
            # Determine region from language or use provided region
            search_region = self._get_region_from_language(language, region)
            
            logger.info(
                "Performing web search",
                query=query,
                language=language,
                region=region,
                search_region=search_region,
                max_results=max_results
            )
            
            # Perform search with retry logic
            results = await self._perform_search_with_retry(
                query=query,
                max_results=max_results,
                region=search_region
            )
            
            search_time = time.time() - start_time
            
            # Transform results to match Google Search API format
            items = []
            for result in results:
                item = {
                    "title": result.get("title", ""),
                    "link": result.get("href", ""),
                    "snippet": result.get("body", ""),
                    "displayLink": self._extract_display_link(result.get("href", "")),
                }
                
                # Add image if available
                if "image" in result and result["image"]:
                    item["image"] = {
                        "url": result["image"],
                        "height": None,
                        "width": None
                    }
                
                items.append(item)
            
            # Build response in Google Search API-like format
            response = {
                "kind": "customsearch#search",
                "searchInformation": {
                    "searchTime": round(search_time, 3),
                    "formattedSearchTime": f"{search_time:.2f}",
                    "totalResults": str(len(items)),
                    "formattedTotalResults": str(len(items))
                },
                "queries": {
                    "request": [{
                        "title": f"Web search: {query}",
                        "totalResults": str(len(items)),
                        "searchTerms": query,
                        "count": len(items),
                        "startIndex": 1,
                        "inputEncoding": "utf8",
                        "outputEncoding": "utf8",
                        "safe": "off"
                    }]
                },
                "items": items
            }
            
            logger.info(
                "Web search completed",
                query=query,
                results_count=len(items),
                search_time=search_time
            )
            
            return response
            
        except Exception as e:
            logger.error("Error performing web search", query=query, error=str(e))
            # Return empty results structure on error
            search_time = time.time() - start_time
            return {
                "kind": "customsearch#search",
                "searchInformation": {
                    "searchTime": round(search_time, 3),
                    "formattedSearchTime": f"{search_time:.2f}",
                    "totalResults": "0",
                    "formattedTotalResults": "0"
                },
                "queries": {
                    "request": [{
                        "title": f"Web search: {query}",
                        "totalResults": "0",
                        "searchTerms": query,
                        "count": 0,
                        "startIndex": 1,
                        "inputEncoding": "utf8",
                        "outputEncoding": "utf8",
                        "safe": "off"
                    }]
                },
                "items": [],
                "error": {
                    "code": "SEARCH_ERROR",
                    "message": str(e)
                }
            }

    def _extract_display_link(self, url: str) -> str:
        """Extract display-friendly link from full URL.
        
        Args:
            url: Full URL
            
        Returns:
            Display-friendly link (e.g., "www.example.com" from "https://www.example.com/path")
        """
        if not url:
            return ""
        
        # Remove protocol
        display_link = url.replace("https://", "").replace("http://", "")
        
        # Remove www. prefix for cleaner display (optional, can be kept)
        # display_link = display_link.replace("www.", "")
        
        # Get just the domain and first path segment
        parts = display_link.split("/")
        if parts:
            return parts[0]
        
        return display_link

    async def search_stream(
        self,
        query: str,
        max_results: int = 10,
        region: Optional[str] = None,
        language: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Perform a web search and stream results one by one.
        
        Args:
            query: Search query string
            max_results: Maximum number of results to return (default: 10)
            region: Search region code (optional, overrides language if provided)
            language: Language code for search results (e.g., 'en', 'es', 'fr'). Defaults to 'en' if None.
        
        Yields:
            Dictionary containing individual search result items and metadata
        """
        start_time = time.time()
        
        try:
            # Determine region from language or use provided region
            search_region = self._get_region_from_language(language, region)
            
            logger.info(
                "Performing web search stream",
                query=query,
                language=language,
                region=region,
                search_region=search_region,
                max_results=max_results
            )
            
            # Perform search with retry logic
            results = await self._perform_search_with_retry(
                query=query,
                max_results=max_results,
                region=search_region
            )
            
            search_time = time.time() - start_time
            
            # First, send search metadata
            metadata = {
                "type": "metadata",
                "searchInformation": {
                    "searchTime": round(search_time, 3),
                    "formattedSearchTime": f"{search_time:.2f}",
                    "totalResults": str(len(results)),
                    "formattedTotalResults": str(len(results))
                },
                "queries": {
                    "request": [{
                        "title": f"Web search: {query}",
                        "totalResults": str(len(results)),
                        "searchTerms": query,
                        "count": len(results),
                        "startIndex": 1,
                        "inputEncoding": "utf8",
                        "outputEncoding": "utf8",
                        "safe": "off"
                    }]
                }
            }
            yield metadata
            
            # Stream results one by one
            for result in results:
                item = {
                    "type": "result",
                    "title": result.get("title", ""),
                    "link": result.get("href", ""),
                    "snippet": result.get("body", ""),
                    "displayLink": self._extract_display_link(result.get("href", "")),
                }
                
                # Add image if available
                if "image" in result and result["image"]:
                    item["image"] = {
                        "url": result["image"],
                        "height": None,
                        "width": None
                    }
                
                yield item
                # Small delay to make streaming visible
                await asyncio.sleep(0.05)
            
            # Send completion event
            yield {"type": "complete"}
            
            logger.info(
                "Web search stream completed",
                query=query,
                results_count=len(results),
                search_time=search_time
            )
            
        except Exception as e:
            logger.error("Error performing web search stream", query=query, error=str(e))
            # Send error event
            search_time = time.time() - start_time
            yield {
                "type": "error",
                "error": {
                    "code": "SEARCH_ERROR",
                    "message": str(e)
                },
                "searchInformation": {
                    "searchTime": round(search_time, 3),
                    "formattedSearchTime": f"{search_time:.2f}",
                    "totalResults": "0",
                    "formattedTotalResults": "0"
                }
            }


# Global service instance
web_search_service = WebSearchService()

