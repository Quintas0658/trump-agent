#!/usr/bin/env python3
"""
Trump Policy Analysis Agent - CLI Entry Point
"""

import asyncio
import sys
import argparse
import os
from datetime import datetime
from dotenv import load_dotenv

from src.config import config
from src.agent.orchestrator import orchestrator
from src.output.report_generator import report_generator
from src.input.truth_social import TruthSocialScraper, MockTruthSocialScraper

async def analyze_single_tweet(tweet_text: str):
    """Analyze a single tweet and print the report."""
    try:
        briefing = await orchestrator.analyze_tweet(tweet_text)
        markdown = report_generator.generate_markdown(briefing)
        
        print("\n" + "="*50)
        print("ANALYSIS REPORT")
        print("="*50 + "\n")
        print(markdown)
        
    except Exception as e:
        print(f"Error during analysis: {e}")
        import traceback
        traceback.print_exc()

async def generate_daily_brief(username: str, mock: bool = False, include_news: bool = True):
    """The SitRep Phase: Sweep environment, collect pulses, and batch-synthesize intelligence."""
    print(f"[*] Starting Daily Intelligence Cycle for @{username}...")
    
    # 1. Proactive Daily Sweep (Environment Tier)
    from src.input.daily_sweep import DailySweep
    sweep = DailySweep()
    await sweep.run()
    
    # 2. Ingest Pulses (Pulse Tier)
    if mock:
        from src.input.truth_social import MockTruthSocialScraper
        scraper = MockTruthSocialScraper()
    else:
        from src.input.truth_social import TruthSocialScraper
        scraper = TruthSocialScraper()
        
    posts = scraper.fetch_recent_posts(username, max_posts=10)
    
    # Save pulses to M-CLAIM layer (skip in mock mode to avoid network issues)
    from src.memory.claim_store import ClaimStore
    from src.memory.schema import Claim
    
    if mock:
        # In mock mode, just use in-memory claims without DB
        pending_pulses = []
        for post in posts:
            claim = Claim(claim_text=post.text, attributed_to=username, claimed_at=post.created_at)
            pending_pulses.append(claim)
    else:
        claim_store = ClaimStore(orchestrator.event_store.client)
        
        # Insert NEW posts from Apify
        for post in posts:
            claim_store.insert(Claim(
                claim_text=post.text,
                attributed_to=username,
                claimed_at=post.created_at
            ))
        
        # Query ALL pending claims from the last 24h (includes Politico, old Trump posts, etc.)
        print("[*] Querying all pending claims from Supabase (last 24h)...")
        pending_pulses = claim_store.get_pending_claims(limit=50)
        print(f"[*] Found {len(pending_pulses)} pending claims to analyze.")
    
    # Add news signals if requested
    if include_news:
        from src.input.news_aggregator import NewsAggregator, filter_trump_related
        print("[*] Fetching news signals...")
        with NewsAggregator() as aggregator:
            all_news = aggregator.fetch_all(max_per_source=5)
            trump_news = filter_trump_related(all_news)
            for news in trump_news[:5]:
                news_text = f"NEWS: {news.title}. {news.description}"
                claim_store.insert(Claim(
                    claim_text=news_text,
                    attributed_to=news.source,
                    source_url=news.link
                ))
                pending_pulses.append(Claim(claim_text=news_text, attributed_to=news.source))
    
    if not pending_pulses:
        print("[!] No pending claims found to analyze.")
        return None
        
    # 3. Intelligent Batch Synthesis (The SitRep)
    print(f"[*] Synthesizing {len(pending_pulses)} pulses into a Strategic Situation Report...")
    briefing = await orchestrator.analyze_batch(pending_pulses)
    
    # 4. Mark analyzed claims as PROCESSED
    if not mock:
        print("[*] Marking analyzed claims as PROCESSED...")
        for claim in pending_pulses:
            if claim.id:
                claim_store.update_status(claim.id, "PROCESSED")
        print(f"[*] Marked {len([c for c in pending_pulses if c.id])} claims as PROCESSED.")
    
    # 5. Output Report
    from src.output.report_generator import report_generator
    report_generator.print_briefing(briefing)
    return briefing

def main():
    load_dotenv()
    
    # Check for missing config
    missing = config.validate()
    if missing:
        print(f"[!] Warning: Missing environment variables: {', '.join(missing)}")
        print("[!] Some features may not work correctly.")
    
    parser = argparse.ArgumentParser(description="Trump Policy Analysis Agent")
    parser.add_argument("--tweet", type=str, help="Analyze a specific tweet/text")
    parser.add_argument("--username", type=str, default="realDonaldTrump", help="Truth Social username to track")
    parser.add_argument("--daily", action="store_true", help="Generate daily brief from recent posts")
    parser.add_argument("--mock", action="store_true", help="Use mock data instead of live APIs")
    parser.add_argument("--output-file", type=str, help="Save report to file (for GitHub Actions email)")
    
    args = parser.parse_args()
    
    if args.tweet:
        asyncio.run(analyze_single_tweet(args.tweet))
    elif args.daily:
        try:
            briefing = asyncio.run(generate_daily_brief(args.username, args.mock))
            
            # Save to file if requested
            if args.output_file:
                if briefing:
                    markdown = report_generator.generate_markdown(briefing)
                    with open(args.output_file, 'w', encoding='utf-8') as f:
                        f.write(markdown)
                    print(f"[*] Report saved to {args.output_file}")
                else:
                    # Create a minimal report even if no briefing
                    with open(args.output_file, 'w', encoding='utf-8') as f:
                        f.write(f"# Daily Intelligence Brief\n\n")
                        f.write(f"**Date**: {datetime.now().strftime('%Y-%m-%d')}\n\n")
                        f.write("No new intelligence signals detected today.\n")
                    print(f"[*] Empty report saved to {args.output_file}")
        except Exception as e:
            print(f"[!] Error generating daily brief: {e}")
            import traceback
            traceback.print_exc()
            
            # Still create a report file for GitHub Actions
            if args.output_file:
                with open(args.output_file, 'w', encoding='utf-8') as f:
                    f.write(f"# Daily Intelligence Brief - Error\n\n")
                    f.write(f"**Date**: {datetime.now().strftime('%Y-%m-%d')}\n\n")
                    f.write(f"Error during analysis: {e}\n")
                print(f"[*] Error report saved to {args.output_file}")
            sys.exit(1)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
