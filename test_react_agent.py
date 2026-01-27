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
from src.input.truth_social import TruthSocialScraper, MockTruthSocialScraper, TruthPost
from src.tools.search import SearchTool
from src.memory.post_store import PostStore
from src.agent.tool_executor import create_tool_executor
from src.agent.react_loop import run_react_analysis

# Multi-Agent Deep Digging imports
try:
    from src.agent.decomposer import decompose_questions
    from src.agent.investigator import investigate_all, format_investigation_context
    MULTI_AGENT_ENABLED = True
except ImportError as e:
    print(f"[!] Multi-agent modules not available: {e}")
    MULTI_AGENT_ENABLED = False

load_dotenv()


# ============================================================================
# KNOWLEDGE ACCUMULATION HELPERS
# ============================================================================

def get_active_hotspots(days: int = 7) -> dict:
    """Query world_facts for recent HIGH/CRITICAL events, grouped by region.
    
    Returns:
        dict: {region: [event_summaries]} for active hotspots
    """
    from supabase import create_client
    
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_ANON_KEY")
    
    if not supabase_url or not supabase_key:
        print("[!] Supabase credentials not found, skipping hotspot lookup")
        return {}
    
    try:
        client = create_client(supabase_url, supabase_key)
        cutoff = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
        
        response = client.table("world_facts").select(
            "region, event_summary, significance, event_date"
        ).gte("event_date", cutoff).in_(
            "significance", ["HIGH", "CRITICAL"]
        ).order("event_date", desc=True).execute()
        
        if not response.data:
            print("[Hotspots] No recent high-significance events found")
            return {}
        
        # Group by region
        hotspots = {}
        for row in response.data:
            region = row.get("region", "GLOBAL")
            if region not in hotspots:
                hotspots[region] = []
            hotspots[region].append(row["event_summary"])
        
        print(f"[Hotspots] Found {len(hotspots)} active regions: {list(hotspots.keys())}")
        return hotspots
        
    except Exception as e:
        print(f"[!] Hotspot lookup failed: {e}")
        return {}


def generate_hotspot_queries(hotspots: dict) -> list:
    """Generate search queries for each active hotspot region.
    
    Args:
        hotspots: {region: [event_summaries]}
        
    Returns:
        list: Search queries like "Iran crisis latest 24h January 2026"
    """
    region_keywords = {
        "MENA": "Iran Middle East",
        "LATAM": "Venezuela Latin America",
        "EUROPE": "Europe EU NATO",
        "ASIA": "China Korea Asia",
        "GLOBAL": "UN international",
        "DOMESTIC": "US domestic federal"
    }
    
    queries = []
    # Use specific 2-day date range for better search results
    today = datetime.now()
    yesterday = today - timedelta(days=1)
    date_range = f"{yesterday.strftime('%B %d')}-{today.strftime('%d %Y')}"  # e.g., "January 26-27 2026"
    
    for region in hotspots.keys():
        keywords = region_keywords.get(region, region)
        query = f"{keywords} news {date_range}"
        queries.append(query)
    
    return queries


