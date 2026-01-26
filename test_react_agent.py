#!/usr/bin/env python3
"""
ReAct Agent Test: Autonomous Tool Calling Demo
===============================================
Purpose: Test the ReAct loop with actual Gemini function calling.
The agent can autonomously decide to:
1. Search for news (Tavily)
2. Recall past analysis (Supabase)
3. Get entity history
"""

import os
import sys
import asyncio
from datetime import datetime, timedelta
import re
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from src.agent.llm_client import get_gemini_client
from src.input.truth_social import TruthSocialScraper, MockTruthSocialScraper
from src.tools.search import SearchTool
from src.memory.post_store import PostStore
from src.agent.tool_executor import create_tool_executor
from src.agent.react_loop import run_react_analysis

load_dotenv()


def fetch_recent_posts(hours: int = 48) -> list:
    """Fetch posts from the last N hours."""
    print(f"[*] Fetching posts from the last {hours} hours...")
    
    try:
        ts = TruthSocialScraper()
        posts = ts.fetch_recent_posts(username="realDonaldTrump", max_posts=30, use_incremental=False)
    except Exception as e:
        print(f"[!] Primary scraper failed: {e}")
        posts = []
    
    if not posts:
        print("[!] No posts found. Switching to Mock Scraper.")
        ts = MockTruthSocialScraper()
        posts = ts.fetch_recent_posts(max_posts=30)
    
    # Filter by time
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    recent_posts = []
    for p in posts:
        created = p.created_at.replace(tzinfo=None)
        if created > cutoff:
            recent_posts.append(p)
            
    print(f"[*] Found {len(recent_posts)} posts in the last {hours} hours.")
    print(f"[*] Found {len(recent_posts)} posts in the last {hours} hours.")
    return recent_posts


async def gather_context(posts: list, client, search_tool) -> str:
    """Gather context by generating queries via LLM and searching Tavily."""
    print("\n" + "=" * 60)
    print("PHASE 1: DETERMINISTIC CONTEXT GATHERING")
    print("=" * 60)
    
    # 1. Generate Queries (Step 1 of 2)
    print("[Context] asking Gemini to generate targeted search queries...")
    combined_text = "\n".join([f"- {p.text}" for p in posts[:15]])
    
    date_str = datetime.now().strftime("%B %d %Y")
    
    query_prompt = f"""You are a research assistant. The current date is {date_str}.
I need to verify the claims in these Truth Social posts.
Generate 5-7 specific Google search queries to check the facts, find the original news source, or get context.
Focus on:
1. Specific events mentioned.
2. Specific names and their recent actions.
3. Broader topics if specific details are vague.
4. APPEND the year {datetime.now().year} to queries to ensure freshness.

POSTS:
{combined_text}

OUTPUT:
Return ONLY a Python list of strings, e.g., ["query 1", "query 2"]. Do not add markdown.
"""
    try:
        response = client.generate(query_prompt, temperature=0.7)
        import ast
        clean_content = response.content.replace("```python", "").replace("```json", "").replace("```", "").strip()
        queries = ast.literal_eval(clean_content)
        if not isinstance(queries, list):
            queries = ["Trump latest news", "US politics top stories today"]
    except Exception as e:
        print(f"[!] Info generation failed: {e}")
        queries = ["Trump latest news"]

    print(f"[Context] Generated {len(queries)} search queries: {queries}")
    
    # 2. Add Mandatory Strategic Source Query
    strategic_query = 'site:politico.com OR site:axios.com "Trump" after:2026-01-25'
    print(f"[Context] Adding strategic source query: {strategic_query}")
    queries.append(strategic_query)

    # 2. Parallel Search (Step 2 of 2)
    print("[Context] Executing parallel searches (Tavily)...")
    search_results = await search_tool.parallel_search(queries)
    
    context_lines = []
    for res in search_results:
        for item in res.results:
            context_lines.append(f"- [{res.query}] {item.title}: {item.content[:250]}...")
            
    unique_context = "\n".join(list(set(context_lines)))
    print(f"[*] Gathered {len(unique_context)} chars of initial context.")
    return unique_context


