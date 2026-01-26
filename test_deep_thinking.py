#!/usr/bin/env python3
"""
Deep Thinking Test: Enhanced Context-Aware Strategic Brain
==========================================================
Purpose: Test a "free-form thinking" prompt that acts as your second brain,
incorporating:
1. 24-hour post filtering
2. Entity extraction & specific context search
3. General news context search
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

load_dotenv()

# ============================================
# PART 1: Fetch Posts (Last 24h)
# ============================================

def fetch_recent_posts(hours: int = 24) -> list:
    """Fetch posts from the last N hours."""
    print(f"[*] Fetching posts from the last {hours} hours...")
    
    # Try real scraper first
    try:
        ts = TruthSocialScraper()
        # Fetch a bit more to ensure coverage
        posts = ts.fetch_recent_posts(username="realDonaldTrump", max_posts=30, use_incremental=False)
    except Exception as e:
        print(f"[!] Primary scraper failed: {e}")
        posts = []
    
    # Fallback to Mock
    if not posts:
        print("[!] No posts found (or API key missing). Switching to Mock Scraper.")
        ts = MockTruthSocialScraper()
        posts = ts.fetch_recent_posts(max_posts=30)
    
    # Filter by time
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    # Ensure timezone awareness compatibility (naive vs aware)
    recent_posts = []
    for p in posts:
        # Normalize to UTC naive for comparison if needed
        created = p.created_at.replace(tzinfo=None)
        if created > cutoff:
            recent_posts.append(p)
            
    print(f"[*] Found {len(recent_posts)} posts in the last {hours} hours.")
    return recent_posts


# ============================================
# PART 2: Context Gathering
# ============================================

async def gather_context(posts, client, search_tool):
    """Gather entity-specific and general news context."""
    print("\n[Context] Starting comprehensive context gathering...")
    
    # 1. Generate Queries using LLM (Step 1 of 2)
    print("[Context] asking Gemini to generate targeted search queries...")
    combined_text = "\n".join([f"- {p.text}" for p in posts[:15]]) # Limit to recent 15 to fit context
    
    # Define date early for prompt context
    date_str = datetime.now().strftime("%B %d %Y")
    
    query_prompt = f"""You are a research assistant. The current date is {date_str}.
I need to verify the claims in these Truth Social posts.
Generate 5-7 specific Google search queries to check the facts, find the original news source, or get context.
Focus on:
1. Specific events mentioned (e.g., "Tom Homan Minnesota visit").
2. Specific names and their recent actions.
3. Broader topics if specific details are vague.
4. APPEND the year {datetime.now().year} to queries to ensure freshness.

POSTS:
{combined_text}

OUTPUT:
Return ONLY a Python list of strings, e.g., ["query 1", "query 2"]. Do not add markdown or explanations.
"""
    try:
        response = client.generate(query_prompt, temperature=0.7)
        # robust parsing
        import ast
        clean_content = response.content.replace("```python", "").replace("```json", "").replace("```", "").strip()
        queries = ast.literal_eval(clean_content)
        if not isinstance(queries, list):
            raise ValueError("LLM did not return a list")
    except Exception as e:
        print(f"[!] LLM Query Generation failed: {e}. Fallback to basic queries.")
        queries = ["Trump latest news", "US politics top stories today"]

    # Add General Context
    queries.append(f"top global news {date_str}")
    
    print(f"[Context] Generated {len(queries)} search queries:")
    for q in queries:
        print(f"  - {q}")
        
    # 2. Parallel Search (Step 2 of 2)
    print("[Context] Executing parallel searches (Tavily)...")
    search_results = await search_tool.parallel_search(queries)
    
    context_lines = []
    for res in search_results:
        for item in res.results:
            context_lines.append(f"- [{res.query}] {item.title}: {item.content[:250]}...")
            
    unique_context = list(set(context_lines))
    print(f"[*] Gathered {len(unique_context)} unique context items.")
    return "\n".join(unique_context)


# ============================================
# PART 3: Deep Thinking Analysis
# ============================================

def deep_think(posts, context_str, client, yesterday_context: str = None):
    """Analyze posts using the 'Second Brain' prompt with context and memory."""
    
    # Format posts
    post_texts = []
    for p in posts:
        created = p.created_at.strftime("%Y-%m-%d %H:%M")
        clean_text = re.sub(r'<[^>]+>', '', p.text).strip()
        post_texts.append(f"[{created}] {clean_text}")
    
    combined_posts = "\n\n---\n\n".join(post_texts)
    
    prompt = f"""你是我的战略思考伙伴，一个拥有这几天全球新闻背景的顶级情报分析师。

**背景上下文 (Real-time Context):**
{context_str}

---