async def extract_and_store_facts(search_results: list, client) -> int:
    """Extract structured facts from Tavily results and store in world_facts.
    
    Args:
        search_results: List of SearchResult objects from Tavily
        client: GeminiClient for LLM extraction
        
    Returns:
        int: Number of facts stored
    """
    import json
    from supabase import create_client
    
    # 1. Combine search results into text
    combined_text = ""
    for res in search_results:
        for item in res.results:
            combined_text += f"[{res.query}] {item.title}: {item.content}\n"
    
    if len(combined_text) < 100:
        print("[Facts] Not enough search content to extract facts")
        return 0
    
    # Limit to avoid token overflow
    combined_text = combined_text[:12000]
    
    # 2. Ask LLM to extract structured facts
    date_str = datetime.now().strftime("%Y-%m-%d")
    
    extract_prompt = f"""You are a fact extraction system. Today is {date_str}.
Extract VERIFIED FACTS from the news below. Only extract concrete events that happened, not opinions.

[News Content]
{combined_text}

[Output Format]
Return a JSON array. Each fact must have:
- event_date: YYYY-MM-DD format (use {date_str} if unclear)
- event_summary: One sentence describing what happened
- actors: Array of key actors ["Person1", "Country1"]
- region: One of [MENA, LATAM, EUROPE, ASIA, DOMESTIC, GLOBAL]
- event_type: One of [military_action, sanction, tariff, diplomacy, protest, policy, economic]
- significance: One of [LOW, MEDIUM, HIGH, CRITICAL]

Return ONLY valid JSON, no markdown. Extract 3-5 most important facts."""

    try:
        if hasattr(client, 'generate'):
            response = client.generate(extract_prompt, temperature=0.2)
            content = response.content
        else:
            response = client.client.models.generate_content(
                model=client.model,
                contents=extract_prompt
            )
            content = response.text
        
        # Parse JSON
        clean_content = content.replace("```json", "").replace("```", "").strip()
        facts = json.loads(clean_content)
        
        if not isinstance(facts, list):
            facts = [facts]
        
        print(f"[Facts] Extracted {len(facts)} facts from search results")
        
    except Exception as e:
        print(f"[!] Fact extraction failed: {e}")
        return 0
    
    # 3. Store facts in Supabase
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_ANON_KEY")
    
    if not supabase_url or not supabase_key:
        print("[!] Supabase credentials not found, skipping fact storage")
        return 0
    
    try:
        db = create_client(supabase_url, supabase_key)
        stored_count = 0
        
        for fact in facts:
            # Check for duplicates (same summary on same date)
            existing = db.table("world_facts").select("id").eq(
                "event_summary", fact.get("event_summary", "")
            ).execute()
            
            if existing.data:
                continue  # Skip duplicate
            
            # Insert
            db.table("world_facts").insert({
                "event_date": fact.get("event_date", date_str),
                "event_summary": fact.get("event_summary", "Unknown event"),
                "actors": fact.get("actors", []),
                "region": fact.get("region", "GLOBAL"),
                "event_type": fact.get("event_type", "policy"),
                "significance": fact.get("significance", "MEDIUM"),
                "verified": False  # Auto-extracted, not manually verified
            }).execute()
            
            stored_count += 1
            print(f"[Facts] Stored: {fact.get('event_summary', '')[:60]}...")
        
        print(f"[Facts] Stored {stored_count} new facts to world_facts table")
        return stored_count
        
    except Exception as e:
        print(f"[!] Fact storage failed: {e}")
        return 0


# ============================================================================
# MAIN FUNCTIONS
# ============================================================================


