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

    async def _generate_final_report(self, input_text, search_results, j0_result, j1_result, state) -> DailyBriefing:
        """Internal helper to generate the final report from aggregated research."""
        j2_result = None
        j3_result = None
        red_team = None
        
        if j1_result and j1_result.result == Judgment1Result.YES:
            context = "\n".join([r['content'][:300] for r in search_results[:10]])
            actions = [a.statement for a in (j0_result.actions_found if j0_result else [])]
            
            j2_data = self.llm.generate_thesis_and_competing(input_text, context, actions)
            
            # Clamp confidence values to fix the 700% (7.0) bug
            j2_data['thesis_confidence'] = max(0.0, min(1.0, float(j2_data.get('thesis_confidence', 0.5))))
            j2_data['competing_confidence'] = max(0.0, min(1.0, float(j2_data.get('competing_confidence', 0.5))))
            
            j2_data.setdefault('thesis_evidence', [])
            j2_data.setdefault('competing_evidence', [])
            j2_data.setdefault('competing_thesis', '')
            j2_data.setdefault('why_main_over_competing', '')
            j2_data.setdefault('strategic_context', 'No strategic context provided.')
            j2_data.setdefault('causal_reasoning', 'No causal reasoning provided.')
            
            j2_result = Judgment2(**j2_data)
            
            red_team = devils_advocate.challenge(
                j2_result.main_thesis, 
                j2_result.thesis_evidence, 
                1
            )
            # Re-clamp after red team adjustment
            j2_result.thesis_confidence = max(0.1, min(0.95, j2_result.thesis_confidence + red_team.confidence_adjustment))
            
            j3_data = self.llm.generate_falsifiable_condition(j2_result.main_thesis, context)
            from datetime import timedelta
            # Extract deadline_days from LLM response, default to 7 days
            deadline_days = int(j3_data.pop('deadline_days', 7))
            j3_result = Judgment3(
                falsifiable_condition=j3_data.get('falsifiable_condition', 'No condition specified'),
                verification_deadline=datetime.utcnow() + timedelta(days=deadline_days),
                what_if_triggered=j3_data.get('what_if_triggered', 'Unknown impact')
            )
            
            self.hypothesis_store.insert(Hypothesis(
                statement=j2_result.main_thesis, 
                falsifiable_condition=j3_result.falsifiable_condition,
                verification_deadline=j3_result.verification_deadline, 
                confidence=j2_result.thesis_confidence
            ))
            
        briefing = DailyBriefing(
            generated_at=datetime.utcnow(),
            analysis_date=datetime.utcnow().strftime("%Y-%m-%d"),
            source_summary="Batch Synthesis",
            source_quote=input_text[:500],
            judgment_0=j0_result.result if j0_result else "UNKNOWN",
            judgment_1=j1_result.result if j1_result else "UNKNOWN",
            judgment_reasoning=j1_result.reasoning if j1_result else "Analysis incomplete",
            strategic_context=j2_result.strategic_context if j2_result else None,
            causal_reasoning=j2_result.causal_reasoning if j2_result else None,
            main_thesis=j2_result.main_thesis if j2_result else None,
            thesis_confidence=j2_result.thesis_confidence if j2_result else 0.0,
            thesis_evidence=j2_result.thesis_evidence if j2_result else [],
            competing_explanation=CompetingExplanation(
                explanation=j2_result.competing_thesis, 
                evidence=j2_result.competing_evidence,
                confidence=j2_result.competing_confidence
            ) if j2_result else None,
            falsifiable_condition=FalsifiableCondition(
                condition=j3_result.falsifiable_condition, 
                deadline=j3_result.verification_deadline,
                what_if_triggered=j3_result.what_if_triggered
            ) if j3_result else None,
            red_team_notes=[RedTeamNote(challenge=c.challenge_text, severity=c.severity) for c in (red_team.challenges if red_team else [])],
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
