import pytest
from datetime import datetime
from src.agent.judgments import JudgmentEngine, Judgment0Result
from src.agent.stop_rules import StopRuleEngine, AgentState, StopReason
from src.agent.devils_advocate import DevilsAdvocate

def test_judgment_0_logic():
    engine = JudgmentEngine()
    # Mock search results with action keywords
    mock_results = [{"content": "Trump signed a new executive order on tariffs today."}]
    j0 = engine.judgment_0(datetime.utcnow(), mock_results)
    assert j0.result == Judgment0Result.ACTION_PRESENT
    assert len(j0.actions_found) > 0

def test_stop_rule_engine():
    engine = StopRuleEngine(max_loops=3)
    state = AgentState(loop_count=3)
    signal = engine.check(state)
    assert signal is not None
    assert signal.reason == StopReason.LOOP_EXHAUSTED

def test_devils_advocate_severity():
    advocate = DevilsAdvocate()
    result = advocate.challenge("Trump will win", ["Tweet from Trump"], reasoning_depth=3)
    # Depth >= 3 should trigger a high severity challenge
    assert any(c.severity == "high" for c in result.challenges)
    assert result.confidence_adjustment < 0