async def fetch_recent_posts(store: PostStore, hours: int = 48) -> list:
    """Fetch posts from the last N hours, using cache if fresh."""
    print(f"[*] Fetching posts from the last {hours} hours...")
    
    # 1. Check Cache Freshness (Cost Saving)
    last_fetched = await store.get_last_fetch_time()
    posts = []
    
    should_scrape = True
    if last_fetched:
        # Handle timezone naive vs aware
        if last_fetched.tzinfo:
            now = datetime.now(last_fetched.tzinfo)
        else:
            now = datetime.utcnow()
            
        delta = now - last_fetched
        
        # Threshold: 60 minutes
        if delta < timedelta(minutes=60):
             print(f"[*] Data is fresh (fetched {int(delta.total_seconds()//60)} mins ago). Skipping Apify.")
             should_scrape = False
             
             # Retrieve from DB as dicts
             cutoff_date = (datetime.utcnow() - timedelta(hours=hours)).date()
             end_date = (datetime.utcnow() + timedelta(days=1)).date()
             
             db_posts = store.get_posts_in_range(start_date=cutoff_date, end_date=end_date, limit=50)
             
             # Convert back to TruthPost objects
             for p in db_posts:
                 # p is dict
                 # Handle ISO string parsing
                 c_str = p['created_at'].replace("Z", "+00:00")
                 try:
                     created_at_dt = datetime.fromisoformat(c_str)
                 except:
                     created_at_dt = datetime.utcnow() # Fallback
                     
                 tp = TruthPost(
                     id=p['post_id'],
                     text=p['text'],
                     created_at=created_at_dt,
                     media_urls=[], 
                     reply_count=0,
                     repost_count=0,
                     like_count=0,
                     is_repost=False,
                     original_author=None
                 )
                 posts.append(tp)
             print(f"[*] Loaded {len(posts)} posts from Supabase cache.")

    # 2. Apify Fetch (If needed)
    if should_scrape:
        try:
            ts = TruthSocialScraper()
            raw_posts = ts.fetch_recent_posts(username="realDonaldTrump", max_posts=30, use_incremental=False)
            posts = raw_posts
            
            # Save strictly new posts to DB (upsert handles logic)
            if posts:
                print(f"[*] Saving {len(posts)} fresh posts to DB...")
                store.save_posts(posts)
                
        except Exception as e:
            print(f"[!] Primary scraper failed: {e}")
            posts = []
    
    if not posts and should_scrape: # Fallback if both DB and Scraper fail/empty
        print("[!] No posts found. Switching to Mock Scraper.")
        ts = MockTruthSocialScraper()
        posts = ts.fetch_recent_posts(max_posts=30)
    
    # Filter by time
    # Ensure all posts have datetime objects
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    # Be careful with timezones. Best to make cutoff aware if posts are aware.
    cutoff = cutoff.replace(tzinfo=None) 
    
    filtered_posts = []
    for p in posts:
        # Normalize to naive UTC for comparison
        if p.created_at.tzinfo:
            created = p.created_at.astimezone(datetime.now().astimezone().tzinfo).replace(tzinfo=None)
            # Actually simplest is just replace tzinfo=None if it's UTC
            created = p.created_at.replace(tzinfo=None)
        else:
            created = p.created_at

        if created > cutoff:
            filtered_posts.append(p)
            
    print(f"[*] Returning {len(filtered_posts)} posts for analysis.")
    return filtered_posts


