"""Report generator - Produces daily briefing output."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import json


@dataclass
class CompetingExplanation:
    """A competing explanation for an event."""
    explanation: str
    evidence: list[str]
    confidence: float


@dataclass
class FalsifiableCondition:
    """A condition that would prove the thesis wrong."""
    condition: str
    deadline: datetime
    what_if_triggered: str


@dataclass
class RedTeamNote:
    """A note from the Devil's Advocate."""
    challenge: str
    severity: str  # "low", "medium", "high"


@dataclass
class IntelligencePillar:
    """A distinct strategic theme identified in the batch."""
    title: str
    summary: str
    strategic_context: str
    causal_reasoning: str
    confidence: float
    evidence: list[str]
    competing_explanation: Optional[str] = None
    falsifiable_condition: Optional[str] = None


@dataclass
class DailyBriefing:
    """The final output structure for a multi-pillar briefing."""
    # Metadata
    generated_at: datetime
    analysis_date: str  # YYYY-MM-DD
    
    # Signal source
    source_summary: str
    source_url: Optional[str] = None
    source_quote: Optional[str] = None
    
    judgment_0: str = "UNKNOWN"
    judgment_1: str = "UNKNOWN"
    judgment_reasoning: str = ""
    
    # NEW: Intelligence Pillars (Supports any number of themes)
    pillars: list[IntelligencePillar] = field(default_factory=list)
    
    # Red team notes (overall)
    red_team_notes: list[RedTeamNote] = field(default_factory=list)
    
    # If J1 = NO or gave up
    give_up_message: Optional[str] = None
    partial_evidence: list[str] = field(default_factory=list)
    
    # Processing metadata
    search_count: int = 0
    loop_count: int = 0
    stop_reason: Optional[str] = None


