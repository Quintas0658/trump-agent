"""Tool Executor - Dispatches and executes tool calls from the ReAct Agent."""

from typing import Any, Dict, Optional
import asyncio


class ToolExecutor:
    """Executes tools requested by the LLM during the ReAct loop.
    
    Responsible for:
    - Dispatching function calls to the appropriate handlers
    - Formatting results for injection back into the conversation
    - Handling errors gracefully
    """
    
    def __init__(self, search_tool=None, post_store=None, claim_store=None):
        """Initialize the executor with available tool implementations.
        
        Args:
            search_tool: SearchTool instance for news search
            post_store: PostStore instance for memory recall
            claim_store: ClaimStore instance for entity history (optional)
        """
        self.search_tool = search_tool
        self.post_store = post_store
        self.claim_store = claim_store
    
    async def execute(self, function_call) -> str:
        """Execute a function call and return the observation.
        
        Args:
            function_call: The function call object from Gemini response
                          with .name and .args attributes
        
        Returns:
            String observation to inject back into the conversation
        """
        name = function_call.name
        args = dict(function_call.args) if hasattr(function_call.args, 'items') else function_call.args
        
        print(f"[ToolExecutor] Executing: {name} with args: {args}")
        
        try:
            if name == "search_news":
                return await self._search_news(args)
            elif name == "recall_past_analysis":
                return await self._recall_past_analysis(args)
            elif name == "get_entity_history":
                return await self._get_entity_history(args)
            else:
                return f"[Error] Unknown tool: {name}"
        except Exception as e:
            print(f"[ToolExecutor] Error: {e}")
            return f"[Error executing {name}]: {str(e)}"
    
    async def _search_news(self, args: Dict[str, Any]) -> str:
        """Execute news search using Tavily."""
        if not self.search_tool:
            return "[Error] Search tool not configured"
        
        query = args.get("query", "")
        if not query:
            return "[Error] No query provided"
        
        # Use the parallel_search method with a single query
        results = await self.search_tool.parallel_search([query])
        
        if not results or not results[0].results:
            return f"[Search: {query}] No results found."
        
        # Format results
        formatted = [f"[Search: {query}]"]
        for item in results[0].results[:5]:  # Limit to top 5
            formatted.append(f"- {item.title}: {item.content[:200]}...")
        
        return "\n".join(formatted)
    
    async def _recall_past_analysis(self, args: Dict[str, Any]) -> str:
        """Recall past analysis from memory."""
        if not self.post_store:
            return "[Error] Memory store not configured"
        
        days_ago = args.get("days_ago", 1)
        search_term = args.get("search_term", None)
        
        if search_term:
            # Search in past reports
            reports = self.post_store.search_reports(search_term, limit=3)
            if not reports:
                return f"[Memory Search: '{search_term}'] No matching reports found."
            
            formatted = [f"[Memory Search: '{search_term}']"]
            for r in reports:
                formatted.append(f"- {r.get('report_date')}: {r.get('summary', 'No summary')[:300]}...")
            return "\n".join(formatted)
        else:
            # Get specific day's report
            report = self.post_store.get_past_report(days_ago=days_ago)
            if not report:
                return f"[Memory: {days_ago} days ago] No report found."
            
            summary = report.get('summary') or report.get('report_content', '')[:500]
            return f"[Memory: {days_ago} days ago ({report.get('report_date')})]\n{summary}"
    
    async def _get_entity_history(self, args: Dict[str, Any]) -> str:
        """Get entity history from claims/events store."""
        entity_name = args.get("entity_name", "")
        if not entity_name:
            return "[Error] No entity name provided"
        
        # Try claim store first
        if self.claim_store:
            claims = self.claim_store.search_claims(entity_name, limit=5)
            if claims:
                formatted = [f"[Entity History: {entity_name}]"]
                for c in claims:
                    formatted.append(f"- {c.claimed_at}: {c.claim_text[:150]}...")
                return "\n".join(formatted)
        
        # Fallback: search in past reports
        if self.post_store:
            reports = self.post_store.search_reports(entity_name, limit=3)
            if reports:
                formatted = [f"[Entity History: {entity_name}] (from past reports)"]
                for r in reports:
                    formatted.append(f"- {r.get('report_date')}: Mentioned in analysis")
                return "\n".join(formatted)
        
        return f"[Entity History: {entity_name}] No historical data found."


def create_tool_executor(search_tool=None, post_store=None, claim_store=None) -> ToolExecutor:
    """Factory function to create a ToolExecutor with dependencies."""
    return ToolExecutor(
        search_tool=search_tool,
        post_store=post_store,
        claim_store=claim_store
    )