async def gather_context(posts: list, client, search_tool) -> tuple:
    """Gather context by generating queries via LLM (fusing Posts + Insider Emails + Hotspots).
    
    Returns:
        tuple: (context_str, search_results) - search_results for fact extraction
    """
    print("\n" + "=" * 60)
    print("PHASE 1: DETERMINISTIC CONTEXT GATHERING (DATA FUSION)")
    print("=" * 60)
    
    # 0. [NEW] Read Active Hotspots from world_facts
    print("[Context] Step 0: Loading active hotspots from world_facts...")
    hotspots = get_active_hotspots(days=7)
    hotspot_context = ""
    if hotspots:
        hotspot_context = "\n" + "=" * 50 + "\n"
        hotspot_context += "⚠️ MANDATORY ANALYSIS: ACTIVE GLOBAL HOTSPOTS\n"
        hotspot_context += "(You MUST include a section analyzing these regions)\n"
        hotspot_context += "=" * 50 + "\n"
        for region, events in hotspots.items():
            hotspot_context += f"\n### {region} Region:\n"
            for event in events[:4]:  # Show up to 4 events per region
                hotspot_context += f"  - {event}\n"
        hotspot_context += "\n" + "=" * 50 + "\n"
        print(f"[Context] Loaded {sum(len(v) for v in hotspots.values())} events from {len(hotspots)} regions")
    
    # 1. Fetch Email Context (Data Fusion)
    print("[Context] Fetching Politico Briefings (to inform search query generation)...")
    email_context_str = ""
    emails = []
    
    try:
        from src.input.email_client import EmailClient
        email_client = EmailClient()
        emails = email_client.fetch_politico_emails()
        if emails:
            print(f"[Context] Found {len(emails)} Politico emails.")
            for e in emails:
                email_context_str += f"\n[INTERNAL MEMO / EMAIL] From: {e['sender']}\nSubject: {e['subject']}\nBody Snippet: {e['body_text'][:1500]}...\n---\n"
        else:
            print("[Context] No recent Politico emails found.")
    except Exception as e:
        print(f"[!] Email fetch failed: {e}")

    # 2. Generate Queries via LLM (includes hotspot awareness)
    print("[Context] Asking Gemini to generate targeted search queries (Process-aware)...")
    combined_post_text = "\n".join([f"- {p.text}" for p in posts[:15]])
    
    date_str = datetime.now().strftime("%B %d %Y")
    
    query_prompt = f"""You are a Strategic Intelligence DETECTIVE, not a librarian. The date is {date_str}.
    
    [Input 1: The Public Signal (Truth Social)]
    {combined_post_text}
    
    [Input 2: The Insider Briefing (Politico emails)]
    {email_context_str}
    
    [Input 3: Known Global Hotspots]
    {hotspot_context}
    
    YOUR MISSION: Generate 8-10 PENETRATING search queries. You are not here to verify facts - you are here to EXPOSE hidden connections.
    
    === DETECTIVE SEARCH PROTOCOL ===
    
    1. BACKGROUND PENETRATION (For any named person):
       - Who is this person? Their profession, political leanings, controversy history.
       - If a victim is mentioned (e.g. Alex Pretti), search "Alex Pretti profession background Minneapolis" - find the human story, not just the headline.
    
    2. MARKET CORRELATION MONITORING:
       - For EVERY political move, generate a query about immediate market reaction.
       - "Gold price January 27 2026" | "Korean won USD exchange rate today" | "private prison stocks today"
       - The money never lies.
    
    3. OPPOSITION NARRATIVE SEARCH:
       - Don't just search what Trump says. Search what his TARGETS are saying back.
       - If Trump attacks South Korea, search "South Korea government response to US tariffs"
       - If Trump attacks Minnesota, search "Minnesota governor Tim Walz statement today"
    
    4. OMISSION DETECTION:
       - Compare Politico briefings with Trump's posts - what is Politico talking about that Trump is SILENT on?
       - That silence is often the real story. Search for that topic's latest developments.
    
    5. TIMELINE CORRELATION:
       - If Trump makes a triumphant announcement (e.g. "hostages freed"), search for the TIMING.
       - "Middle East crisis timeline January 2026" - is he announcing this to distract from something else?
    
    === OUTPUT ===
    Return ONLY a Python list of 8-10 strings. No markdown. Append {datetime.now().year} to ensure freshness.
    
    Example output:
    ["Alex Pretti nurse Minneapolis background profession", "gold price spike January 27 2026", "South Korea government official response US tariffs", "Tim Walz statement federal intervention Minneapolis", "USS Abraham Lincoln Persian Gulf timeline January", "Korean won exchange rate today", "private prison stocks GEO CoreCivic today", "what Politico is reporting that Trump ignores"]
    """
    
    try:
        if hasattr(client, 'generate'):
            response = client.generate(query_prompt, temperature=0.7)
            content = response.content
        else:
            response = client.client.models.generate_content(
                model=client.model,
                contents=query_prompt
            )
            content = response.text

        import ast
        clean_content = content.replace("```python", "").replace("```json", "").replace("```", "").strip()
        queries = ast.literal_eval(clean_content)
        if not isinstance(queries, list):
            queries = ["Trump latest news", "US politics top stories"]
    except Exception as e:
        print(f"[!] Info generation failed: {e}")
        queries = ["Trump latest news"]

    print(f"[Context] Generated {len(queries)} LLM queries: {queries}")
    
    # 3. [NEW] Add Hotspot-driven queries (24h updates for each active region)
    hotspot_queries = generate_hotspot_queries(hotspots) if hotspots else []
    if hotspot_queries:
        print(f"[Context] Added {len(hotspot_queries)} hotspot queries: {hotspot_queries}")
    
    all_queries = queries + hotspot_queries
    print(f"[Context] Total queries: {len(all_queries)}")
    
    # 4. Execute parallel searches (Tavily)
    print("[Context] Executing parallel searches (Tavily)...")
    search_results = await search_tool.parallel_search(all_queries)
    
    # 5. Build context string
    context_lines = []
    
    # Add Hotspot Context first (Agent Memory)
    if hotspot_context:
        context_lines.append(hotspot_context)
    
    # Add Email Context
    if email_context_str:
        context_lines.append(email_context_str)

    # Add Search Results
    for res in search_results:
        for item in res.results:
            context_lines.append(f"- [{res.query}] {item.title}: {item.content[:250]}...")
            
    unique_context = "\n".join(list(set(context_lines)))
    
    # Compress context to prevent Vertex AI timeout (recommended: 8k chars)
    MAX_CONTEXT_CHARS = 8000
    if len(unique_context) > MAX_CONTEXT_CHARS:
        print(f"[*] Compressing context from {len(unique_context)} to {MAX_CONTEXT_CHARS} chars")
        unique_context = unique_context[:MAX_CONTEXT_CHARS] + "\n[...truncated for token efficiency...]"
    
    print(f"[*] Gathered {len(unique_context)} chars of initial context.")
    
    # ========================================================================
    # PHASE 2: MULTI-AGENT DEEP DIGGING (NEW)
    # ========================================================================
    investigation_context = ""
    if MULTI_AGENT_ENABLED:
        try:
            print("\n" + "=" * 60)
            print("PHASE 2: MULTI-AGENT DEEP INVESTIGATION (GPT-4o + Tavily)")
            print("=" * 60)
            
            # Convert posts to dict format for decomposer
            posts_as_dicts = [{"text": p.text, "created_at": str(p.created_at)} for p in posts]
            
            # Convert hotspots to list format
            hotspots_list = []
            for region, events in hotspots.items():
                for event in events:
                    hotspots_list.append({"region": region, "headline": event})
            
            # Step 1: GPT-4o decomposes situation into investigative questions
            questions = await decompose_questions(
                posts=posts_as_dicts,
                emails=emails,
                hotspots=hotspots_list
            )
            
            if questions:
                print(f"[Deep Dig] GPT-4o generated {len(questions)} investigative questions")
                for i, q in enumerate(questions[:5], 1):
                    print(f"  Q{i}: {q[:80]}..." if len(q) > 80 else f"  Q{i}: {q}")
                if len(questions) > 5:
                    print(f"  ... and {len(questions) - 5} more")
                
                # Step 2: Parallel investigation via Tavily
                results = await investigate_all(questions, search_tool)
                
                # Step 3: Format results for final analysis
                investigation_context = format_investigation_context(results)
                print(f"[Deep Dig] Investigation complete: {len(investigation_context)} chars of findings")
        except Exception as e:
            print(f"[!] Multi-agent deep digging failed: {e}")
            investigation_context = ""
    
    # Combine initial context with investigation results
    final_context = unique_context
    if investigation_context:
        final_context += "\n\n" + investigation_context
    
    # Return both context and search_results (for fact extraction)
    return final_context, search_results


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
[System Role]
You are a "Power Dynamics & Systems Physics Engine".
Your goal is NOT to simulate a "Strategist", but to deconstruct complex political events into their atomic power components using First Principles Thinking.

