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
# Judgment 2: Multi-Pillar Strategic Analysis
JUDGMENT_2_PROMPT = """You are a Senior Strategic Analyst. Your task is to identify ALL distinct strategic themes (Intelligence Pillars) present in these signals.

STATEMENT BATCH: "{tweet}"
ACTIONS RECORDED: {actions}
SEARCH CONTEXT: {context}

YOUR GOAL: Segment these pulses into distinct "Intelligence Pillars".
CRITICAL: Do not ignore international events (Iran, Venezuela, etc.) if they are in the context. Every major geopolitical theatre is a valid pillar.

PRYING QUESTIONS FOR EACH PILLAR:
- WHO: Who are the key players?
- WHY: Why is this happening now?
- SO WHAT: What is the strategic outcome?

OUTPUT (JSON object with a list of pillars):
{{
    "pillars": [
        {{
            "title": "Short descriptive title (e.g., 'The China-Canada Trade Warning')",
            "summary": "1-2 sentence high-level summary",
            "strategic_context": "Deep background...",
            "causal_reasoning": "Analysis of why this is happening...",
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
# Multi-Pillar Narrative generation
NARRATIVE_PROMPT = """You are a Senior Advisor explaining complex geopolitical strategy to a client who is smart but NOT an expert in US politics or finance.

TASK: Write a clear, accessible intelligence briefing based on the identified pillars.

{pillars_data}

STYLE GUIDELINES (CRITICAL):
1. **Plain English**: Avoid "consultant speak". Don't say "exogenous shock", say "sudden outside event".
2. **Explain Concepts**: If you mention a specific bill, person, or term (like "Section 232"), briefly explain WHAT it is.
3. **Connect the Dots**: Explicitly say "This matters because..." for every point.
4. **No Fluff**: Get straight to the point.

STRUCTURE:
1. **The Big Picture** (Executive Summary): One paragraph on how these stories fit together.
2. **Deep Dives**: For each pillar, use this format:
   - **Headline**: Catchy and descriptive.
   - **The Surface**: What is the official news? (Simple terms)
   - **The Reality**: What is actually happening behind the scenes?
   - **Who Wins/Loses**: Clear winners and losers.
   - **Why You Care**: How this affects the market or the future.

3. **Risk Radar**: What specifically should we watch in the next 7 days?

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


# ============================================================================
# GATEKEEPER & EDITOR PROMPTS (Strategic Depth Reinforcement)
# ============================================================================

GATEKEEPER_PROMPT = """You are a ruthless Senior Editor at a top-tier intelligence firm. 
Your job is to CRITIQUE this draft strategic memo and identify its WEAK POINTS.

[DRAFT REPORT]
{draft_report}

[ORIGINAL CONTEXT AVAILABLE]
{original_context}

CRITIQUE RULES:
1. **Missing Specifics**: Is anything asserted without a specific name, date, or number? (e.g., "sources say" is weak)
2. **Shallow Analysis**: Is any pillar just rewriting the news instead of explaining the *why* and *who benefits*?
3. **Ignored Context**: Is there something in the ORIGINAL CONTEXT that the draft failed to mention?
4. **Logical Gaps**: Are there any claims that don't logically follow from the evidence?

For EACH significant weakness, generate 2-3 highly specific "Deep Dive Questions" that a junior analyst should research.

OUTPUT (JSON):
{{
    "overall_assessment": "One sentence summary of draft quality",
    "critiques": [
        {{
            "pillar_title": "The pillar/section with the problem",
            "weakness": "What exactly is wrong",
            "deep_dive_questions": [
                "Specific search query 1 to fix this",
                "Specific search query 2"
            ],
            "severity": "minor|moderate|critical"
        }}
    ]
}}

If the draft is excellent and has no major issues, return an empty critiques array."""


EDITOR_PROMPT = """You are an experienced intelligence analyst tasked with REFINING a strategic memo.

[ORIGINAL DRAFT]
{draft_report}

[CRITIQUES IDENTIFIED]
{critique_summary}

[NEW EVIDENCE FROM DEEP DIVES]
{new_evidence}

YOUR TASK:
1. Take the original draft and INTEGRATE the new evidence into the weak sections.
2. Do NOT rewrite the entire report. Keep the good parts intact.
3. Where new evidence is added, make it seamless—don't say "According to new sources" or break the narrative flow.
4. If the new evidence contradicts the draft, update the analysis accordingly.
5. Preserve the original structure (Executive Summary, Pillars, Tables, etc.)

OUTPUT the complete refined memo (not just the changes)."""

