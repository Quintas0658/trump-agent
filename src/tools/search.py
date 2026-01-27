"""Search tool - Parallel web search using Tavily."""

import asyncio
from dataclasses import dataclass
from typing import Optional
from tavily import TavilyClient

from src.config import config


@dataclass
class SearchResult:
    """A single search result."""
    title: str
    url: str
    content: str
    score: float


@dataclass
class SearchResponse:
    """Response from a search query."""
    query: str
    results: list[SearchResult]
    

class SearchTool:
    """Web search using Tavily API with parallel query support and key rotation."""
    
    def __init__(self, api_keys: list[str] = None):
        """Initialize with one or more API keys for rotation.
        
        Args:
            api_keys: List of API keys. If None, reads from:
                      1. TAVILY_API_KEYS (comma-separated)
                      2. TAVILY_API_KEY (single key, fallback)
        """
        import os
        
        if api_keys:
            self.api_keys = api_keys
        else:
            # Try comma-separated keys first
            keys_str = os.getenv("TAVILY_API_KEYS", "")
            if keys_str:
                self.api_keys = [k.strip() for k in keys_str.split(",") if k.strip()]
            else:
                # Fallback to single key
                single_key = config.TAVILY_API_KEY
                self.api_keys = [single_key] if single_key else []
        
        self.current_key_index = 0
        self.exhausted_keys = set()  # Track keys that hit quota
        
        if not self.api_keys:
            self.client = None
            print("[!] Tavily API key missing. Search tool operating in MOCK mode.")
        else:
            self.client = TavilyClient(api_key=self.api_keys[0])
            print(f"[Tavily] Initialized with {len(self.api_keys)} API key(s)")
    
    def _rotate_key(self) -> bool:
        """Rotate to the next available API key.
        
        Returns:
            True if rotation successful, False if all keys exhausted
        """
        self.exhausted_keys.add(self.current_key_index)
        
        # Find next non-exhausted key
        for i in range(len(self.api_keys)):
            if i not in self.exhausted_keys:
                self.current_key_index = i
                self.client = TavilyClient(api_key=self.api_keys[i])
                print(f"[Tavily] Rotated to key #{i + 1}/{len(self.api_keys)}")
                return True
        
        print("[!] All Tavily API keys exhausted!")
        return False
    
    def search(
        self, 
        query: str, 
        max_results: int = 5, 
        deep: bool = False,
        include_domains: list[str] = None
    ) -> SearchResponse:
        """Execute a single search query with automatic key rotation on quota limit.
        
        Args:
            query: Search query string
            max_results: Number of results to return (default 5)
            deep: If True, use advanced search and include AI answer
            include_domains: Optional list of domains to prioritize (e.g., ["axios.com"])
        """
        if not self.client:
            return SearchResponse(query=query, results=[
                SearchResult(title=f"Mock result for {query}", url="https://example.com", content=f"This is a mock search result for {query}. It contains some text about Trump and his policies.", score=0.9)
            ])
        
        try:
            # Build search kwargs
            search_kwargs = {
                "query": query,
                "search_depth": "advanced",  # Always use advanced for better results
                "max_results": max_results,
                "include_answer": True,  # Get AI-summarized answer
                "include_raw_content": deep,  # Only for deep dives
            }
            
            # Add domain filter if provided
            if include_domains:
                search_kwargs["include_domains"] = include_domains
            
            response = self.client.search(**search_kwargs)
            
            results = [
                SearchResult(
                    title=r.get("title", ""),
                    url=r.get("url", ""),
                    content=r.get("content", ""),
                    score=r.get("score", 0.0),
                )
                for r in response.get("results", [])
            ]
            
            # Prepend AI answer as first result if available
            if response.get("answer"):
                results.insert(0, SearchResult(
                    title="[Tavily AI Summary]",
                    url="",
                    content=response["answer"],
                    score=1.0,
                ))
            
            return SearchResponse(query=query, results=results)
        except Exception as e:
            error_msg = str(e).lower()
            
            # Check if it's a quota/usage limit error
            if "usage limit" in error_msg or "quota" in error_msg or "rate limit" in error_msg:
                print(f"[!] Key #{self.current_key_index + 1} quota exceeded, attempting rotation...")
                if self._rotate_key():
                    # Retry with new key
                    return self.search(query, max_results, deep, include_domains)
            
            print(f"[!] Search failed for '{query}': {e}")
            # Return empty results on failure instead of crashing
            return SearchResponse(query=query, results=[])
    
    async def parallel_search(
        self, 
        queries: list[str], 
        max_results_per_query: int = 3,
        include_domains: list[str] = None
    ) -> list[SearchResponse]:
        """Execute multiple search queries in parallel.
        
        This reduces total latency from N * latency to ~1 * latency.
        """
        async def search_async(query: str) -> SearchResponse:
            # Run sync search in thread pool
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None, 
                lambda: self.search(query, max_results_per_query, include_domains=include_domains)
            )
        
        tasks = [search_async(q) for q in queries]
        results = await asyncio.gather(*tasks)
        return list(results)
    
    def generate_queries(self, tweet: str, entities: list[str]) -> list[str]:
        """Generate parallel search queries from a tweet and extracted entities.
        
        This creates diverse queries to get comprehensive context.
        """
        queries = []
        
        # Query 1: Direct tweet context
        if len(tweet) > 50:
            queries.append(f"Trump {tweet[:50]}")
        else:
            queries.append(f"Trump {tweet}")
        
        # Query 2-N: Entity-specific queries
        for entity in entities[:config.MAX_PARALLEL_QUERIES - 1]:
            queries.append(f"{entity} news January 2026")
        
        # Ensure we have at least 2 queries
        if len(queries) < 2:
            queries.append("Trump latest news today")
        
        return queries[:config.MAX_PARALLEL_QUERIES]
