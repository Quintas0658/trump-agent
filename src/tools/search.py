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
    """Web search using Tavily API with parallel query support."""
    
    def __init__(self, api_key: Optional[str] = None):
        api_key = api_key or config.TAVILY_API_KEY
        if not api_key:
            self.client = None
            print("[!] Tavily API key missing. Search tool operating in MOCK mode.")
        else:
            self.client = TavilyClient(api_key=api_key)
    
    def search(self, query: str, max_results: int = 5) -> SearchResponse:
        """Execute a single search query."""
        if not self.client:
            return SearchResponse(query=query, results=[
                SearchResult(title=f"Mock result for {query}", url="https://example.com", content=f"This is a mock search result for {query}. It contains some text about Trump and his policies.", score=0.9)
            ])
        
        try:
            response = self.client.search(
                query=query,
                search_depth="advanced",
                max_results=max_results,
            )
            
            results = [
                SearchResult(
                    title=r.get("title", ""),
                    url=r.get("url", ""),
                    content=r.get("content", ""),
                    score=r.get("score", 0.0),
                )
                for r in response.get("results", [])
            ]
            
            return SearchResponse(query=query, results=results)
        except Exception as e:
            print(f"[!] Search failed for '{query}': {e}")
            # Return empty results on failure instead of crashing
            return SearchResponse(query=query, results=[])
    
    async def parallel_search(
        self, 
        queries: list[str], 
        max_results_per_query: int = 3
    ) -> list[SearchResponse]:
        """Execute multiple search queries in parallel.
        
        This reduces total latency from N * latency to ~1 * latency.
        """
        async def search_async(query: str) -> SearchResponse:
            # Run sync search in thread pool
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None, 
                lambda: self.search(query, max_results_per_query)
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