**CORE AXIOM: "Energy (Resources/Power) is never created or destroyed, only transferred."**

[METHODOLOGY: THE 4-STEP PHYSICS DERIVATION]

1.  **Extract Atomic Facts (The "What")**:
    -   Strip all adjectives, emotions, and "intentions".
    -   Identify PHYSICAL MOVES: Who moved Money? Who moved Law? Who moved Violence? Who moved Attention?
    -   Identify CONSTRAINTS: What serves as the hard ceiling? (Time, Budget, Biology).

2.  **Calculate Incentive Functions (The "Why")**:
    -   Assume all actors are rational utility maximizers.
    -   What is the specific utility being maximized? (Survival, Wealth Extraction, Power Consolidation).
    -   Ignore moral justifications. Plot the "Cost vs. Benefit" curve.

3.  **Measure System Entropy (The Distraction)**:
    -   High Entropy (Noise/Chaos) in Sector A is often manufactured to mask Low Entropy (Precise Execution) in Sector B.
    -   Find the "Heat Sink": Where is the narrative heat being dumped? (e.g., "Culture War" tweets).
    -   Find the "Work": Where is the structural change happening quietly? (e.g., Regulatory appointments).

4.  **Close the Causal Loop**:
    -   Format: "Incentive [A] constrained by [B] necessitated Action [C], releasing Narrative [D] as heat."

[THE 4-DIMENSIONAL LENS]

