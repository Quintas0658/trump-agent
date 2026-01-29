#!/usr/bin/env python3
"""
Evaluation Scorer
=================
LLM-as-Judge to compare F (Agent) vs G (Baseline) outputs.
Also fetches Y(t) - actual news - to check prediction accuracy.

Usage:
    python -m src.evaluation.score_evaluation --date 2026-01-28
"""

import os
import sys
import json
import argparse
from datetime import datetime, date, timedelta
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from supabase import create_client
from src.agent.llm_client import get_gemini_client
from src.tools.search import SearchTool


JUDGE_PROMPT = """You are an impartial intelligence analyst tasked with judging two competing strategic memos.

## Report A (Our Agent)
{agent_output}

---

## Report B (Baseline Gemini)
{baseline_output}

---

## Ground Truth (What Actually Happened on {next_date})
{ground_truth}

---

## Your Evaluation Task

Score EACH report on four dimensions (0-10 scale):

1. **Information Density**: How many concrete facts, names, dates, and numbers are cited?
   - 0-3: Vague generalities
   - 4-6: Some specifics
   - 7-10: Dense with verifiable details

2. **Specificity**: Does the report name specific companies, Tickers, or individuals?
   - 0-3: Only mentions sectors/themes
   - 4-6: Names some actors
   - 7-10: Precise "who benefits" analysis with named entities

3. **Causal Logic**: Is there a complete causal chain (Incentive → Constraint → Action → Outcome)?
   - 0-3: Just summarizes news
   - 4-6: Some "why" analysis
   - 7-10: Clear multi-step logic with evidence

4. **Prediction Accuracy**: Did the report's predictions match what actually happened (Ground Truth)?
   - 0-3: No predictions or all wrong
   - 4-6: Some hits
   - 7-10: Accurate foresight

## Output Format (JSON ONLY)

Return ONLY valid JSON, no markdown:

{{
  "report_a": {{
    "info_density": <score>,
    "specificity": <score>,
    "causal_logic": <score>,
    "prediction_accuracy": <score>,
    "total": <sum>,
    "strengths": "<one sentence>",
    "weaknesses": "<one sentence>"
  }},
  "report_b": {{
    "info_density": <score>,
    "specificity": <score>,
    "causal_logic": <score>,
    "prediction_accuracy": <score>,
    "total": <sum>,
    "strengths": "<one sentence>",
    "weaknesses": "<one sentence>"
  }},
  "winner": "A" | "B" | "TIE",
  "reasoning": "<one paragraph explaining the verdict>"
}}
"""


def get_supabase_client():
    """Initialize Supabase client."""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_ANON_KEY")
    if not url or not key:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_ANON_KEY")
    return create_client(url, key)


def get_evaluation_entry(client, target_date: date):
    """Fetch evaluation log entry."""
    response = client.table("evaluation_log").select("*").eq(
        "eval_date", target_date.isoformat()
    ).limit(1).execute()
    
    return response.data[0] if response.data else None


def fetch_ground_truth(search_tool, target_date: date) -> str:
    """Fetch actual news from the day AFTER the analysis (Y(t))."""
    next_date = target_date + timedelta(days=1)
    
    queries = [
        f"Trump news {next_date.strftime('%B %d %Y')}",
        f"US politics major news {next_date.strftime('%B %d %Y')}",
        f"stock market moves {next_date.strftime('%B %d %Y')}"
    ]
    
    results = []
    for q in queries:
        try:
            response = search_tool.search(q, max_results=3)
            for r in response.results:
                results.append(f"- {r.title}: {r.content[:200]}")
        except Exception as e:
            print(f"[!] Search failed for '{q}': {e}")
    
    return "\n".join(results) if results else "No ground truth data available."


def run_judge(gemini_client, agent_output: str, baseline_output: str, ground_truth: str, next_date: date) -> dict:
    """Run LLM-as-Judge to score both reports."""
    prompt = JUDGE_PROMPT.format(
        agent_output=agent_output[:8000],  # Truncate to avoid token limits
        baseline_output=baseline_output[:8000],
        ground_truth=ground_truth[:3000],
        next_date=next_date.strftime("%Y-%m-%d")
    )
    
    response = gemini_client.generate(prompt, temperature=0.1)
    
    # Parse JSON from response
    content = response.content.strip()
    # Clean up markdown if present
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
    
    return json.loads(content)


