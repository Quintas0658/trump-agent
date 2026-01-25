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
JUDGMENT_2_PROMPT = """Generate the main thesis AND a competing explanation.

STATEMENT: "{tweet}"
ACTIONS: {actions}
CONTEXT: {context}

RULES:
1. Main thesis = most likely interpretation
2. Competing thesis = plausible alternative
3. You MUST provide BOTH
4. Confidence 0.0-1.0 based on evidence strength

OUTPUT (JSON):
{{
    "main_thesis": "...",
    "thesis_evidence": ["evidence 1", "evidence 2"],
    "thesis_confidence": 0.X,
    "competing_thesis": "alternative interpretation",
    "competing_evidence": ["evidence"],
    "competing_confidence": 0.X,
    "why_main_over_competing": "reasoning"
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
NARRATIVE_PROMPT = """Generate the final analysis report.

STATEMENT ANALYZED: "{tweet}"
POSTED AT: {posted_at}

JUDGMENT RESULTS:
- Judgment 0: {j0_result} (Actions: {actions})
- Judgment 1: {j1_result}
- Main Thesis: {main_thesis} (Confidence: {thesis_confidence})
- Competing Thesis: {competing_thesis}

RED TEAM CHALLENGES:
{challenges}

FALSIFIABLE CONDITION:
{falsifiable_condition}
Deadline: {deadline}

CONTEXT USED:
{context}

WRITE A CONCISE INTELLIGENCE BRIEF (3-5 paragraphs):
1. What happened and what it means (main interpretation)
2. Alternative interpretation (competing thesis)
3. Key uncertainties and what to watch
4. The specific prediction to track

TONE: Intelligence analyst, not pundit. Facts first, speculation labeled.

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