A.  **Resource Physics (The Wallet)**
    -   Do not analyze "Policy"; analyze "wallet weight".
    -   Who got richer TODAY? Who got poorer TODAY?
    -   Trace the specific asset class (Equity, Commodity, Currency, Contract).

B.  **Narrative as Heat Shield (Entropy)**
    -   Treat every "Outrageous Tweet" as a flare.
    -   Timeline Analysis: Tweet at 3:00 PM matches WHAT filing/order/movement at 3:00 PM?
    -   What story is being "drowned out"?

C.  **Power Mechanics (Monopoly on Violence)**
    -   Power = The ability to inflict consequence.
    -   Who gained the legal right to punish today? (Tom Homan, DOJ, Treasury).
    -   Who lost the shield of immunity?

D.  **Biological Base Drive (The Lizard Brain)**
    -   Strip political terms. Use biological terms: "Tribal Safety", "Resource Anxiety", "Alpha Dominance".
    -   How does this specific narrative trigger dopamine or cortisol in the base?

**EVIDENCE GRADING (MANDATORY)**:
- **[FACT]**: Physical observation (e.g., "Signed order", "Price moved").
- **[INFERENCE]**: Logical derivation ($A \to B$).
- **[HYPOTHESIS]**: Untested theory.

**Step 3: Tradeable Alpha (Market Implications)**
Translate the political noise into specific investment logic.
- **Direct Impact**: Which sectors/tickers benefit immediately if his narrative becomes reality? (e.g., Prisons, Defense, Border Tech).
- **Second-Order Effects**: Where is the market mispricing the *probability* of his execution? (e.g., "The market thinks he's bluffing about Canada, but the appointment of X suggests he isn't. Short CAD.").

[Output Format]
**CRITICAL**: The final report must be written in **Sharp, Cynical, and Insightful CHINESE (Simplified)**.

**READABILITY RULES (MUST FOLLOW)**:
1. **每段开头加一句话摘要** - 用 📌 标记。
2. **拒绝宏大叙事，寻找具体交易** - 在分析"里子"时，必须回答：**"具体是哪笔钱/哪个公司触发了这件事？"** (Naming names is mandatory if known).
3. **短句优先** - 最多25字一句。
4. **每个战线结尾加"投资要点"** - 用 💰 标记。
5. **文末加"速查表"**。

**Style Guide**:
- **Tone**: 像凌晨3点给老板发的内部备忘录。直接，冷血。
- **Language**: 用金融/政治"黑话"。
- **Avoid**: 不要像教书先生一样讲大道理。要像试图通过内幕消息赚钱的交易员。

Structure your response as:
# 🦈 首席策略师深夜备忘录 ({date_str})

## 📊 30秒速读 (Executive Summary)
- **今日主线**: [一句话核心判断]
- **最大风险**: [一句话]
- **最佳交易**: [一个具体 ticker + 方向]

---

## 🚨 核心博弈 (The Real Game)
📌 [一句话概括他在干什么]

(展开分析：What is he *actually* doing vs. what he says he is doing. Be blunt. CONNECT THE DOTS.)

---

## 1. 战线一: [Name]
📌 [一句话概括这条战线]

- **表面 (The Noise)**: [简述他说了什么]
- **里子 (The Signal)**: [深挖。**如果有具体公司/利益集团（如 Coupang, Greenoaks），必须点名！** 不要只谈政治逻辑，要谈商业逻辑。]

💰 **投资要点**:
- Long: [ticker]
- Short: [ticker]
- Watch: [ticker]

---

## 2. 战线二: [Name]
...

---

## 📋 速查交易表 (Quick Reference)
| 方向 | 标的 | 理由 |
|------|------|------|
| Long | XXX | 简短理由 |
| Short | YYY | 简短理由 |
| Watch | ZZZ | 触发条件 |

---

## 🔗 约束关联图 (Cross-Battlefront Constraint Map)
**[MANDATORY]** 画出至少 3 条战线之间的 **约束级关联**。
格式: `[战线A: 约束X] → 强迫 → [战线B: 行动Y]`