def build_react_prompt(posts: list, initial_context: str) -> str:
    """Build the initial prompt for the ReAct agent."""
    
    # Format posts
    post_texts = []
    for p in posts:
        created = p.created_at.strftime("%Y-%m-%d %H:%M")
        clean_text = re.sub(r'<[^>]+>', '', p.text).strip()
        post_texts.append(f"[{created}] {clean_text}")
    
    combined_posts = "\n\n---\n\n".join(post_texts)
    date_str = datetime.now().strftime("%B %d, %Y")
    
    prompt = f"""[System Role]
You are a **Chief Macro Strategist** at a top-tier hedge fund, specializing in **Political Risk & Narrative Analysis**.
Your clients are institutional investors who need to understand the *real* power dynamics and market implications behind the noise.

[Objective]
Analyze Donald Trump's social media feed from the last 24 hours.
Deconstruct his narratives to reveal the underlying political strategy, power moves, and actionable market triggers (Alpha).

[Input Data]
- **Date**: {date_str}
- **The Feed**: 
{combined_posts}
- **Context (Ground Truth)**: 
{initial_context}

[Analysis Instructions]
You must think like a Machiavellian strategist. Do not be a fact-checker. Do not be moralistic.
Focus on **Intent**, **Leverage**, and **Consequences**.

**Step 1: Narrative Clustering**
Group the chaotic feed into 3-4 distinct "Battlefronts" (e.g., Domestic Purge, Geopolitical Escalation, Culture War).
Do not analyze posts in isolation; see them as coordinated campaigns.

**Step 2: Deep Strategic Decoding (Per Battlefront)**
For each battlefront, provide a deep-dive analysis covering:
1.  **The Legitimization Play**: How are exaggerations or specific framings being used to manufacture consent for future executive actions? (e.g., Inflating fraud numbers to justify federal takeover of state powers).
2.  **The "Why Now?"**: Why is this specific narrative being pushed *today*? What damaging story is he trying to drown out (The Controlled Burn)?
3.  **The Power Signal**: Who is the real target? Is this a loyalty test for his own party, or a warning shot to institutions?

**Step 3: Tradeable Alpha (Market Implications)**
Translate the political noise into specific investment logic.
- **Direct Impact**: Which sectors/tickers benefit immediately if his narrative becomes reality? (e.g., Prisons, Defense, Border Tech).
- **Second-Order Effects**: Where is the market mispricing the *probability* of his execution? (e.g., "The market thinks he's bluffing about Canada, but the appointment of X suggests he isn't. Short CAD.").

[Output Format]
**CRITICAL**: The final report must be written in **Sharp, Cynical, and Insightful CHINESE (Simplified)**.
**Style Guide**:
- **Tone**: Imagine you are sending a late-night internal memo to a trading floor. Be direct, use short sentences, and cut the "official report" fluff.
- **Language**: Use financial/political "black speech" (e.g., instead of "legitimizing action", say "preparing the kill zone" or "manufacturing consent").
- **Avoid**: Do not sound like a translation or a news anchor. Sound like a cynical strategist who has seen it all.

Structure your response as:
# 🦈 首席策略师深夜备忘录 ({date_str})

## 🚨 核心博弈 (The Real Game)
(One paragraph summary: What is he *actually* doing vs. what he says he is doing. Be blunt.)

## 1. 战线一: [Name]
   - **表面 (The Noise)**: [Briefly state what he posted]
   - **里子 (The Signal)**: [Deep dive into the power move. Why this specific lie? Who is he threatening?]
   - **交易员笔记 (Alpha)**: [Specific tickers/sectors. If nothing, say "No trade here".]

## 2. 战线二: [Name]
   ...

## 🔮 接下来的剧本 (Next 48h)
[Specific prediction of the next executive order or news cycle]
"""
    return prompt


async def main():
    print("=" * 60)
    print("REACT AGENT TEST: Autonomous Tool Calling")
    print("=" * 60)
    
    try:
        # 1. Init components
        client = get_gemini_client()
        search_tool = SearchTool()
        post_store = PostStore()
        
        print(f"[*] Client initialized: {client.thinking_model}")
        print(f"[*] Memory store: PostStore")
        print(f"[*] Search tool: Tavily")
        
        # 2. Create Tool Executor
        executor = create_tool_executor(
            search_tool=search_tool,
            post_store=post_store,
        )
        print("[*] Tool Executor created with 3 tools")
        
        # 3. Fetch Posts
        posts = fetch_recent_posts(hours=48)
        
        if not posts:
            print("[!] No posts found.")
            return
        
        # 4. Save posts to memory
        saved = post_store.save_posts(posts)
        print(f"[*] Saved {saved} posts to Supabase")
        
        # 5. Gather Initial Context (Deterministic)
        initial_context = await gather_context(posts, client, search_tool)
        
        # 6. Build ReAct prompt (with context)
        prompt = build_react_prompt(posts, initial_context)
        print(f"[*] Prompt built ({len(prompt)} chars)")
        
        # 7. Run ReAct Loop (the magic happens here!)
        print("\n" + "=" * 60)
        print("STARTING REACT LOOP")
        print("=" * 60)
        
        result = await run_react_analysis(
            client=client,
            executor=executor,
            prompt=prompt,
            max_iterations=5,  # Max tool calls
            thinking_budget=8192,
            verbose=True
        )
        
        # 7. Save result
        print("\n" + "=" * 60)
        print("REACT ANALYSIS COMPLETE")
        print("=" * 60)
        
        # Save to Supabase
        from datetime import date
        report_id = post_store.save_daily_report(
            report_date=date.today(),
            report_content=result,
            summary=result[:500] + "..." if len(result) > 500 else result,
        )
        print(f"[*] Report saved to Supabase: {report_id}")
        
        # Save locally
        with open("react_analysis.md", "w") as f:
            f.write("# ReAct Agent Analysis\n\n")
            f.write(result)
        print("[*] Result saved to react_analysis.md")
        
        # Print preview
        print("\n" + "-" * 60)
        print("ANALYSIS PREVIEW:")
        print("-" * 60)
        print(result[:2000] + "..." if len(result) > 2000 else result)
        
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