def save_scores(client, target_date: date, scores: dict, ground_truth: str):
    """Save scores to evaluation log."""
    data = {
        "eval_date": target_date.isoformat(),
        "ground_truth_json": json.dumps({"raw": ground_truth}, ensure_ascii=False),
        "horizontal_scores": json.dumps({
            "agent": scores.get("report_a", {}),
            "baseline": scores.get("report_b", {})
        }, ensure_ascii=False),
        "vertical_scores": json.dumps({
            "prediction_accuracy_a": scores.get("report_a", {}).get("prediction_accuracy", 0),
            "prediction_accuracy_b": scores.get("report_b", {}).get("prediction_accuracy", 0)
        }, ensure_ascii=False),
        "winner": scores.get("winner", "TIE"),
        "notes": scores.get("reasoning", ""),
        "scored_at": datetime.utcnow().isoformat()
    }
    
    response = client.table("evaluation_log").update(data).eq(
        "eval_date", target_date.isoformat()
    ).execute()
    
    return response.data[0] if response.data else None


def main():
    parser = argparse.ArgumentParser(description="Score F vs G evaluation")
    parser.add_argument("--date", type=str, required=True, help="Date to evaluate (YYYY-MM-DD)")
    args = parser.parse_args()
    
    target_date = datetime.strptime(args.date, "%Y-%m-%d").date()
    
    print(f"[*] Scoring evaluation for: {target_date}")
    
    # Initialize clients
    db = get_supabase_client()
    gemini = get_gemini_client()
    search = SearchTool()
    
    # Fetch evaluation entry
    eval_entry = get_evaluation_entry(db, target_date)
    if not eval_entry:
        print(f"[!] No evaluation entry found for {target_date}")
        sys.exit(1)
    
    agent_output = eval_entry.get("agent_output", "")
    baseline_output = eval_entry.get("baseline_output", "")
    
    if not agent_output:
        print("[!] No agent output (F) found. Run the main agent first.")
        sys.exit(1)
    
    if not baseline_output:
        print("[!] No baseline output (G) found. Run collect_baseline.py first.")
        sys.exit(1)
    
    print(f"[*] Agent output: {len(agent_output)} chars")
    print(f"[*] Baseline output: {len(baseline_output)} chars")
    
    # Fetch ground truth (Y(t))
    print("[*] Fetching ground truth (next day's news)...")
    ground_truth = fetch_ground_truth(search, target_date)
    print(f"[*] Ground truth: {len(ground_truth)} chars")
    
    # Run LLM-as-Judge
    print("[*] Running LLM-as-Judge...")
    scores = run_judge(gemini, agent_output, baseline_output, ground_truth, target_date + timedelta(days=1))
    
    # Display results
    print("\n" + "="*60)
    print("EVALUATION RESULTS")
    print("="*60)
    
    print("\n📊 Report A (Our Agent):")
    a = scores.get("report_a", {})
    print(f"   Info Density:       {a.get('info_density', '?')}/10")
    print(f"   Specificity:        {a.get('specificity', '?')}/10")
    print(f"   Causal Logic:       {a.get('causal_logic', '?')}/10")
    print(f"   Prediction Accuracy:{a.get('prediction_accuracy', '?')}/10")
    print(f"   TOTAL:              {a.get('total', '?')}/40")
    print(f"   Strengths: {a.get('strengths', '-')}")
    print(f"   Weaknesses: {a.get('weaknesses', '-')}")
    
    print("\n📊 Report B (Baseline Gemini):")
    b = scores.get("report_b", {})
    print(f"   Info Density:       {b.get('info_density', '?')}/10")
    print(f"   Specificity:        {b.get('specificity', '?')}/10")
    print(f"   Causal Logic:       {b.get('causal_logic', '?')}/10")
    print(f"   Prediction Accuracy:{b.get('prediction_accuracy', '?')}/10")
    print(f"   TOTAL:              {b.get('total', '?')}/40")
    print(f"   Strengths: {b.get('strengths', '-')}")
    print(f"   Weaknesses: {b.get('weaknesses', '-')}")
    
    print("\n" + "="*60)
    winner = scores.get("winner", "TIE")
    if winner == "A":
        print("🏆 WINNER: Report A (Our Agent)")
    elif winner == "B":
        print("🏆 WINNER: Report B (Baseline)")
    else:
        print("🤝 RESULT: TIE")
    print("="*60)
    print(f"\n{scores.get('reasoning', '')}")
    
    # Save to database
    print("\n[*] Saving scores to database...")
    save_scores(db, target_date, scores, ground_truth)
    print("[*] Done!")
    
    # Save detailed report
    os.makedirs("evaluations", exist_ok=True)
    report_file = f"evaluations/{target_date.strftime('%Y-%m-%d')}_eval.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(scores, f, ensure_ascii=False, indent=2)
    print(f"[*] Detailed report saved to: {report_file}")


if __name__ == "__main__":
    main()