class ReportGenerator:
    """Generates formatted reports from analysis results."""
    
    def __init__(self):
        self.template_markdown = """# Daily Briefing: {date}

**Generated**: {generated_at}
**Analysis Window**: 24 hours ending {date}

---

## Signal Source

{source_summary}

{source_quote_section}

---

## Judgment Summary

| Step | Result | Meaning |
|------|--------|---------|
| **J0**: Real-world action? | {j0} | {j0_meaning} |
| **J1**: Clear thesis today? | {j1} | {j1_meaning} |

---

## 🏛️ Strategic Intelligence Pillars

{pillars_content}

---

## Red Team Review

{red_team_section}

---

## Processing Info

- **Search queries**: {search_count}
- **Reasoning loops**: {loop_count}
- **Stop reason**: {stop_reason}
- **Confidence**: {confidence:.0%}

---

*This briefing is generated automatically. All theses are falsifiable and should be tracked for verification.*
"""
    
    def generate_markdown(self, briefing: DailyBriefing) -> str:
        """Generate a markdown report from a briefing."""
        # Source quote section
        if briefing.source_quote:
            source_quote_section = f'> "{briefing.source_quote}"\n>\n> — Source'
        else:
            source_quote_section = ""
        
        # J0/J1 meanings
        j0_meaning = (
            "Real-world actions detected (military, personnel, legal)"
            if briefing.judgment_0 == "ACTION_PRESENT"
            else "Language signals only, no confirmed actions"
        )
        
        if briefing.judgment_1 == "YES":
            j1_meaning = "Sufficient evidence to form a thesis"
        elif briefing.judgment_1 == "UNCERTAIN":
            j1_meaning = "Possible direction, but not confirmed"
        else:
            j1_meaning = "Insufficient evidence for any thesis"
        
        # Red team section
        if briefing.red_team_notes:
            red_team_section = "\n".join([
                f"- **[{note.severity.upper()}]** {note.challenge}"
                for note in briefing.red_team_notes
            ])
        else:
            red_team_section = "No significant challenges raised."
        
        return self.template_markdown.format(
            date=briefing.analysis_date,
            generated_at=briefing.generated_at.strftime("%Y-%m-%d %H:%M UTC"),
            source_summary=briefing.source_summary,
            source_quote_section=source_quote_section,
            j0=briefing.judgment_0,
            j0_meaning=j0_meaning,
            j1=briefing.judgment_1,
            j1_meaning=j1_meaning,
            pillars_content=self._generate_pillars_section(briefing),
            red_team_section=red_team_section,
            search_count=briefing.search_count,
            loop_count=briefing.loop_count,
            stop_reason=briefing.stop_reason or "Normal completion",
            confidence=0.0 if not briefing.pillars else max(p.confidence for p in briefing.pillars),
        )

    def _generate_pillars_section(self, briefing: DailyBriefing) -> str:
        """Generate the content for all intelligence pillars."""
        if not briefing.pillars:
            if briefing.give_up_message:
                return f"### Analysis Inconclusive\n\n> {briefing.give_up_message}"
            return "No intelligence pillars identified."

        sections = []
        for i, pillar in enumerate(briefing.pillars):
            p_lines = [
                f"### Pillar {i+1}: {pillar.title}",
                "",
                f"> **Summary**: {pillar.summary}",
                f"> (Confidence: {pillar.confidence:.0%})",
                "",
                "#### 📍 Strategic Context",
                pillar.strategic_context,
                "",
                "#### ⛓️ Causal Reasoning",
                pillar.causal_reasoning,
                "",
                "#### 🔍 Key Evidence",
            ]
            for ev in pillar.evidence:
                p_lines.append(f"- {ev}")
            
            if pillar.competing_explanation:
                p_lines.extend([
                    "",
                    "#### ⚖️ Competing Explanation",
                    pillar.competing_explanation
                ])
                
            if pillar.falsifiable_condition:
                p_lines.extend([
                    "",
                    "#### 🎯 Falsifiable Condition",
                    pillar.falsifiable_condition
                ])
            
            sections.append("\n".join(p_lines))
            sections.append("\n---\n")
            
        return "\n".join(sections)
    
    def _generate_thesis_section(self, briefing: DailyBriefing) -> str:
        """Generate the thesis section of the report."""
        lines = ["## Main Thesis", ""]
        lines.append(f"> **{briefing.main_thesis}**")
        lines.append(f"> (Confidence: {briefing.thesis_confidence:.0%})")
        lines.append("")
        
        # Evidence
        lines.append("### Supporting Evidence")
        for evidence in briefing.thesis_evidence:
            lines.append(f"- {evidence}")
        lines.append("")
        
        # Competing explanation
        if briefing.competing_explanation:
            lines.append("### Competing Explanation")
            lines.append(f"> {briefing.competing_explanation.explanation}")
            lines.append(f"> (Confidence: {briefing.competing_explanation.confidence:.0%})")
            lines.append("")
            lines.append("**Evidence for competing view:**")
            for evidence in briefing.competing_explanation.evidence:
                lines.append(f"- {evidence}")
            lines.append("")
            
            if briefing.why_main_over_competing:
                lines.append(f"**Why main thesis wins**: {briefing.why_main_over_competing}")
                lines.append("")
        
        # Falsifiable condition
        if briefing.falsifiable_condition:
            lines.append("### Falsifiable Condition")
            lines.append("")
            lines.append(f"**Condition**: {briefing.falsifiable_condition.condition}")
            lines.append(f"**Deadline**: {briefing.falsifiable_condition.deadline.strftime('%Y-%m-%d')}")
            lines.append(f"**If triggered**: {briefing.falsifiable_condition.what_if_triggered}")
        
        return "\n".join(lines)
    
    def _generate_give_up_section(self, briefing: DailyBriefing) -> str:
        """Generate the give-up section when no confident thesis could be formed."""
        lines = ["## Analysis Inconclusive", ""]
        lines.append(f"> {briefing.give_up_message}")
        lines.append("")
        
        if briefing.partial_evidence:
            lines.append("### Partial Signals Detected")
            for evidence in briefing.partial_evidence:
                lines.append(f"- {evidence}")
        
        return "\n".join(lines)
    
    def generate_json(self, briefing: DailyBriefing) -> str:
        """Generate JSON output for API consumption."""
        output = {
            "metadata": {
                "generated_at": briefing.generated_at.isoformat(),
                "analysis_date": briefing.analysis_date,
            },
            "source": {
                "summary": briefing.source_summary,
                "url": briefing.source_url,
                "quote": briefing.source_quote,
            },
            "judgments": {
                "j0": briefing.judgment_0,
                "j1": briefing.judgment_1,
            },
            "thesis": None,
            "processing": {
                "search_count": briefing.search_count,
                "loop_count": briefing.loop_count,
                "stop_reason": briefing.stop_reason,
            },
        }
        
        if briefing.main_thesis:
            output["thesis"] = {
                "strategic_context": briefing.strategic_context,
                "causal_reasoning": briefing.causal_reasoning,
                "main": {
                    "statement": briefing.main_thesis,
                    "confidence": briefing.thesis_confidence,
                    "evidence": briefing.thesis_evidence,
                },
                "competing": (
                    {
                        "statement": briefing.competing_explanation.explanation,
                        "confidence": briefing.competing_explanation.confidence,
                        "evidence": briefing.competing_explanation.evidence,
                    }
                    if briefing.competing_explanation
                    else None
                ),
                "why_main_wins": briefing.why_main_over_competing,
                "falsifiable": (
                    {
                        "condition": briefing.falsifiable_condition.condition,
                        "deadline": briefing.falsifiable_condition.deadline.isoformat(),
                        "if_triggered": briefing.falsifiable_condition.what_if_triggered,
                    }
                    if briefing.falsifiable_condition
                    else None
                ),
            }
            output["red_team"] = [
                {"challenge": note.challenge, "severity": note.severity}
                for note in briefing.red_team_notes
            ]
        elif briefing.give_up_message:
            output["give_up"] = {
                "message": briefing.give_up_message,
                "partial_evidence": briefing.partial_evidence,
            }
        
        return json.dumps(output, indent=2, ensure_ascii=False)


    def print_briefing(self, briefing: DailyBriefing):
        """Helper to print a briefing to the console."""
        print(self.generate_markdown(briefing))


# Default instance
report_generator = ReportGenerator()
