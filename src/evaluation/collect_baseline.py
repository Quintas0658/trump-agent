#!/usr/bin/env python3
"""
Baseline Collector
==================
CLI tool for pasting in Gemini's baseline output (G[·]).

Usage:
    python -m src.evaluation.collect_baseline --date 2026-01-28
"""

import os
import sys
import argparse
from datetime import datetime, date
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from supabase import create_client


def get_supabase_client():
    """Initialize Supabase client."""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_ANON_KEY")
    if not url or not key:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_ANON_KEY")
    return create_client(url, key)


def get_snapshot(client, target_date: date):
    """Fetch snapshot for the given date."""
    response = client.table("daily_snapshots").select("*").eq(
        "snapshot_date", target_date.isoformat()
    ).limit(1).execute()
    
    return response.data[0] if response.data else None


def get_evaluation_entry(client, target_date: date):
    """Fetch or create evaluation log entry."""
    response = client.table("evaluation_log").select("*").eq(
        "eval_date", target_date.isoformat()
    ).limit(1).execute()
    
    return response.data[0] if response.data else None


def save_baseline(client, target_date: date, snapshot_id: str, baseline_output: str):
    """Save baseline output to evaluation log."""
    data = {
        "eval_date": target_date.isoformat(),
        "snapshot_id": snapshot_id,
        "baseline_output": baseline_output
    }
    
    response = client.table("evaluation_log").upsert(
        data, on_conflict="eval_date"
    ).execute()
    
    return response.data[0]["id"] if response.data else None


def main():
    parser = argparse.ArgumentParser(description="Collect Gemini baseline output")
    parser.add_argument("--date", type=str, required=True, help="Date to collect for (YYYY-MM-DD)")
    parser.add_argument("--file", type=str, help="Optional: Read baseline from file instead of stdin")
    args = parser.parse_args()
    
    target_date = datetime.strptime(args.date, "%Y-%m-%d").date()
    
    print(f"[*] Collecting baseline for: {target_date}")
    
    # Initialize client
    client = get_supabase_client()
    
    # Check if snapshot exists
    snapshot = get_snapshot(client, target_date)
    if not snapshot:
        print(f"[!] No snapshot found for {target_date}. Run snapshot.py first.")
        sys.exit(1)
    
    snapshot_id = snapshot["id"]
    print(f"[*] Found snapshot: {snapshot_id}")
    
    # Show existing agent output if available
    eval_entry = get_evaluation_entry(client, target_date)
    if eval_entry and eval_entry.get("agent_output"):
        print("\n" + "="*60)
        print("AGENT OUTPUT (F) - Preview:")
        print("="*60)
        print(eval_entry["agent_output"][:1000] + "...")
        print("")
    
    # Get baseline from file or stdin
    if args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            baseline_output = f.read()
        print(f"[*] Read baseline from: {args.file}")
    else:
        print("\n" + "="*60)
        print("PASTE GEMINI'S OUTPUT BELOW")
        print("(End with Ctrl+D on Unix or Ctrl+Z on Windows)")
        print("="*60)
        
        lines = []
        try:
            while True:
                line = input()
                lines.append(line)
        except EOFError:
            pass
        
        baseline_output = "\n".join(lines)
    
    if not baseline_output.strip():
        print("[!] No baseline output provided. Aborting.")
        sys.exit(1)
    
    # Save to database
    print(f"\n[*] Saving baseline output ({len(baseline_output)} chars)...")
    eval_id = save_baseline(client, target_date, snapshot_id, baseline_output)
    print(f"[*] Saved to evaluation_log: {eval_id}")
    
    # Also save to local file for reference
    os.makedirs("baselines", exist_ok=True)
    baseline_file = f"baselines/{target_date.strftime('%Y-%m-%d')}_gemini.md"
    with open(baseline_file, "w", encoding="utf-8") as f:
        f.write(f"# Gemini Baseline Output: {target_date}\n\n")
        f.write(baseline_output)
    print(f"[*] Saved to: {baseline_file}")
    
    print("\n✅ Baseline collected! Now run score_evaluation.py to compare.")


if __name__ == "__main__":
    main()
