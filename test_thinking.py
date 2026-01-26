#!/usr/bin/env python3
"""
Minimal Test Script: Apify + Gemini Thinking Mode
==================================================
Purpose: Verify that Gemini 2.5 Flash Thinking mode works correctly.

This script:
1. Fetches 20 posts from Truth Social via Apify (full fetch, no incremental)
2. Sends them to Gemini 2.5 Flash with thinking_budget=4096
3. Prints the thinking token count and analysis result
"""

import os
from dotenv import load_dotenv
import httpx

# Load environment variables
load_dotenv()

# ============================================
# PART 1: Fetch Posts from Apify
# ============================================

def fetch_apify_posts(max_posts: int = 20) -> list[dict]:
    """Fetch posts from Apify Truth Social scraper."""
    api_key = os.getenv("APIFY_API_KEY")
    if not api_key:
        raise ValueError("APIFY_API_KEY not set in environment")
    
    task_id = "lissome_jolt~truth-social-scraper-task"
    url = f"https://api.apify.com/v2/actor-tasks/{task_id}/run-sync-get-dataset-items"
    
    run_input = {
        "username": "realDonaldTrump",
        "maxPosts": max_posts,
        "useLastPostId": False,  # FULL fetch, not incremental
        "cleanContent": True,
    }
    
    print(f"[Apify] Fetching {max_posts} posts (useLastPostId=False)...")
    
    with httpx.Client(timeout=180.0) as client:
        response = client.post(url, params={"token": api_key}, json=run_input)
        response.raise_for_status()
        items = response.json()
    
    print(f"[Apify] Successfully fetched {len(items)} posts.")
    return items


# ============================================
# PART 2: Call Gemini 2.5 Flash with Thinking
# ============================================

def analyze_with_thinking(posts: list[dict]) -> str:
    """Analyze posts using Gemini 2.5 Flash with Thinking mode."""
    from google import genai
    from google.genai.types import GenerateContentConfig, ThinkingConfig
    
    # Initialize Vertex AI
    project_id = "trump-analyst"
    location = "us-central1"
    os.environ["GOOGLE_CLOUD_PROJECT"] = project_id
    os.environ["GOOGLE_CLOUD_LOCATION"] = location
    os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"
    
    client = genai.Client()
    
    # Build input text from posts
    post_texts = []
    for i, post in enumerate(posts[:20], 1):
        text = post.get("content") or post.get("text", "")
        # Strip HTML
        import re
        clean_text = re.sub(r'<[^>]+>', '', text).strip()
        if clean_text:
            post_texts.append(f"[Post {i}]: {clean_text[:500]}")
    
    combined_input = "\n\n".join(post_texts)
    
    prompt = f"""You are a strategic intelligence analyst. Analyze the following Truth Social posts from Donald Trump and identify the TOP 3 strategic themes or policy signals. For each theme, provide:
1. Theme Title
2. Summary (2-3 sentences)
3. Strategic Significance

Posts to analyze:
{combined_input}

Respond in JSON format with a "pillars" array containing objects with "title", "summary", and "significance" fields."""

    print(f"\n[Gemini] Sending {len(post_texts)} posts to Gemini 2.5 Flash with Thinking mode...")
    print(f"[Gemini] thinking_budget=4096")
    
    # Call with Thinking mode
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=GenerateContentConfig(
            temperature=0.5,
            max_output_tokens=4096,
            thinking_config=ThinkingConfig(thinking_budget=4096)
        )
    )
    
    # Check for thinking tokens
    print("\n" + "=" * 50)
    print("THINKING MODE RESULTS")
    print("=" * 50)
    
    if hasattr(response, 'usage_metadata'):
        print(f"[Usage] Prompt tokens: {response.usage_metadata.prompt_token_count}")
        print(f"[Usage] Completion tokens: {response.usage_metadata.candidates_token_count}")
        if hasattr(response.usage_metadata, 'thoughts_token_count'):
            print(f"[Usage] THINKING tokens: {response.usage_metadata.thoughts_token_count}")
        else:
            print("[Usage] thoughts_token_count attribute NOT FOUND")
    else:
        print("[Usage] No usage_metadata in response")
    
    print("\n" + "-" * 50)
    print("RAW RESPONSE TEXT:")
    print("-" * 50)
    print(response.text)
    
    return response.text


# ============================================
# MAIN
# ============================================

if __name__ == "__main__":
    print("=" * 60)
    print("MINIMAL TEST: Apify + Gemini 2.5 Flash Thinking")
    print("=" * 60)
    
    try:
        # Step 1: Fetch posts
        posts = fetch_apify_posts(max_posts=20)
        
        if not posts:
            print("[Error] No posts returned from Apify.")
            exit(1)
        
        # Step 2: Analyze with Thinking
        result = analyze_with_thinking(posts)
        
        print("\n" + "=" * 60)
        print("TEST COMPLETE")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        exit(1)
