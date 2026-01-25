"""Prompt templates for the agent."""

# Entity extraction prompt
ENTITY_EXTRACTION = """Extract key entities from this text.

TEXT: "{text}"

Return a JSON object with:
- entities: list of {{name, type}} where type is person/country/org/topic
- keywords: important keywords
- queries: 3-5 search queries for context

OUTPUT:"""


# Judgment 0: Action detection
JUDGMENT_0_PROMPT = """You are analyzing a political statement for REAL-WORLD ACTIONS.

STATEMENT: "{tweet}"

BACKGROUND FROM SEARCH:
{search_context}

RECENT EVENTS FROM MEMORY:
{memory_context}

TASK: Is there a REAL-WORLD ACTION (not just words)?

REAL-WORLD ACTIONS (ground the analysis):
- Military deployments, strikes, operations
- Executive orders SIGNED and ENACTED (not announced)
- Personnel appointments/firings that happened
- Arrests, sanctions with evidence they occurred
- Physical movements of military assets

NOT ACTIONS (language only):
- Threats, promises, "considering", "might"
- Plans announced but not executed
- Social media rhetoric
- Negotiations without outcomes

OUTPUT (JSON):
{{
    "judgment_0": "ACTION_PRESENT" or "LANGUAGE_ONLY",
    "actions_found": ["list of verified actions"] or [],
    "evidence_sources": ["source 1", "source 2"],
    "reasoning": "explanation"
}}"""


# Judgment 1: Clear thesis check
JUDGMENT_1_PROMPT = """Based on Judgment 0 result and evidence, determine if there's a clear thesis.

JUDGMENT 0 RESULT: {j0_result}
ACTIONS FOUND: {actions}

STATEMENT: "{tweet}"
CONTEXT: {context}

RULES:
- If J0 = LANGUAGE_ONLY: Maximum allowed is UNCERTAIN (never YES)
- If J0 = ACTION_PRESENT: Can be YES/NO/UNCERTAIN based on evidence

OUTPUT (JSON):
{{
    "judgment_1": "YES" or "NO" or "UNCERTAIN",
    "reasoning": "explanation",
    "candidate_directions": ["direction 1"] if UNCERTAIN else []
}}"""


# Judgment 2: Multi-Pillar Strategic Analysis
JUDGMENT_2_PROMPT = """You are a Senior Strategic Analyst. Your task is to identify ALL distinct strategic themes (Intelligence Pillars) present in these signals.

STATEMENT BATCH: "{tweet}"
ACTIONS RECORDED: {actions}
SEARCH CONTEXT: {context}

YOUR GOAL: Segment these pulses into as many distinct "Intelligence Pillars" as you can identify. Do NOT limit yourself to a fixed number. For each pillar, explain the "Who", the "Why", and the "So What" for someone unfamiliar with US politics.

PRYING QUESTIONS FOR EACH PILLAR:
- WHO: Who are the key players and what is their historical role?
- WHY: Why is this happening now? What are the political stakes?
- SO WHAT: What is the intended strategic outcome?

OUTPUT (JSON object with a list of pillars):
{{
    "pillars": [
        {{
            "title": "Short descriptive title (e.g., 'The China-Canada Trade Warning')",
            "summary": "1-2 sentence high-level summary",
            "strategic_context": "Deep background on players and history for this specific pillar...",
            "causal_reasoning": "Analysis of why this is happening and the strategic intent...",
            "confidence": 0.X (0.0-1.0),
            "evidence": ["evidence 1", "evidence 2"],
            "competing_explanation": "A plausible alternative interpretation...",
            "falsifiable_condition": "One specific verifiable outcome to watch"
        }}
    ]
}}"""


# Judgment 3: Falsifiable condition
JUDGMENT_3_PROMPT = """Create a FALSIFIABLE CONDITION for this thesis.

THESIS: "{thesis}"
CONTEXT: {context}

RULES:
1. Must be objectively verifiable
2. Must have a time window (1-14 days)
3. Must specify what happens if triggered

OUTPUT (JSON):
{{
    "falsifiable_condition": "specific observable outcome",
    "deadline_days": N,
    "what_if_triggered": "what this means"
}}"""


# Devil's Advocate / Red Team
RED_TEAM_PROMPT = """You are a RED TEAM analyst. ATTACK this thesis.

THESIS: "{thesis}"

EVIDENCE USED:
{evidence}

YOUR MISSION:
1. Find holes in the reasoning
2. Propose alternative explanations
3. Identify what evidence would DISPROVE this
4. Check for 3rd-order reasoning (predicting what others predict)

DO NOT AGREE. BE SKEPTICAL.

OUTPUT (JSON):
{{
    "challenges": [
        {{"text": "problem with the thesis", "severity": "high/medium/low"}}
    ],
    "alternative_explanations": ["alt 1", "alt 2"],
    "missing_evidence": ["what we don't know"],
    "suggested_searches": ["queries to verify/refute"],
    "overall_severity": "high/medium/low",
    "confidence_adjustment": -0.X (negative number)
}}"""


# Multi-Pillar Narrative generation
NARRATIVE_PROMPT = """You are a Senior Strategic Advisor providing an intelligence briefing.

TASK: Take the identified "Intelligence Pillars" and write a cohesive, sophisticated briefing.

{pillars_data}

STRUCTURE:
1. **Executive Summary**: 1 paragraph summarizing the overall strategic posture across all pillars.
2. **Strategic Deep Dives**: For each pillar, use the provided context and reasoning to tell a story. Explain the "inner workings". Use headers.
3. **Synthesis**: Are there connections between these pillars? (e.g., is Trade being used as leverage for Border?)
4. **Risk Assessment**: What is the #1 thing to watch in the next 7 days?

TONE: Professional, authoritative, and explanatory. Break down complex jargon.

OUTPUT:"""


# Give Up message
GIVE_UP_PROMPT = """Generate a "low confidence" report when analysis cannot reach conclusions.

STATEMENT: "{tweet}"
SEARCH COUNT: {search_count}
EVIDENCE FOUND: {evidence}

EXPLAIN:
1. What we tried to find
2. Why confidence is low
3. What additional information would help

OUTPUT (2-3 paragraphs):"""
