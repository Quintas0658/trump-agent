"""Shadow Investigator - Recursively hunts for vague entities in search results."""

from typing import List, Dict, Any
import asyncio
from src.agent.openai_client import OpenAIClient
from src.tools.search import SearchTool

SHADOW_HUNTER_PROMPT = """You are the "Shadow Investigator" for a Deep Research engine.
Your goal is to find "Entities in the Shadows" within search snippets and generate follow-up queries to reveal them.

[DEFINITION: SHADOW ENTITY]
A "Shadow Entity" is:
1. A **Vague Reference**: "US investors", "a major tech company", "a lobbying group", "senior officials".
2. An **Unknown Proper Noun**: A specific name (e.g., "Greenoaks", "Project 2026") that appears in context but lacks definition.

[INPUT DATA]
{context}

[TASK]
1. Scan the search snippets for Shadow Entities that are relevant to the user's mission.
2. Generate 3-5 highly specific "Follow-up Search Queries" to Identify/Profile them.
3. The queries MUST be formatted to find the *identity* and *motive* of the entity.

[EXAMPLE]
Snippet: "Several US hedge funds have petitioned the USTR regarding Korea's e-commerce rules."
Shadow Entity: "Several US hedge funds"
Query: "Names of US hedge funds petitioning USTR re Korea e-commerce January 2026"

[OUTPUT FORMAT]
Return ONLY a JSON array of strings:
[
  "Query 1",
  "Query 2",
  ...
]
"""

class ShadowInvestigator:
    def __init__(self, client: OpenAIClient, search_tool: SearchTool):
        self.client = client
        self.search_tool = search_tool

    def hunt(self, context_text: str) -> List[str]:
        """Analyze context and generate follow-up queries."""
        import json
        
        # 1. Generate queries
        prompt = SHADOW_HUNTER_PROMPT.format(context=context_text[:15000]) # Limit context window
        
        try:
            response = self.client.generate(prompt)
            content = response.content.strip()
            
            # Clean markup if any
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[0].strip()
                
            queries = json.loads(content)
            print(f"[Shadow Investigator] Generated {len(queries)} follow-up queries: {queries}")
            return queries
        except Exception as e:
            print(f"[Shadow Investigator] Failed to generate queries: {e}")
            return []

    def investigate(self, context_text: str) -> str:
        """Run the full investigation loop: Hunt -> Search -> Return new context."""
        print("[Shadow Investigator] Scanning for shadow entities...")
        
        # 1. Hunt for queries
        queries = self.hunt(context_text)
        if not queries:
            return ""
            
        # 2. Execute deep searches
        print(f"[Shadow Investigator] executing {len(queries)} deep dive searches...")
        # Use sync wrapper for simplicity in this flow, or reuse parallel logic if available
        # logic here mimics the SearchTool usage in main script
        
        new_findings = []
        for q in queries:
            # We use "include_answer=True" to get the summary directly
            res = self.search_tool.search(q, max_results=3, deep=True) 
            # 'deep=True' might be overkill, let's stick to standard advanced
            
            # Extract content
            snippet = f"Query: {q}\n"
            if res.results:
                # Prioritize the AI answer if available (it sets score=1.0)
                ai_answer = next((r for r in res.results if r.title == "[Tavily AI Summary]"), None)
                if ai_answer:
                    snippet += f"Answer: {ai_answer.content}\n"
                else:
                    # Fallback to top result
                    snippet += f"Result: {res.results[0].content}\n"
            
            new_findings.append(snippet)
            
        print(f"[Shadow Investigator] Uncovered {len(new_findings)} new data points.")
        return "\n=== SHADOW INVESTIGATION FINDINGS ===\n" + "\n".join(new_findings)


async def investigate_all(questions: List[str], search_tool: SearchTool) -> List[Dict[str, Any]]:
    """Parallel execution of investigate_one for all questions."""
    print(f"[Investigator] Starting parallel investigation of {len(questions)} questions...")
    
    tasks = []
    # Identify factual/exposure questions (use answer_only mode) vs deep questions
    for q in questions:
        # Heuristic: questions starting with 'List of' or about 'US companies' are factual/exposure
        is_exposure = q.startswith("List of") or "US companies" in q or "supply chain" in q
        tasks.append(_investigate_one(q, search_tool, answer_only=is_exposure))
        
    results = await asyncio.gather(*tasks)
    print(f"[Investigator] Completed: {len(results)}/{len(questions)} questions with results")
    return results

async def _investigate_one(question: str, search_tool: SearchTool, answer_only: bool = False) -> Dict[str, Any]:
    """Execute a single investigation step."""
    # Run sync search in thread pool to avoid blocking
    loop = asyncio.get_running_loop()
    
    # Use 'answer_only' mode if applicable (requires SearchTool update or manual handling)
    # Since SearchTool might not strictly support answer_only argument in run_in_executor easily without lambda
    # We will use the standard search but extract answer
    
    try:
        if answer_only:
             # If search_tool supports answer_only, use it. Otherwise standard.
             # Based on our previous discussion, we assume search_tool.search handles regular queries.
             # But to implement answer_only logic:
             response = await loop.run_in_executor(
                None, 
                lambda: search_tool.search(question, max_results=1, deep=False) # Minimal results
             )
        else:
            response = await loop.run_in_executor(
                None, 
                lambda: search_tool.search(question, max_results=3, deep=False)
            )
        
        return {
            "question": question,
            "results": response.results if response else [],
            "answer_only": answer_only
        }
    except Exception as e:
        print(f"[!] Investigation failed for '{question}': {e}")
        return {"question": question, "results": [], "error": str(e)}

def format_investigation_context(results: List[Dict[str, Any]]) -> str:
    """Format investigation results into a single context string."""
    blocks = []
    for r in results:
        q = r['question']
        
        # Format results
        content_block = f"### Question: {q}\n"
        
        if r.get('results'):
            # Check for AI summary first
            ai_summary = next((res for res in r['results'] if res.title == "[Tavily AI Summary]"), None)
            
            if ai_summary:
                 content_block += f"**Direct Answer**: {ai_summary.content}\n"
            
            # Add top result if not answer-only mode
            if not r.get('answer_only', False):
                count = 0
                for res in r['results']:
                    if res.title == "[Tavily AI Summary]": continue
                    content_block += f"- [{res.title}]: {res.content[:300]}...\n"
                    count += 1
                    if count >= 2: break
        else:
            if r.get('error'):
                content_block += f"Error: {r['error']}\n"
            else:
                content_block += "No relevant results found.\n"
        
        blocks.append(content_block)
            
    return "\n\n".join(blocks)
