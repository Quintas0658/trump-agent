import pytest
import asyncio
from unittest.mock import MagicMock, patch
from datetime import datetime
from src.agent.orchestrator import AgentOrchestrator
from src.memory.schema import Event, Hypothesis, HypothesisStatus, ActionType

@pytest.mark.asyncio
async def test_get_comprehensive_context():
    orchestrator = AgentOrchestrator()
    
    # Mock stores
    orchestrator.event_store.get_recent = MagicMock(return_value=[
        Event(statement="Trump signed an order", occurred_at=datetime(2025, 1, 1))
    ])
    orchestrator.hypothesis_store.get_pending = MagicMock(return_value=[
        Hypothesis(statement="Tariffs will increase", falsifiable_condition="Mexico retaliates", status=HypothesisStatus.PROPOSED)
    ])
    
    context = await orchestrator._get_comprehensive_context()
    
    assert "RECENT VERIFIED EVENTS:" in context
    assert "Trump signed an order" in context
    assert "PENDING HYPOTHESES:" in context
    assert "Tariffs will increase" in context

def test_consolidate_memory():
    orchestrator = AgentOrchestrator()
    
    # Mock a pending hypothesis
    mock_hyp = Hypothesis(
        id="hyp-123",
        statement="Trump will increase tariffs on Mexico",
        falsifiable_condition="Mexico signs deal",
        status=HypothesisStatus.PROPOSED
    )
    orchestrator.hypothesis_store.get_pending = MagicMock(return_value=[mock_hyp])
    orchestrator.hypothesis_store.update_status = MagicMock()
    
    # New event that overlaps with hypothesis
    new_event = Event(
        statement="Official order: Trump increase tariffs on Mexico trade",
        action_type=ActionType.LEGAL_DOCUMENT
    )
    
    orchestrator._consolidate_memory([new_event])
    
    # Verify update_status was called
    orchestrator.hypothesis_store.update_status.assert_called_once_with(
        "hyp-123",
        HypothesisStatus.STRENGTHENED,
        support_delta=1
    )

def test_consolidate_memory_no_overlap():
    orchestrator = AgentOrchestrator()
    
    mock_hyp = Hypothesis(
        id="hyp-456",
        statement="Mars colony established",
        falsifiable_condition="Elon Musk lands",
        status=HypothesisStatus.PROPOSED
    )
    orchestrator.hypothesis_store.get_pending = MagicMock(return_value=[mock_hyp])
    orchestrator.hypothesis_store.update_status = MagicMock()
    
    new_event = Event(statement="It rained in Seattle today")
    
    orchestrator._consolidate_memory([new_event])
    
    orchestrator.hypothesis_store.update_status.assert_not_called()