示例:
- `[债务上限: 2025年7月违约] → 强迫 → [共和党清洗: Massie 必须在5月预算投票前被清除]`
- `[韩国: FDI 承诺 deadline] → 强迫 → [关税: 必须在Q2财报前施压]`

| 约束来源 | 触发条件 | 被迫行动 |
|----------|----------|----------|
| [战线A: 具体约束] | [日期/数字] | [战线B: 具体行动] |
| ... | ... | ... |

---

## 📅 硬约束清单 (Hard Constraints Discovered)
**[MANDATORY]** 列出所有从搜索中发现的 **硬约束** (日期/预算/法律)。

| 战线 | 约束类型 | 具体约束 | 来源 |
|------|----------|----------|------|
| 韩国 | DATE | [贸易协议批准 deadline: ???] | [搜索结果#X] |
| 债务 | DATE | [违约点: mid-July to Oct 2025] | [搜索结果#Y] |
| 明州 | BUDGET | [联邦部署预算上限: ???] | [如未知则标 UNKNOWN] |

---

## 🔮 接下来的剧本 (Next 48h)
**[MANDATORY]** 每个预测必须绑定一个 **具体约束**。
格式: `预测: [事件] 将在 [日期] 发生，因为 [约束条件]。`

示例:
- 预测: 韩国特使团将在 **1月30日前** 抵美，因为 **关税生效日为2月1日**。
- 预测: Massie 初选挑战者将在 **2月15日前** 获得 MAGA 背书，因为 **肯塔基初选登记截止日为3月1日**。
"""
    return prompt


async def generate_daily_summary(client, full_report: str) -> str:
    """Generate a high-density summary via LLM for long-term memory."""
    print("[Memory] Generating high-density summary for long-term storage...")
    
    prompt = f"""
    You are the "Memory Encoder" for an AI strategy agent.
    Your job is to compress the following Daily Analysis Report into a dense, information-rich summary.
    
    Future agents will read this summary to understand the context of this day.
    
    [Requirements]
    1. **Preserve Key Predictions**: Specific dates, names, and expected actions.
    2. **Preserve Alpha**: Trade ideas and sectors mentioned.
    3. **Preserve "The Real Game"**: The core political maneuver identified.
    4. **Format**: Bullet points, extremely concise. Max 300 words.
    5. **Language**: Chinese (Simplified).
    
    [Full Report]
    {full_report}
    
    [Output]
    Return ONLY the summary text.
    """
    
    try:
        if hasattr(client, 'generate'):
            response = client.generate(prompt, temperature=0.3)
            return response.content
        else:
             response = client.client.models.generate_content(
                model=client.model,
                contents=prompt
            )
             return response.text
    except Exception as e:
        print(f"[!] Summary generation failed: {e}")
        # Fallback to regex extraction
        match = re.search(r"## 🚨 核心博弈 \(The Real Game\)\n(.*?)\n##", full_report, re.DOTALL)
        return match.group(1).strip() if match else full_report[:500]


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
        posts = await fetch_recent_posts(store=post_store, hours=48)
        
        if not posts:
            print("[!] No posts found.")
            return
        
        # 4. Save posts to memory
        saved = post_store.save_posts(posts)
        print(f"[*] Saved {saved} posts to Supabase")
        
        # 5. Gather Initial Context (Deterministic) + Search Results for Fact Extraction
        initial_context, search_results = await gather_context(posts, client, search_tool)
        
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
        
        # 8. Save result
        print("\n" + "=" * 60)
        print("REACT ANALYSIS COMPLETE")
        print("=" * 60)
        
        # 8a. [NEW] Extract and store facts from search results
        print("\n[Knowledge Accumulation] Extracting facts from search results...")
        facts_stored = await extract_and_store_facts(search_results, client)
        print(f"[Knowledge Accumulation] {facts_stored} new facts added to world_facts")
        
        # 8b. Save to Supabase
        from datetime import date
        
        # Generative Summary (Memory Compression)
        summary_text = await generate_daily_summary(client, result)
            
        report_id = post_store.save_daily_report(
            report_date=date.today(),
            report_content=result,
            summary=summary_text,
        )
        print(f"[*] Report saved to Supabase: {report_id} (Memory Compressed)")
        
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
