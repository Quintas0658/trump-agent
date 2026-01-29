#!/usr/bin/env python3
"""
Snapshot Generator
==================
Freezes X(t-1) + Y(t-1) as a Markdown file for manual baseline testing.

Usage:
    python -m src.evaluation.snapshot [--date YYYY-MM-DD]
"""

import os
import sys
import json
import argparse
from datetime import datetime, date, timedelta
from dotenv import load_dotenv

load_dotenv()

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from supabase import create_client


def get_supabase_client():
    """Initialize Supabase client."""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_ANON_KEY")
    if not url or not key:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_ANON_KEY")
    return create_client(url, key)


def fetch_posts(client, target_date: date) -> list:
    """Fetch Trump posts for a specific date."""
    start = datetime.combine(target_date, datetime.min.time())
    end = datetime.combine(target_date + timedelta(days=1), datetime.min.time())
    
    response = client.table("trump_posts").select(
        "text, created_at"
    ).gte("created_at", start.isoformat()).lt("created_at", end.isoformat()).order(
        "created_at", desc=False
    ).execute()
    
    return response.data if response.data else []


def fetch_context(client, target_date: date) -> dict:
    """Fetch context: world_facts + emails for a specific date."""
    context = {
        "world_facts": [],
        "emails": []
    }
    
    # World Facts (last 7 days for context)
    cutoff = target_date - timedelta(days=7)
    facts_response = client.table("world_facts").select(
        "event_summary, event_date, region, significance"
    ).gte("event_date", cutoff.isoformat()).lte("event_date", target_date.isoformat()).order(
        "event_date", desc=True
    ).limit(20).execute()
    
    if facts_response.data:
        context["world_facts"] = facts_response.data
    
    # Emails (today only)
    try:
        email_response = client.table("email_sources").select(
            "sender, subject, body_text, received_at"
        ).gte("received_at", target_date.isoformat()).order(
            "received_at", desc=True
        ).limit(10).execute()
        
        if email_response.data:
            context["emails"] = email_response.data
    except Exception as e:
        print(f"[!] Email fetch skipped: {e}")
    
    return context


def generate_markdown(target_date: date, posts: list, context: dict) -> str:
    """Generate a Markdown snapshot for manual analysis."""
    lines = []
    
    # Header
    lines.append(f"# Daily Analysis Input: {target_date.strftime('%Y-%m-%d')}")
    lines.append("")
    lines.append("> **Instructions**: Copy this entire document into Gemini (gemini.google.com) and ask it to analyze.")
    lines.append("")
    
    # Posts Section (X)
    lines.append("## 📱 Trump Posts (X)")
    lines.append("")
    if posts:
        for p in posts:
            created = p.get("created_at", "")[:16].replace("T", " ")
            text = p.get("text", "").replace("\n", " ")[:500]
            lines.append(f"**[{created}]** {text}")
            lines.append("")
    else:
        lines.append("*No posts found for this date.*")
        lines.append("")
    
    # Context Section (Y)
    lines.append("---")
    lines.append("")
    lines.append("## 🌍 Context (Y)")
    lines.append("")
    
    # World Facts
    lines.append("### Known World Facts (Last 7 Days)")
    if context.get("world_facts"):
        for f in context["world_facts"]:
            region = f.get("region", "GLOBAL")
            sig = f.get("significance", "MEDIUM")
            summary = f.get("event_summary", "")
            lines.append(f"- **[{region}]** [{sig}] {summary}")
    else:
        lines.append("*No world facts in database.*")
    lines.append("")
    
    # Emails
    lines.append("### Politico Briefings")
    if context.get("emails"):
        for e in context["emails"]:
            subject = e.get("subject", "No Subject")
            body = e.get("body_text", "")[:800]
            lines.append(f"#### 📧 {subject}")
            lines.append(f"```")
            lines.append(body)
            lines.append(f"```")
            lines.append("")
    else:
        lines.append("*No emails found for this date.*")
    lines.append("")
    
    # Task
    lines.append("---")
    lines.append("")
    lines.append("## 🎯 Your Task")
    lines.append("")
    lines.append("Analyze the above Trump posts in the context of the world facts and briefings.")
    lines.append("")
    lines.append("**Answer these questions:**")
    lines.append("1. What is Trump **really** trying to achieve with these posts?")
    lines.append("2. Who benefits financially from his statements?")
    lines.append("3. What market implications (Long/Short ideas) emerge?")
    lines.append("4. What predictions can you make for the next 48 hours?")
    lines.append("")
    lines.append("**Format**: Write a concise strategic memo in Chinese (Simplified).")
    
    return "\n".join(lines)


def save_snapshot(client, target_date: date, posts: list, context: dict, markdown: str):
    """Save snapshot to database."""
    data = {
        "snapshot_date": target_date.isoformat(),
        "posts_json": json.dumps(posts, ensure_ascii=False),
        "context_json": json.dumps(context, ensure_ascii=False),
        "markdown_content": markdown
    }
    
    # Upsert (update if exists, insert if not)
    response = client.table("daily_snapshots").upsert(
        data, on_conflict="snapshot_date"
    ).execute()
    
    return response.data[0]["id"] if response.data else None


def save_markdown_file(target_date: date, markdown: str, output_dir: str = "snapshots"):
    """Save Markdown to local file."""
    os.makedirs(output_dir, exist_ok=True)
    filename = f"{output_dir}/{target_date.strftime('%Y-%m-%d')}.md"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(markdown)
    return filename


def main():
    parser = argparse.ArgumentParser(description="Generate daily snapshot for evaluation")
    parser.add_argument("--date", type=str, help="Date to snapshot (YYYY-MM-DD), default: today")
    args = parser.parse_args()
    
    # Determine target date
    if args.date:
        target_date = datetime.strptime(args.date, "%Y-%m-%d").date()
    else:
        target_date = date.today()
    
    print(f"[*] Generating snapshot for: {target_date}")
    
    # Initialize client
    client = get_supabase_client()
    
    # Fetch data
    print("[*] Fetching Trump posts...")
    posts = fetch_posts(client, target_date)
    print(f"    Found {len(posts)} posts")
    
    print("[*] Fetching context...")
    context = fetch_context(client, target_date)
    print(f"    Found {len(context.get('world_facts', []))} world facts, {len(context.get('emails', []))} emails")
    
    # Generate Markdown
    print("[*] Generating Markdown...")
    markdown = generate_markdown(target_date, posts, context)
    
    # Save to database
    print("[*] Saving to database...")
    snapshot_id = save_snapshot(client, target_date, posts, context, markdown)
    print(f"    Snapshot ID: {snapshot_id}")
    
    # Save to file
    filename = save_markdown_file(target_date, markdown)
    print(f"[*] Saved to: {filename}")
    
    # Also create initial evaluation_log entry with agent output
    try:
        # Check if today's agent output exists
        report_response = client.table("daily_reports").select(
            "report_content"
        ).eq("report_date", target_date.isoformat()).limit(1).execute()
        
        if report_response.data:
            agent_output = report_response.data[0].get("report_content", "")
            client.table("evaluation_log").upsert({
                "eval_date": target_date.isoformat(),
                "snapshot_id": snapshot_id,
                "agent_output": agent_output
            }, on_conflict="eval_date").execute()
            print(f"[*] Agent output linked to evaluation log")
    except Exception as e:
        print(f"[!] Could not link agent output: {e}")
    
    print(f"\n✅ Snapshot complete! Open {filename} and paste into Gemini.")


if __name__ == "__main__":
    main()