**分析对象 (Trump's Last 24h Posts):**
{combined_posts}

---

**昨日分析回顾 (Previous Context - Optional):**
{yesterday_context if yesterday_context else "[无历史记录 - 这是首次分析]"}

---

**任务指令:**

【角色设定】 你现在是一位全球顶尖的 “宏观地缘与量化叙事”分析官。你擅长从杂乱的政治辞令中剥离出真实的权力逻辑，并能敏锐地察觉到“话语”对全球资产定价和产业布局的影响。

【任务指令】 请结合提供的 背景上下文 (News Context) 和 Trump 的帖子 (The Feed)，进行深度的“全息式”战略复盘。

【分析维度】

现实扭曲力场 (Distortion Filter): * 他的陈述与事实之间的“Gap”在哪里？这种扭曲是出于无知，还是刻意地**“重新定义现实”**以创造政治合法性？

如果没有对应的新闻背景，他是否正在进行“议程先行”的压力测试 (A/B Testing)？

战略真空与消声 (Strategic Omission): * 今天哪个重大的“房间里的大象”被他彻底无视了？

这种**“战略性沉默”**是在为秘密谈判腾出空间，还是在试图冷处理某个对其不利的叙事螺旋？

战术支点与时机 (Tactical Pivoting): * 为什么是现在？ 这个帖子的发布是否精准对冲了某个负面头条（如：委内瑞拉行动的波折或国内罢工）？

他是在“带节奏”（Lead the cycle）还是在“灭火”（Respond to pressure）？

叙事原形 (Narrative Archetype): * 他今天在扮演什么角色？（守护者、受害者、复仇者、还是建设者？）

将散乱帖子串联起来：他是在推销**“堡垒经济”，还是在通过攻击特定人物（如奥马尔）来巩固“内部纯洁性”**？

Alpha 传导路径 (Transmission Channels): * 二级市场影响： 哪些特定板块（能源、军工、加元、比特币）会因这些信号产生异常波动？

具体的交易假设： 请给出一个“如果...那么...”的逻辑链。例如：“如果他继续攻击加美边境，那么做空加元的窗口期将缩短至 24 小时。”

对手方视角 (Counter-party Reaction): * 如果我是马杜罗、硅谷硬件商或中国出海企业，我从这些帖子里读到的**“最后通牒”**是什么？

【输出要求】 请用一种冷静、专业且略带犀利的口吻进行复盘，不要有AI味，要像在机密简报室里对核心决策者说话。
"""

    print(f"\n[Gemini] Sending to {client.thinking_model} with thinking_budget=8192...")
    
    response = client.generate(
        prompt,
        model=client.thinking_model,
        thinking_budget=8192,
        max_tokens=16384  # INCREASED to accommodate thinking budget + full response
    )
    
    # Print usage
    print("\n" + "=" * 60)
    print("ENHANCED DEEP THINKING RESULTS")
    print("=" * 60)
    
    if response.usage:
        print(f"[Usage] Prompt tokens: {response.usage.get('prompt_tokens', '?')}")
        print(f"[Usage] Completion tokens: {response.usage.get('completion_tokens', '?')}")
    print(f"[Usage] THINKING tokens: {response.thoughts_token_count if response.thoughts_token_count else 'Not reported'}")
    
    print("\n" + "-" * 60)
    print("RESPONSE:")
    print("-" * 60)
    print(response.content)
    
    return response.content


# ============================================
# MAIN
# ============================================

async def main():
    print("=" * 60)
    print("ENHANCED THINKING TEST: Context + 24h Filter + Memory")
    print("=" * 60)
    
    try:
        # 1. Init Client and Memory
        client = get_gemini_client()
        search_tool = SearchTool()
        post_store = PostStore()
        print(f"[*] Client initialized: {client.thinking_model}")
        print(f"[*] Memory store initialized: PostStore")
        
        # 2. Fetch Posts
        posts = fetch_recent_posts(hours=48) # Use 48h to ensure we get data for the test mock
        
        if not posts:
            print("[!] No posts found in the last 24h.")
            return
        
        # 2.5 Save posts to Supabase
        saved_count = post_store.save_posts(posts)
        print(f"[*] Saved {saved_count} posts to Supabase.")

        # 3. Gather Context (News)
        context_str = await gather_context(posts, client, search_tool)
        
        # 3.5 Load Yesterday's Report (if exists)
        yesterday_report = post_store.get_past_report(days_ago=1)
        yesterday_context = None
        if yesterday_report:
            print(f"[*] Found yesterday's report: {yesterday_report.get('report_date')}")
            yesterday_context = yesterday_report.get('summary') or yesterday_report.get('report_content', '')[:2000]
        else:
            print("[*] No previous report found. This is the first run.")
        
        # 4. Deep Thinking (with memory context)
        result = deep_think(posts, context_str, client, yesterday_context)
        
        # 5. Save Report to Supabase
        from datetime import date
        report_id = post_store.save_daily_report(
            report_date=date.today(),
            report_content=result,
            summary=result[:500] + "..." if len(result) > 500 else result,  # Simple summary
            key_entities=[],  # Could extract later
            key_hypotheses=[]
        )
        print(f"[*] Report saved to Supabase: {report_id}")
        
        # 6. Also save locally
        with open("deep_thinking_enhanced.md", "w") as f:
            f.write("# Enhanced Deep Thinking Analysis\n\n")
            f.write(result)
        print("[*] Result also saved to deep_thinking_enhanced.md")
        
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
