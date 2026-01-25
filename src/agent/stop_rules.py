"""STOP RULE system - Prevents over-research and controls agent behavior."""

from dataclasses import dataclass
from datetime import datetime, time
from enum import Enum
from typing import Optional


class StopType(str, Enum):
    """Type of stop signal."""
    HARD = "hard"   # Must stop immediately
    SOFT = "soft"   # Warning, can be overridden


class StopReason(str, Enum):
    """Reasons for stopping."""
    # Hard stops (P0-P3)
    TIME_LOCK = "TIME_LOCK"                # P0: Outside analysis window
    J0_COMPLETE = "J0_COMPLETE"            # P1: Judgment 0 concluded
    J1_COMPLETE = "J1_COMPLETE"            # P2: Judgment 1 concluded
    DEPTH_EXCEEDED = "DEPTH_EXCEEDED"      # P3: Reasoning depth > 2
    LOOP_EXHAUSTED = "LOOP_EXHAUSTED"      # P3: Max search loops reached
    
    # Soft stops (P4-P8)
    COMPETING_EXISTS = "COMPETING_EXISTS"  # P4: Has 1 competing explanation
    FALSIFIABLE_SET = "FALSIFIABLE_SET"    # P5: Has 1 falsifiable condition
    SEARCH_SUFFICIENT = "SEARCH_SUFFICIENT"  # P6: >= 3 relevant results
    INFO_REPEATING = "INFO_REPEATING"      # P7: > 70% repeat rate
    WINDOW_COVERED = "WINDOW_COVERED"      # P8: 24h window fully processed


@dataclass
class StopSignal:
    """A stop signal with its metadata."""
    reason: StopReason
    type: StopType
    priority: int  # Lower = higher priority
    message: str


@dataclass
class AgentState:
    """Current state of the agent for STOP RULE evaluation."""
    loop_count: int = 0
    search_count: int = 0
    reasoning_depth: int = 0
    judgment_0_complete: bool = False
    judgment_1_complete: bool = False
    has_competing_explanation: bool = False
    has_falsifiable_condition: bool = False
    search_result_count: int = 0
    info_repeat_rate: float = 0.0
    stop_reason: Optional[StopReason] = None
    
    
# STOP RULE priority mapping
STOP_PRIORITIES = {
    StopReason.TIME_LOCK: 0,
    StopReason.J0_COMPLETE: 1,
    StopReason.J1_COMPLETE: 2,
    StopReason.DEPTH_EXCEEDED: 3,
    StopReason.LOOP_EXHAUSTED: 3,
    StopReason.COMPETING_EXISTS: 4,
    StopReason.FALSIFIABLE_SET: 5,
    StopReason.SEARCH_SUFFICIENT: 6,
    StopReason.INFO_REPEATING: 7,
    StopReason.WINDOW_COVERED: 8,
}


class StopRuleEngine:
    """Evaluates STOP RULEs and returns the highest priority triggered signal."""
    
    def __init__(
        self, 
        max_loops: int = 3,
        max_reasoning_depth: int = 2,
        analysis_start_hour: int = 12,  # UTC
        analysis_end_hour: int = 14,    # UTC
    ):
        self.max_loops = max_loops
        self.max_reasoning_depth = max_reasoning_depth
        self.analysis_start = time(analysis_start_hour, 0)
        self.analysis_end = time(analysis_end_hour, 0)
    
    def check(self, state: AgentState) -> Optional[StopSignal]:
        """Check all STOP RULEs and return highest priority triggered signal.
        
        Returns None if no stop condition is triggered.
        """
        signals = []
        
        # Check hard stops first
        signals.extend(self._check_hard_stops(state))
        
        # Check soft stops
        signals.extend(self._check_soft_stops(state))
        
        if not signals:
            return None
        
        # Return highest priority (lowest number)
        signals.sort(key=lambda s: s.priority)
        return signals[0]
    
    def _check_hard_stops(self, state: AgentState) -> list[StopSignal]:
        """Check hard stop conditions."""
        signals = []
        
        # P0: Time lock (disabled for MVP - can run anytime)
        # if not self._in_analysis_window():
        #     signals.append(StopSignal(
        #         reason=StopReason.TIME_LOCK,
        #         type=StopType.HARD,
        #         priority=STOP_PRIORITIES[StopReason.TIME_LOCK],
        #         message="Outside analysis window (UTC 12:00-14:00)"
        #     ))
        
        # P3: Loop exhausted
        if state.loop_count >= self.max_loops:
            signals.append(StopSignal(
                reason=StopReason.LOOP_EXHAUSTED,
                type=StopType.HARD,
                priority=STOP_PRIORITIES[StopReason.LOOP_EXHAUSTED],
                message=f"Search loop limit reached ({self.max_loops})"
            ))
        
        # P3: Reasoning depth exceeded
        if state.reasoning_depth > self.max_reasoning_depth:
            signals.append(StopSignal(
                reason=StopReason.DEPTH_EXCEEDED,
                type=StopType.HARD,
                priority=STOP_PRIORITIES[StopReason.DEPTH_EXCEEDED],
                message=f"Reasoning depth exceeded ({state.reasoning_depth} > {self.max_reasoning_depth})"
            ))
        
        return signals
    
    def _check_soft_stops(self, state: AgentState) -> list[StopSignal]:
        """Check soft stop conditions."""
        signals = []
        
        # P4: Has competing explanation
        if state.has_competing_explanation:
            signals.append(StopSignal(
                reason=StopReason.COMPETING_EXISTS,
                type=StopType.SOFT,
                priority=STOP_PRIORITIES[StopReason.COMPETING_EXISTS],
                message="Competing explanation already generated"
            ))
        
        # P5: Has falsifiable condition
        if state.has_falsifiable_condition:
            signals.append(StopSignal(
                reason=StopReason.FALSIFIABLE_SET,
                type=StopType.SOFT,
                priority=STOP_PRIORITIES[StopReason.FALSIFIABLE_SET],
                message="Falsifiable condition already set"
            ))
        
        # P6: Sufficient search results
        if state.search_result_count >= 3:
            signals.append(StopSignal(
                reason=StopReason.SEARCH_SUFFICIENT,
                type=StopType.SOFT,
                priority=STOP_PRIORITIES[StopReason.SEARCH_SUFFICIENT],
                message=f"Sufficient search results ({state.search_result_count} >= 3)"
            ))
        
        # P7: Information repeating
        if state.info_repeat_rate > 0.7:
            signals.append(StopSignal(
                reason=StopReason.INFO_REPEATING,
                type=StopType.SOFT,
                priority=STOP_PRIORITIES[StopReason.INFO_REPEATING],
                message=f"Information repeating ({state.info_repeat_rate:.0%} > 70%)"
            ))
        
        return signals
    
    def _in_analysis_window(self) -> bool:
        """Check if current time is within analysis window."""
        now = datetime.utcnow().time()
        return self.analysis_start <= now <= self.analysis_end
    
    def should_give_up(self, state: AgentState, confidence: float) -> bool:
        """Determine if agent should enter GIVE_UP state.
        
        GIVE_UP when:
        - Loop limit reached AND
        - Confidence is still low (< threshold)
        """
        from src.config import config
        
        return (
            state.loop_count >= self.max_loops and 
            confidence < config.CONFIDENCE_THRESHOLD
        )


# Singleton instance
stop_rule_engine = StopRuleEngine(
    max_loops=3,
    max_reasoning_depth=2,
)
