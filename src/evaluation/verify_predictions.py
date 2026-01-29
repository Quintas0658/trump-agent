#!/usr/bin/env python3
"""
Prediction Verification Script
===============================
Runs daily to check predictions that have reached their resolve_by date.
Uses LLM to compare predictions against world_facts and determine correctness.

Usage:
    python verify_predictions.py
"""

import os
import sys
from datetime import datetime, date
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

load_dotenv()


def get_due_predictions():
    """Get predictions that need verification (past their resolve_by date)."""
    from supabase import create_client
    
    client = create_client(
        os.getenv("SUPABASE_URL"),
        os.getenv("SUPABASE_ANON_KEY")
    )
    
    today = date.today().isoformat()
    
    response = client.table("predictions").select("*").eq(
        "status", "pending"
    ).lte("resolve_by", today).execute()
    
    return response.data or []


def get_relevant_facts(made_at: str, resolve_by: str):
    """Get world_facts that occurred during the prediction window."""
    from supabase import create_client
    
    client = create_client(
        os.getenv("SUPABASE_URL"),
        os.getenv("SUPABASE_ANON_KEY")
    )
    
    response = client.table("world_facts").select(
        "event_date, event_summary, region"
    ).gte("event_date", made_at).lte("event_date", resolve_by).order(
        "event_date", desc=True
    ).execute()
    
    return response.data or []


def verify_prediction(prediction: dict, facts: list) -> dict:
    """Use LLM to judge if prediction was correct.
    
    Returns:
        dict: {"result": "correct|wrong|ambiguous", "explanation": "..."}
    """
    from google import genai
    import json
    
    facts_text = "\n".join([
        f"- [{f['event_date']}] [{f['region']}] {f['event_summary']}"
        for f in facts
    ]) if facts else "（期间没有相关事实记录）"
    
    prompt = f"""作为一个客观的评判者，判断以下预测是否正确。

## 预测信息
- **问题**: {prediction['question']}
- **预测内容**: {prediction['prediction']}
- **置信度**: {prediction['confidence']}%
- **预测日期**: {prediction['made_at']}
- **验证截止**: {prediction['resolve_by']}
- **预测依据**: {prediction['reasoning'] or '未提供'}

## 验证期间发生的事实
{facts_text}

## 判断规则
1. **CORRECT**: 预测的事件确实发生了，或预测的趋势确实出现了
2. **WRONG**: 预测的事件明显没有发生，或发生了相反的情况
3. **AMBIGUOUS**: 证据不足，无法明确判断；或事件仍在进行中

## 输出格式
请只输出 JSON，不要其他内容：
{{"result": "CORRECT|WRONG|AMBIGUOUS", "explanation": "简短说明判断理由"}}
"""
    
    try:
        client = genai.Client()
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
        )
        
        text = response.text.strip()
        # Clean up markdown if present
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
        if text.endswith("```"):
            text = text.rsplit("\n", 1)[0]
        if text.startswith("json"):
            text = text[4:].strip()
        
        return json.loads(text)
        
    except Exception as e:
        print(f"[!] Verification LLM error: {e}")
        return {"result": "AMBIGUOUS", "explanation": f"验证失败: {str(e)}"}


def update_prediction_status(pred_id: str, result: str, explanation: str):
    """Update the prediction status in database."""
    from supabase import create_client
    
    client = create_client(
        os.getenv("SUPABASE_URL"),
        os.getenv("SUPABASE_ANON_KEY")
    )
    
    client.table("predictions").update({
        "status": result.lower(),
        "resolution_notes": explanation,
        "resolved_at": date.today().isoformat()
    }).eq("id", pred_id).execute()


def main():
    print("=" * 60)
    print("PREDICTION VERIFICATION")
    print(f"Date: {date.today()}")
    print("=" * 60)
    
    # Get due predictions
    due = get_due_predictions()
    
    if not due:
        print("\n[✓] No predictions due for verification today.")
        return
    
    print(f"\n[*] Found {len(due)} predictions to verify:\n")
    
    correct = 0
    wrong = 0
    ambiguous = 0
    
    for pred in due:
        print(f"\n--- Verifying: {pred['question'][:60]}...")
        print(f"    Prediction: {pred['prediction'][:60]}...")
        print(f"    Made: {pred['made_at']} | Due: {pred['resolve_by']}")
        
        # Get relevant facts
        facts = get_relevant_facts(pred['made_at'], pred['resolve_by'])
        print(f"    Found {len(facts)} relevant facts")
        
        # Verify
        result = verify_prediction(pred, facts)
        
        print(f"    Result: {result['result']}")
        print(f"    Reason: {result['explanation']}")
        
        # Update database
        update_prediction_status(pred['id'], result['result'], result['explanation'])
        
        if result['result'].upper() == "CORRECT":
            correct += 1
        elif result['result'].upper() == "WRONG":
            wrong += 1
        else:
            ambiguous += 1
    
    # Summary
    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)
    print(f"✓ Correct:   {correct}")
    print(f"✗ Wrong:     {wrong}")
    print(f"? Ambiguous: {ambiguous}")
    
    if correct + wrong > 0:
        accuracy = round(correct / (correct + wrong) * 100, 1)
        print(f"\nToday's Accuracy: {accuracy}%")


if __name__ == "__main__":
    main()
