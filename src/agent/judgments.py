"""Judgment logic - Implements Judgment 0-3 structure."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

from src.config import config
from src.memory.schema import ActionType, Event
from src.memory.event_store import EventStore


class Judgment0Result(str, Enum):
    """Result of Judgment 0: Is there a real-world action?"""
    ACTION_PRESENT = "ACTION_PRESENT"
    LANGUAGE_ONLY = "LANGUAGE_ONLY"


class Judgment1Result(str, Enum):
    """Result of Judgment 1: Is there a clear thesis today?"""
    YES = "YES"
    NO = "NO"
    UNCERTAIN = "UNCERTAIN"


@dataclass
class Judgment0:
    """Output of Judgment 0."""
    result: Judgment0Result
    actions_found: list[Event]
    reasoning: str


@dataclass
class Judgment1:
    """Output of Judgment 1."""
    result: Judgment1Result
    reasoning: str
    # If UNCERTAIN, these are candidate directions to watch
    candidate_directions: list[str] = None


@dataclass
class Judgment2:
    """Output of Judgment 2: Main thesis and competing explanation."""
    main_thesis: str
    thesis_evidence: list[str]
    thesis_confidence: float
    
    # NEW: Strategic Context & Causal Reasoning
    strategic_context: str
    causal_reasoning: str
    
    competing_thesis: str
    competing_evidence: list[str]
    competing_confidence: float
    
    why_main_over_competing: str


@dataclass
class Judgment3:
    """Output of Judgment 3: Falsifiable condition."""
    falsifiable_condition: str
    verification_deadline: datetime
    what_if_triggered: str  # What happens if condition is met


@dataclass
class GiveUpResult:
    """When agent cannot make a confident judgment."""
    message: str
    partial_evidence: list[str]
    search_count: int
    confidence: float = 0.3


class JudgmentEngine:
    """Executes the Judgment 0-3 pipeline."""
    
    def __init__(self, event_store: Optional[EventStore] = None):
        self.event_store = event_store or EventStore()
    
    def judgment_0(
        self, 
        tweet_time: datetime,
        search_results: list[dict],
        window_hours: int = 24
    ) -> Judgment0:
        """Judgment 0: Check if real-world actions exist.
        
        Only ACTION_PRESENT allows Judgment 1 to be YES.
        """
        start_time = tweet_time - timedelta(hours=window_hours)
        
        # Check database for recent actions
        db_actions = self.event_store.get_actions_in_window(start_time, tweet_time)
        
        # Check search results for action indicators
        action_keywords = [
            "signed", "deployed", "arrested", "fired", "appointed",
            "executive order", "military", "sanctions", "troops",
            "aircraft carrier", "strike", "raid"
        ]
        
        found_actions = []
        
        # From database
        found_actions.extend(db_actions)
        
        # From search results
        for result in search_results:
            content = result.get("content", "").lower()
            for keyword in action_keywords:
                if keyword in content:
                    # Create a potential action event
                    found_actions.append(Event(
                        statement=result.get("content", "")[:200],
                        sources=[],
                        entities=[],
                        action_type=ActionType.RESOURCE_DEPLOYMENT,  # Default
                    ))
                    break
        
        if found_actions:
            return Judgment0(
                result=Judgment0Result.ACTION_PRESENT,
                actions_found=found_actions[:5],  # Limit to 5
                reasoning=f"Found {len(found_actions)} real-world actions"
            )
        else:
            return Judgment0(
                result=Judgment0Result.LANGUAGE_ONLY,
                actions_found=[],
                reasoning="No real-world actions found, only language signals"
            )
    
    def judgment_1(
        self,
        j0: Judgment0,
        tweet_content: str,
        search_results: list[dict],
        evidence_confidence: float
    ) -> Judgment1:
        """Judgment 1: Is there a clear thesis today?
        
        Respects Judgment 0 constraint:
        - If J0 = LANGUAGE_ONLY, J1 can only be UNCERTAIN or NO
        - If J0 = ACTION_PRESENT, J1 can be YES/NO/UNCERTAIN
        """
        # Constraint: LANGUAGE_ONLY limits J1
        if j0.result == Judgment0Result.LANGUAGE_ONLY:
            if evidence_confidence > 0.5:
                return Judgment1(
                    result=Judgment1Result.UNCERTAIN,
                    reasoning="Language signals suggest a direction, but no real-world actions to confirm",
                    candidate_directions=self._extract_candidate_directions(tweet_content)
                )
            else:
                return Judgment1(
                    result=Judgment1Result.NO,
                    reasoning="Insufficient evidence and no real-world actions"
                )
        
        # J0 = ACTION_PRESENT, can fully evaluate
        if evidence_confidence >= config.CONFIDENCE_THRESHOLD:
            return Judgment1(
                result=Judgment1Result.YES,
                reasoning="Real-world actions present with sufficient evidence"
            )
        elif evidence_confidence >= 0.4:
            return Judgment1(
                result=Judgment1Result.UNCERTAIN,
                reasoning="Actions present but evidence is not conclusive",
                candidate_directions=self._extract_candidate_directions(tweet_content)
            )
        else:
            return Judgment1(
                result=Judgment1Result.NO,
                reasoning="Evidence too weak to form a thesis"
            )
    
    def _extract_candidate_directions(self, tweet_content: str) -> list[str]:
        """Extract possible thematic directions from tweet."""
        # This would be done by LLM in practice
        # Placeholder implementation
        directions = []
        
        if any(w in tweet_content.lower() for w in ["iran", "tehran", "persian"]):
            directions.append("Iran policy direction")
        if any(w in tweet_content.lower() for w in ["tariff", "trade", "china"]):
            directions.append("Trade policy direction")
        if any(w in tweet_content.lower() for w in ["venezuela", "delcy", "maduro"]):
            directions.append("Venezuela policy direction")
        
        return directions if directions else ["Unclear direction"]


# Default instance
judgment_engine = JudgmentEngine()
