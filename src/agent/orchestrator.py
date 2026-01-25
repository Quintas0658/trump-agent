"""Agent Orchestrator - Ties all components together into the analysis pipeline."""

import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Any

from src.config import config
from src.agent.llm_client import get_gemini_client
from src.agent.judgments import judgment_engine, Judgment0, Judgment1, Judgment2, Judgment3, Judgment1Result
from src.agent.stop_rules import stop_rule_engine, AgentState, StopReason, StopType
from src.agent.devils_advocate import devils_advocate, RedTeamResult
from src.input.entity_extractor import LLMEntityExtractor
from src.tools.search import SearchTool
from src.memory.event_store import EventStore
from src.memory.entity_store import EntityStore
from src.memory.hypothesis_store import HypothesisStore
from src.memory.claim_store import ClaimStore
from src.memory.schema import (
    Event, ActionType, SourceReference, Hypothesis, 
    HypothesisStatus, Claim, ClaimStatus
)
from src.output.report_generator import (
    report_generator, DailyBriefing, CompetingExplanation, 
    FalsifiableCondition, RedTeamNote
)

class AgentOrchestrator:
    """Orchestrates the analysis pipeline for a single input or a batch of pulses."""
    
    def __init__(self):
        self.llm = get_gemini_client()
        self.search_tool = SearchTool()
        self.entity_extractor = LLMEntityExtractor(self.llm)
        self.event_store = EventStore()
        self.entity_store = EntityStore()
        self.hypothesis_store = HypothesisStore()
        self.claim_store = ClaimStore(self.event_store.client)

    async def _get_comprehensive_context(self) -> str:
        """Retrieves recent events (including RAW sweep results) and pending hypotheses."""
        print("[Memory] Retrieving comprehensive historical context...")
        recent_events = self.event_store.get_recent(limit=15)
        pending_hypotheses = self.hypothesis_store.get_pending()
        
        context_parts = []
        if recent_events:
            context_parts.append("RECENT EVENTS & BACKGROUND:")
            for e in recent_events:
                status_str = f"[{e.status.value}]" if hasattr(e, 'status') else ""
                context_parts.append(f"- {status_str} {e.statement} ({e.occurred_at.date() if e.occurred_at else 'unknown'})")
            
        if pending_hypotheses:
            context_parts.append("\nACTIVE HYPOTHESES:")
            context_parts.extend([f"- {h.statement} (Confidence: {h.confidence}, Falsifiable if: {h.falsifiable_condition})" for h in pending_hypotheses])
            
        return "\n".join(context_parts)

    def _consolidate_memory(self, new_events: List[Event]):
        """Cross-references new events against pending hypotheses to update world model."""
        if not new_events:
            return
            
        print(f"[Memory] Consolidating memory with {len(new_events)} new events...")
        pending_hypotheses = self.hypothesis_store.get_pending()
        
        for event in new_events:
            for hypothesis in pending_hypotheses:
                event_words = set(event.statement.lower().split())
                hyp_words = set(hypothesis.statement.lower().split())
                overlap = event_words.intersection(hyp_words)
                
                if len(overlap) > 3:
                    print(f"[*] Found link: Event -> Hypothesis \"{hypothesis.statement[:30]}...\"")
                    self.hypothesis_store.update_status(
                        hypothesis.id, 
                        HypothesisStatus.STRENGTHENED,
                        support_delta=1
                    )

    async def analyze_batch(self, claims: List[Claim]) -> DailyBriefing:
        """Analyze a batch of claims as a single strategic unit (The SitRep Phase)."""
        if not claims:
            return None
            
        print(f"[*] Starting BATCH analysis for {len(claims)} pulses...")
        
        # 1. Synthesize Claims Intent
        combined_claims = "\n---\n".join([f"FROM @{c.attributed_to}: {c.claim_text}" for c in claims])
        
        # 2. Context Retrieval (Step 0)
        memory_context = await self._get_comprehensive_context()
        
        # 3. Grounded Extraction (Step 1)
        print("[1] Extracting unified entities and strategic queries...")
        extraction = self.entity_extractor.extract(f"CONTEXT:\n{memory_context}\n\nBATCH_PULSES:\n{combined_claims}")
        
        # 4. Research Loop (Batch-Level)
        state = AgentState()
        all_search_results = []
        j0_result = None
        j1_result = None
        
        while state.loop_count < config.MAX_SEARCH_LOOPS:
            state.loop_count += 1
            print(f"[Loop {state.loop_count}] Executing parallel search for batch...")
            
            if state.loop_count == 1:
                current_queries = extraction.suggested_queries[:config.MAX_PARALLEL_QUERIES]
            else:
                current_queries = self.search_tool.generate_queries(combined_claims, [e.name for e in extraction.entities])
            
            search_responses = await self.search_tool.parallel_search(current_queries)
            loop_results = []
            for resp in search_responses:
                for res in resp.results:
                    loop_results.append({
                        "title": res.title, "url": res.url,
                        "content": res.content, "score": res.score
                    })
            all_search_results.extend(loop_results)
            state.search_result_count = len(all_search_results)
            
            # Grounding check
            j0_result = judgment_engine.judgment_0(datetime.utcnow(), loop_results)
            evidence_confidence = min(0.4 + (state.search_result_count * 0.05), 0.9)
            j1_result = judgment_engine.judgment_1(j0_result, combined_claims, loop_results, evidence_confidence)
            
            stop_signal = stop_rule_engine.check(state)
            if j1_result.result == Judgment1Result.YES or stop_signal:
                if stop_signal:
                    state.stop_reason = stop_signal.reason
                break
        
        # Save search results as events (marked as VERIFIED)
        if j0_result and j0_result.actions_found:
            for action in j0_result.actions_found:
                from src.memory.schema import EventStatus
                action.status = EventStatus.VERIFIED
                self.event_store.insert(action)
            self._consolidate_memory(j0_result.actions_found)

        # 5. Final Synthesis
        print("[6] Generating Situation Report (Batch SitRep)...")
        briefing = await self._generate_final_report(combined_claims, all_search_results, j0_result, j1_result, state)
        return briefing

    def _parse_confidence(self, val: Any) -> float:
        """Robustly parse confidence value from LLM (handles 0.9, '0.9', 'High', etc.)."""
        if isinstance(val, (int, float)):
            return max(0.0, min(1.0, float(val)))
        
        if isinstance(val, str):
            val_clean = val.strip().lower()
            # Handle semantic strings
            if "high" in val_clean: return 0.9
            if "medium" in val_clean: return 0.5
            if "low" in val_clean: return 0.2
            
            # Try parsing as float
            try:
                # Handle cases like "0.9 (Strong evidence)"
                numeric_part = "".join(c for c in val if c.isdigit() or c == ".")
                if numeric_part:
                    return max(0.0, min(1.0, float(numeric_part)))
            except ValueError:
                pass
        
        return 0.5 # Default fallback

    async def _generate_final_report(self, input_text, search_results, j0_result, j1_result, state) -> DailyBriefing:
        """Internal helper to generate the final report from aggregated research."""
        j2_result = None
        j3_result = None
        red_team = None
        
        if j1_result and j1_result.result == Judgment1Result.YES:
            context = "\n".join([r['content'][:300] for r in search_results[:10]])
            actions = [a.statement for a in (j0_result.actions_found if j0_result else [])]
            
            # 1. Generate Intelligence Pillars
            pillar_results = self.llm.generate_thesis_and_competing(input_text, context, actions)
            raw_pillars = pillar_results.get('pillars', [])
            
            processed_pillars = []
            for raw_p in raw_pillars:
                # Robustly parse confidence
                conf = self._parse_confidence(raw_p.get('confidence', 0.5))
                
                pillar = IntelligencePillar(
                    title=raw_p.get('title', 'Unknown Pillar'),
                    summary=raw_p.get('summary', 'No summary provided.'),
                    strategic_context=raw_p.get('strategic_context', 'No context provided.'),
                    causal_reasoning=raw_p.get('causal_reasoning', 'No reasoning provided.'),
                    confidence=conf,
                    evidence=raw_p.get('evidence', []),
                    competing_explanation=raw_p.get('competing_explanation'),
                    falsifiable_condition=raw_p.get('falsifiable_condition')
                )
                
                # Devil's Advocate for each pillar (Optional: Could do per-pillar or overall)
                # For now, let's keep it simple and just add the pillar
                processed_pillars.append(pillar)
                
                # Save to Hypothesis Store
                self.hypothesis_store.insert(Hypothesis(
                    statement=pillar.title + ": " + pillar.summary,
                    falsifiable_condition=pillar.falsifiable_condition or "None",
                    verification_deadline=datetime.utcnow() + timedelta(days=7),
                    confidence=pillar.confidence
                ))

            # 2. Generate Final Narrative based on all pillars
            pillars_data_str = "\n\n".join([
                f"Pillar: {p.title}\nContext: {p.strategic_context}\nReasoning: {p.causal_reasoning}" 
                for p in processed_pillars
            ])
            
            narrative_prompt = prompts.NARRATIVE_PROMPT.format(
                pillars_data=pillars_data_str,
                challenges="None" # Red team logic to be updated later
            )
            narrative_resp = self.llm.generate(narrative_prompt)
            briefing_text = narrative_resp.content
            
        briefing = DailyBriefing(
            generated_at=datetime.utcnow(),
            analysis_date=datetime.utcnow().strftime("%Y-%m-%d"),
            source_summary="Multi-Pillar Strategic Synthesis",
            source_quote=input_text[:500],
            judgment_0=j0_result.result if j0_result else "UNKNOWN",
            judgment_1=j1_result.result if j1_result else "UNKNOWN",
            judgment_reasoning=briefing_text if j1_result and j1_result.result == Judgment1Result.YES else (j1_result.reasoning if j1_result else "Analysis incomplete"),
            pillars=processed_pillars if j1_result and j1_result.result == Judgment1Result.YES else [],
            search_count=state.search_result_count, 
            loop_count=state.loop_count, 
            stop_reason=state.stop_reason
        )
        if not j2_result:
            briefing.give_up_message = j1_result.reasoning if j1_result else "Failed to gather evidence."
            briefing.partial_evidence = [r['title'] for r in search_results[:5]]
            
        return briefing

    async def analyze_tweet(self, tweet_text: str, tweet_time: Optional[datetime] = None) -> DailyBriefing:
        """Backward compatibility wrapper for single tweet."""
        claim = Claim(claim_text=tweet_text, attributed_to="realDonaldTrump", claimed_at=tweet_time)
        return await self.analyze_batch([claim])

# Singleton
orchestrator = AgentOrchestrator()
