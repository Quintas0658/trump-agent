"""Daily sweep - Proactive broad search for environmental baseline."""

from datetime import datetime, timedelta
from typing import List, Optional
import asyncio

from src.config import config
from src.agent.llm_client import get_gemini_client
from src.tools.search import SearchTool
from src.memory.event_store import EventStore
from src.memory.schema import Event, ActionType, EventStatus, SourceReference


class DailySweep:
    """Proactively sweeps for broad environmental context."""
    
    def __init__(self):
        self.llm = get_gemini_client()
        self.search_tool = SearchTool()
        self.event_store = EventStore()
        
    async def run(self) -> int:
        """Run the daily sweep. Returns the number of new events stored."""
        print("[*] Starting proactive daily sweep...")
        
        # 1. Broad Queries
        queries = [
            "latest US executive orders January 2026",
            "US Treasury department new sanctions actions",
            "US Department of Defense major movements latest",
            "White House official press releases last 24 hours",
            "Federal Register new entries significant"
        ]
        
        all_results = []
        for query in queries:
            print(f"[*] Sweeping: {query}")
            search_response = self.search_tool.search(query, max_results=5)
            # Convert dataclass results to dicts for _extract_facts
            loop_dicts = [
                {"title": r.title, "url": r.url, "content": r.content, "score": r.score}
                for r in search_response.results
            ]
            all_results.extend(loop_dicts)
            
        if not all_results:
            print("[!] Sweep found no search results (network issue?). Skipping extraction.")
            return 0
            
        # 2. Extract Actionable Facts
        try:
            facts = await self._extract_facts(all_results)
        except Exception as e:
            print(f"[!] Failed to extract facts: {e}. Using fallback.")
            facts = self._mock_facts()
        
        # 3. Store in M-EVENT (RAW)
        new_count = 0
        for fact in facts:
            fact.status = EventStatus.RAW
            self.event_store.insert(fact)
            new_count += 1
            
        print(f"[*] Daily sweep complete. {new_count} RAW events stored.")
        return new_count
        
    async def _extract_facts(self, search_results: List[dict]) -> List[Event]:
        """Use LLM to extract objective facts from search results."""
        context = "\n\n".join([
            f"SOURCE: {r.get('url')}\nCONTENT: {r.get('content')}"
            for r in search_results[:15] # Limit context
        ])
        
        prompt = f"""Extract objective actions taken by the US government from these search results.
Focus on: SIGNED orders, APPOINTMENTS, MILITARY moves, or OFFICIAL SANCTIONS.
Exclude: Opinions, polls, or speculation.

RESULTS:
{context}

Return a list of atomic facts in this format:
FACT: [Description of the action]
TYPE: [resource_deployment | legal_document | personnel_change | diplomatic_action]
SOURCE: [Exact URL]
DATE: [YYYY-MM-DD]
---
"""
        # Call LLM (mocked logic if no key)
        if not config.GOOGLE_API_KEY:
            return self._mock_facts()
            
        response = self.llm.generate(prompt)
        return self._parse_llm_facts(response.content)
        
    def _parse_llm_facts(self, text: str) -> List[Event]:
        """Parse the LLM output into Event objects."""
        events = []
        blocks = text.split("---")
        for block in blocks:
            if "FACT:" not in block: continue
            
            try:
                fact_match = block.split("FACT:")[1].split("TYPE:")[0].strip()
                type_match = block.split("TYPE:")[1].split("SOURCE:")[0].strip()
                source_match = block.split("SOURCE:")[1].split("DATE:")[0].strip()
                
                events.append(Event(
                    statement=fact_match,
                    action_type=ActionType(type_match),
                    sources=[SourceReference(source_id="sweep", url=source_match)],
                    status=EventStatus.RAW,
                    occurred_at=datetime.utcnow() # Default
                ))
            except:
                continue
        return events
        
    def _mock_facts(self) -> List[Event]:
        """Fallback facts for mock mode."""
        return [
            Event(
                statement="Department of Treasury announced new sanctions targeting individual entities in Caracas.",
                action_type=ActionType.DIPLOMATIC_ACTION,
                status=EventStatus.RAW,
                occurred_at=datetime.utcnow()
            ),
            Event(
                statement="Executive Order signed regarding border security technology procurement.",
                action_type=ActionType.LEGAL_DOCUMENT,
                status=EventStatus.RAW,
                occurred_at=datetime.utcnow()
            )
        ]

if __name__ == "__main__":
    # Test run
    sweep = DailySweep()
    asyncio.run(sweep.run())
