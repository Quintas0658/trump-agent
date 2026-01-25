"""Devil's Advocate - Red team challenge before final output."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class RedTeamChallenge:
    """A challenge raised by the Devil's Advocate."""
    challenge_text: str
    severity: str  # "low", "medium", "high"
    suggested_search: Optional[str] = None


@dataclass
class RedTeamResult:
    """Result of Devil's Advocate analysis."""
    challenges: list[RedTeamChallenge]
    alternative_explanations: list[str]
    has_strong_challenge: bool
    confidence_adjustment: float  # Negative value to reduce confidence


class DevilsAdvocate:
    """Generates red team challenges for a proposed thesis.
    
    Forces the agent to consider alternative explanations
    and potential flaws in reasoning before final output.
    """
    
    def __init__(self, llm_client=None):
        self.llm = llm_client
    
    def challenge(
        self,
        main_thesis: str,
        evidence: list[str],
        reasoning_depth: int
    ) -> RedTeamResult:
        """Generate challenges to the proposed thesis.
        
        Args:
            main_thesis: The proposed conclusion
            evidence: List of evidence points
            reasoning_depth: Current depth (1, 2, or 3+)
            
        Returns:
            RedTeamResult with challenges and alternatives
        """
        challenges = []
        alternatives = []
        
        # Challenge 1: Check for third-order reasoning
        if reasoning_depth >= 3:
            challenges.append(RedTeamChallenge(
                challenge_text="Analysis includes third-order reasoning (predicting what others predict). This is unverifiable.",
                severity="high",
                suggested_search=None
            ))
        
        # Challenge 2: Check for single-source issues
        if len(evidence) == 1:
            challenges.append(RedTeamChallenge(
                challenge_text="Thesis relies on a single evidence source. Multi-source confirmation missing.",
                severity="medium",
                suggested_search="alternative news sources for verification"
            ))
        
        # Challenge 3: Check for motive attribution
        motive_words = ["wants", "intends", "hoping", "trying to", "believes"]
        if any(word in main_thesis.lower() for word in motive_words):
            challenges.append(RedTeamChallenge(
                challenge_text="Thesis attributes internal motives. Consider: What if this is purely tactical messaging?",
                severity="medium",
                suggested_search=None
            ))
            alternatives.append("This may be strategic messaging without the attributed intent")
        
        # Challenge 4: Alternative interpretation
        alternatives.append("The events may be coincidental rather than coordinated")
        alternatives.append("This may be a trial balloon rather than committed policy direction")
        
        # Determine if there's a strong challenge
        has_strong = any(c.severity == "high" for c in challenges)
        
        # Calculate confidence adjustment
        if has_strong:
            adjustment = -0.2
        elif len([c for c in challenges if c.severity == "medium"]) >= 2:
            adjustment = -0.1
        else:
            adjustment = -0.05  # Always slightly reduce confidence
        
        return RedTeamResult(
            challenges=challenges,
            alternative_explanations=alternatives[:2],  # Max 2 alternatives
            has_strong_challenge=has_strong,
            confidence_adjustment=adjustment
        )
    
    def generate_prompt(self, main_thesis: str, evidence: list[str]) -> str:
        """Generate prompt for LLM-based challenge (when LLM is available)."""
        return f"""You are a Red Team analyst. Your job is to challenge the following thesis.

THESIS: {main_thesis}

SUPPORTING EVIDENCE:
{chr(10).join(f"- {e}" for e in evidence)}

YOUR TASK:
1. What evidence might contradict this thesis?
2. What alternative explanations exist?
3. What would make this thesis wrong?
4. Is there any third-order reasoning (predicting what others predict)?

Be specific. Do not agree with the thesis. Your job is to challenge.
Output format:
CHALLENGES:
- [challenge 1]
- [challenge 2]

ALTERNATIVES:
- [alternative explanation 1]
- [alternative explanation 2]

SUGGESTED SEARCH (if needed):
- [search query to verify/refute]
"""


# Default instance
devils_advocate = DevilsAdvocate()
