#!/usr/bin/env python3
"""
Autonomous Gemini Thinking Test
===============================
Purpose: Grant Gemini 3 Pro "Agency" to use tools autonomously based on high-level directives.
Methodology: "The Mission Command"
1. GPT-4o (Director): Decomposes the situation into a "Mission" (Constraints & Anomalies).
2. Gemini 3 (Agent): Receives the Mission -> Thinks -> Calls Tools -> Solves.
"""

import os
import sys
import json
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from src.agent.llm_client import get_gemini_client, GeminiClient
from src.input.truth_social import TruthSocialScraper
from src.tools.search import SearchTool
from src.memory.post_store import PostStore
from src.agent.openai_client import OpenAIClient
from src.agent.decomposer import DECOMPOSER_PROMPT

# Import existing tools to wrap as functions for Gemini
# We need to expose: tavily_search, get_recent_posts, query_world_facts

load_dotenv()

class GeminiThinkingAgent:
    def __init__(self):
        self.gemini = get_gemini_client()
        self.openai = OpenAIClient()
        self.post_store = PostStore()
        self.search_tool = SearchTool()
        self.truth_scraper = TruthSocialScraper()
        
    def search_web(self, query: str):
        """Tool: Search the live internet."""
        print(f"🔍 [Tool: Search] Searching for: '{query}'")
        # SearchTool.search is likely async, so we need to run it synchronously
        # If we are not in an active loop, asyncio.run works.
        # If we ARE, we need a different approach. 
        # Strategy: Run the whole script synchronously. 
        return asyncio.run(self.search_tool.search(query))

    def get_trump_posts_tool(self, hours: int = 24):
        """Tool: Get recent posts."""
        print(f"📱 [Tool: Posts] Fetching last {hours}h...")
        end_date = datetime.now()
        start_date = end_date - timedelta(hours=hours)
        # PostStore.get_posts_in_range is synchronous
        posts = self.post_store.get_posts_in_range(start_date, end_date, limit=50) 
        return [p['text'] for p in posts]

    def query_world_facts(self, keyword: str):
        """Tool: Query internal facts."""
        print(f"📚 [Tool: Facts] Querying for: '{keyword}'")
        return f"Found 3 facts related to {keyword} (Stub)"

    def run_mission(self):
        print("🚀 [Mission Control] Initializing Autonomous Gemini...")
        
        # 1. Get Context (Director Phase)
        print("[Director] Gathering Context...")
        end_date = datetime.now()
        start_date = end_date - timedelta(hours=24)
        posts = self.post_store.get_posts_in_range(start_date, end_date, limit=20)
        
        if not posts:
            print("[Director] No posts found in DB. Fetching live...")
            # Fetch live if DB empty - TruthSocialScraper is likely async
            # asyncio.run(self.truth_scraper.get_profile_posts(...))
            scraped = asyncio.run(self.truth_scraper.get_profile_posts("realDonaldTrump", limit=10))
            self.post_store.save_posts(scraped)
            posts = [{"created_at": p.created_at, "text": p.text} for p in scraped]
            
        posts_text = "\n".join([f"[{p.get('created_at')}] {p.get('text')}" for p in posts])
        
        # 2. GPT-4o Decomposer (The Director)
        print("[Director] GPT-4o is defining the Mission...")
        director_prompt = f"""You are a "Constraint Hunter" for a Power Physics Engine.
Your job is NOT to ask "Why", but to find the physical boundaries and resource flows.

**CORE AXIOM: "Politics is the art of the possible. Physics defines the possible."**

[SEARCH PROTOCOL: ATOMIC FACT MINING]

1.  **Hunt for Constraints (The Hard Ceiling)**:
    -   Search for *deadlines* (e.g., "debt ceiling expiration date", "trade deal ratification deadline").
    -   Search for *budget limits* (e.g., "federal agency insolvency date").
    -   Search for *physical limits* (e.g., "oil tanker capacity straits of hormuz").

2.  **Trace Resource Flows (The Energy)**:
    -   Don't ask "Who supports this?". Ask "Who funded this?".
    -   Search for "lobbying disclosures", "campaign donations", "contract awards".
    -   Search for "capital flight" (e.g., "Korea foreign direct investment outflow 2026").

3.  **Find Entropy/Anomalies (The Glitch)**:
    -   Search for *timing coincidences*. (e.g., "What else happened on [Date] of tweet?").
    -   Search for *silence*. (e.g., "Official denial of [Event]").

**Task**: Generate 15 SEARCH QUERIES as Mission Directives for an autonomous agent.
- 5 Constraint Queries (Deadlines/Budgets)
- 5 Resource Flow Queries (Money/Contracts)
- 5 Entropy/Anomaly Queries (Timing/Denials)

## RAW DATA (Trump's Recent Posts)
{posts_text[:4000]}

Return as a numbered list:
1. [Constraint] ...
2. [Constraint] ...
...
6. [Resource] ...
...
11. [Anomaly] ...
"""
        
        # Mocking OpenAI response for now to focus on Gemini Autonomous part or use actual client
        gpt_response = self.openai.generate(director_prompt)
        mission_directives = gpt_response.content
        print(f"\n📋 [Mission Directives]:\n{mission_directives}\n")
        
        # 3. Gemini Thinking Loop (The Agent)
        print("🧠 [Agent] Gemini 3 is thinking & executing...")
        
        # We need to bind the actual functions for automatic calling
        # The Gemini SDK expects a list of Callables or Tool objects
        # We'll create a simple dictionary map for manual execution if auto-calling fails, 
        # or pass the functions directly if using the high-level API.
        
        # For simplicity in this test script, we will use the Tool definitions + Manual Loop or Auto
        # Let's try passing the functions directly to the model tools list
        
        tools_list = [self.search_web, self.get_trump_posts_tool, self.query_world_facts]
        
        # Re-initialize client with tools
        # The new Google GenAI SDK allows passing python functions directly to `tools`
        tools_list = [self.search_web, self.get_trump_posts_tool, self.query_world_facts]
        
        # We use the raw client from GeminiClient wrapper to start a chat with tools
        chat = self.gemini.client.chats.create(
            model=self.gemini.model_name, # Use standard model for tool use, or thinking model if supported
            config={
                "tools": tools_list,
                "temperature": 0.0 # Force deterministic tool use
            }
        )
        
        # Restore the system prompt
        agent_system_prompt = f"""
        You are an Autonomous Intelligence Officer.
        Your goal is to execute the following Mission Directives using your tools.
        
        MISSION:
        {mission_directives}
        
        PROTOCOL:
        1. THINK first. (Internal Monologue).
        2. FORMULATE a plan.
        3. CALL tools to execute the plan.
        4. SYNTHESIZE findings into a "Power Physics" report.
        """
        
        print("💬 [Agent] Starting autonomous loop...")
        
        # Send the mission
        # chat.send_message is synchronous in the referenced SDK usage for tools
        response = chat.send_message(agent_system_prompt)
        
        print("\n📝 [Agent First Response]:")
        try:
             print(response.text)
        except:
             print("[No text, likely function call]")
             
        # Simple loop to handle function calls if SDK doesn't auto-resolve (it should if configured)
        # The `google.genai` SDK's `chats.create` with `tools` usually handles the round-trip or provides easy access.
        # Let's inspect the response to see if it's a function call or text.
        
        # For this prototype, we'll print the full conversation history to see the chain of thought.
        for msg in chat._curated_history:
            role = msg.role
            try:
                txt = msg.parts[0].text
                print(f"[{role}]: {txt[:200]}...")
            except:
                print(f"[{role}]: [Complex Part]")

        # Save to artifact
        with open("autonomous_report.md", "w") as f:
            try:
                f.write(response.text if response.text else "No text response")
            except:
                f.write(str(response))
            print("\n💾 Report saved to `autonomous_report.md`")

if __name__ == "__main__":
    agent = GeminiThinkingAgent()
    # Run synchronously
    agent.run_mission()
