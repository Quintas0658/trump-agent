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


# Judgment 2: Thesis generation with competing explanation
JUDGMENT_2_PROMPT = """You are a Senior Strategic Analyst. Generate a deep-dive thesis AND a competing explanation.

STATEMENT: "{tweet}"
ACTIONS RECORDED: {actions}
SEARCH CONTEXT: {context}

YOUR GOAL: Break this down for someone who doesn't understand US politics. Explain the "Who", the "Why", and the "So What".

RULES:
1. **Strategic Context**: Explain WHO the key players are and their HISTORICAL background/roles. Don't assume the user knows them.
2. **Causal Reasoning**: Explain WHY this is happening now. What are the political stakes? What is the intended strategic outcome?
3. **Main Thesis**: Most likely interpretation of the strategic shift.
4. **Competing Thesis**: A plausible alternative explanation that would also fit the facts.
5. **Confidence**: Must be a number between 0.0 and 1.0.

OUTPUT (JSON):
{{
    "strategic_context": "Comprehensive background on players and history...",
    "causal_reasoning": "Deep analysis of why this is happening and the impact...",
    "main_thesis": "The strategic signal identified...",
    "thesis_evidence": ["evidence 1", "evidence 2"],
    "thesis_confidence": 0.X,
    "competing_thesis": "Alternative interpretation...",
    "competing_evidence": ["evidence"],
    "competing_confidence": 0.X,
    "why_main_over_competing": "Reasoning for prioritizing the main thesis"
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


# Final narrative generation
NARRATIVE_PROMPT = """You are a Senior Strategic Advisor providing an intelligence briefing to a VIP client.

STATEMENT ANALYZED: "{tweet}"
STAKEHOLDERS: {actions}

KEY INPUTS:
- Strategic Context: {strategic_context}
- Causal Reasoning: {causal_reasoning}
- Main Thesis: {main_thesis} (Confidence: {thesis_confidence})
- Competing Thesis: {competing_thesis}
- Red Team Review: {challenges}

TASK: Write a sophisticated, deep-dive intelligence brief.
1. **The Lead**: Summarize the event and its immediate strategic meaning.
2. **The Deep Dive**: Use the Strategic Context and Causal Reasoning to explain the "inner workings" of this event. Why does it matter to the bigger picture?
3. **The Counter-Perspective**: Present the competing thesis and why it's worth considering.
4. **Risk Assessment**: What should the client watch for next? Mention the Falsifiable Condition.

TONE: Professional, authoritative, yet explanatory. Break down complex jargon. Use clear logic.

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
