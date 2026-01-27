"""Gatekeeper Module - Critique and Refine Strategic Reports.

Implements the 4-Step Depth Reinforcement Loop:
1. Draft -> 2. Critique -> 3. Deep Dive -> 4. Refine

This module provides:
- Gatekeeper: Identifies weak points in draft reports
- Editor: Synthesizes new evidence into the final report
"""

import json
from dataclasses import dataclass
from typing import List, Optional

from src.agent.llm_client import get_gemini_client, LLMResponse
from src.agent import prompts


@dataclass
class Critique:
    """Result of the Gatekeeper's critique."""
    pillar_title: str
    weakness: str
    deep_dive_questions: List[str]
    severity: str  # "minor", "moderate", "critical"


@dataclass
class GatekeeperResult:
    """Output of the Gatekeeper phase."""
    overall_assessment: str
    critiques: List[Critique]
    needs_refinement: bool


class Gatekeeper:
    """The Gatekeeper Agent - A ruthless critic of draft reports.
    
    This agent reads a draft strategic memo and identifies:
    1. Weak pillars that lack specific evidence
    2. Vague generalizations that need concrete examples
    3. Missing important angles (like international dimensions)
    """
    
    def __init__(self, client=None):
        self.client = client or get_gemini_client()
    
    def critique_draft(self, draft_report: str, original_context: str = "") -> GatekeeperResult:
        """Critique a draft report and identify areas for deep dives."""
        prompt = prompts.GATEKEEPER_PROMPT.format(
            draft_report=draft_report,
            original_context=original_context[:5000] if original_context else "Not provided"
        )
        
        try:
            # Enable thinking mode for critique
            response = self.client.generate(prompt, temperature=0.3, thinking_budget=2048)
            
            # Print thoughts for visibility
            if response.thoughts:
                print("\n" + "-"*30)
                print("[Gatekeeper Intelligence - CRITIQUE LOGIC]")
                print("-"*30)
                print(response.thoughts)
                print("-"*30 + "\n")
                
            content = response.content.strip()
            
            # Parse JSON response
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            data = json.loads(content)
            
            critiques = []
            for c in data.get("critiques", []):
                critiques.append(Critique(
                    pillar_title=c.get("pillar_title", "Unknown"),
                    weakness=c.get("weakness", ""),
                    deep_dive_questions=c.get("deep_dive_questions", []),
                    severity=c.get("severity", "moderate")
                ))
            
            return GatekeeperResult(
                overall_assessment=data.get("overall_assessment", "No assessment"),
                critiques=critiques,
                needs_refinement=len(critiques) > 0
            )
            
        except Exception as e:
            print(f"[Gatekeeper] Critique failed: {e}")
            return GatekeeperResult(
                overall_assessment="Critique failed due to error",
                critiques=[],
                needs_refinement=False
            )
    
    def get_deep_dive_queries(self, result: GatekeeperResult) -> List[str]:
        """Extract all deep-dive questions from a GatekeeperResult.
        
        Returns:
            Flat list of all search queries to execute
        """
        queries = []
        for critique in result.critiques:
            queries.extend(critique.deep_dive_questions)
        return queries


class Editor:
    """The Editor Agent - Synthesizes new evidence into the final report.
    
    Takes the original draft and the new deep-dive findings,
    and produces a refined, evidence-enriched final report.
    """
    
    def __init__(self, client=None):
        self.client = client or get_gemini_client()
    
    def refine_report(
        self, 
        draft_report: str, 
        critiques: List[Critique],
        new_evidence: str
    ) -> str:
        """Refine the draft report with new evidence.
        
        Args:
            draft_report: The original draft memo
            critiques: What was criticized (to focus refinement)
            new_evidence: The deep-dive search results
            
        Returns:
            The refined final report (full text)
        """
        # Format critiques for the prompt
        critique_summary = "\n".join([
            f"- **{c.pillar_title}**: {c.weakness}"
            for c in critiques
        ])
        
        prompt = prompts.EDITOR_PROMPT.format(
            draft_report=draft_report,
            critique_summary=critique_summary,
            new_evidence=new_evidence[:8000]  # Limit to avoid token overflow
        )
        
        try:
            # Enable thinking mode for refinement
            response = self.client.generate(
                prompt, 
                temperature=0.4,
                max_tokens=8192,
                thinking_budget=4096
            )
            
            # Print thoughts for visibility
            if response.thoughts:
                print("\n" + "-"*30)
                print("[Editor Intelligence - REFINEMENT LOGIC]")
                print("-"*30)
                print(response.thoughts)
                print("-"*30 + "\n")
                
            return response.content.strip()
            
        except Exception as e:
            print(f"[Editor] Refinement failed: {e}")
            return draft_report  # Return original if refinement fails


# Convenience function for the main loop
def run_gatekeeper_loop(
    draft_report: str,
    original_context: str,
    search_function,  # Callable that takes List[str] queries and returns str results
    client=None
) -> str:
    """Run the full Gatekeeper reinforcement loop.
    
    Args:
        draft_report: Initial strategic memo
        original_context: The search context used in draft generation
        search_function: Function to execute deep-dive searches
        client: Optional GeminiClient instance
        
    Returns:
        Final refined report (or original if no refinement needed)
    """
    gatekeeper = Gatekeeper(client)
    editor = Editor(client)
    
    print("\n" + "="*60)
    print("PHASE 4: GATEKEEPER CRITIQUE")
    print("="*60)
    
    # Step 1: Critique the draft
    result = gatekeeper.critique_draft(draft_report, original_context)
    
    print(f"[Gatekeeper] Assessment: {result.overall_assessment}")
    print(f"[Gatekeeper] Found {len(result.critiques)} weak points")
    
    if not result.needs_refinement:
        print("[Gatekeeper] Draft is solid. No refinement needed.")
        return draft_report
    
    # Log critiques
    for c in result.critiques:
        print(f"  - [{c.severity.upper()}] {c.pillar_title}: {c.weakness[:80]}...")
    
    # Step 2: Execute deep dives
    queries = gatekeeper.get_deep_dive_queries(result)
    print(f"\n[Deep Scout] Executing {len(queries)} targeted searches...")
    
    new_evidence = search_function(queries)
    print(f"[Deep Scout] Retrieved {len(new_evidence)} chars of new intel.")
    
    # Step 3: Refine the report
    print("\n[Editor] Synthesizing final report...")
    final_report = editor.refine_report(draft_report, result.critiques, new_evidence)
    
    print("[Editor] Final report ready.")
    return final_report
