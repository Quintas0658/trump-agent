"""Parallel Investigator - Runs multiple Tavily searches in parallel for deep investigation."""

import asyncio
from typing import Optional
from dataclasses import dataclass
from src.tools.search import SearchTool, SearchResponse


@dataclass
class InvestigationResult:
    """Result of investigating a single question."""
    question: str
    answer: str  # Tavily AI summary
    sources: list[dict]  # List of {title, url, snippet}
    

async def investigate_question(
    question: str,
    search_tool: SearchTool
) -> InvestigationResult:
    """Investigate a single question using Tavily search.
    
    Args:
        question: The investigative question to answer
        search_tool: Tavily search tool instance
    
    Returns:
        InvestigationResult with AI summary and sources
    """
    # Run search in thread pool (Tavily client is sync)
    loop = asyncio.get_event_loop()
    response: SearchResponse = await loop.run_in_executor(
        None,
        lambda: search_tool.search(question, max_results=5, deep=False)
    )
    
    # Extract AI summary (first result if available)
    answer = ""
    sources = []
    
    for result in response.results:
        if result.title == "[Tavily AI Summary]":
            answer = result.content
        else:
            sources.append({
                "title": result.title,
                "url": result.url,
                "snippet": result.content[:300],
            })
    
    return InvestigationResult(
        question=question,
        answer=answer,
        sources=sources[:5],  # Limit to 5 sources per question
    )


async def investigate_all(
    questions: list[str],
    search_tool: Optional[SearchTool] = None,
    max_concurrent: int = 10
) -> list[InvestigationResult]:
    """Run parallel investigations for all questions.
    
    Args:
        questions: List of investigative questions
        search_tool: Tavily search tool (creates one if not provided)
        max_concurrent: Maximum concurrent searches (default 10)
    
    Returns:
        List of InvestigationResult, one per question
    """
    if search_tool is None:
        search_tool = SearchTool()
    
    print(f"[Investigator] Starting parallel investigation of {len(questions)} questions...")
    
    # Create semaphore for rate limiting
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def investigate_with_limit(question: str) -> InvestigationResult:
        async with semaphore:
            return await investigate_question(question, search_tool)
    
    # Run all investigations in parallel
    tasks = [investigate_with_limit(q) for q in questions]
    results = await asyncio.gather(*tasks)
    
    # Count successful investigations
    success_count = sum(1 for r in results if r.answer or r.sources)
    print(f"[Investigator] Completed: {success_count}/{len(questions)} questions with results")
    
    return list(results)


def format_investigation_context(results: list[InvestigationResult]) -> str:
    """Format investigation results into context string for the final analysis.
    
    Args:
        results: List of InvestigationResult from parallel investigation
    
    Returns:
        Formatted string ready to insert into analysis prompt
    """
    context_parts = []
    
    context_parts.append("=" * 60)
    context_parts.append("🕵️ DEEP INVESTIGATION RESULTS (GPT-4o Questions → Tavily Answers)")
    context_parts.append("=" * 60)
    
    for i, result in enumerate(results, 1):
        context_parts.append(f"\n### Q{i}: {result.question}")
        
        if result.answer:
            context_parts.append(f"**AI Summary**: {result.answer[:500]}...")
        else:
            context_parts.append("**AI Summary**: No summary available")
        
        if result.sources:
            context_parts.append("**Sources**:")
            for source in result.sources[:3]:
                context_parts.append(f"  - [{source['title'][:50]}]({source['url']})")
        
        context_parts.append("")
    
    return "\n".join(context_parts)
