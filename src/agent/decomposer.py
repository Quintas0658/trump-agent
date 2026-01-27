"""Question Decomposer - Uses GPT-4o to break complex situations into investigative questions."""

from typing import Optional
from src.agent.openai_client import OpenAIClient


DECOMPOSER_PROMPT = """You are a "Constraint Hunter" for a Power Physics Engine.
Your job is NOT to ask "Why", but to find the physical boundaries and resource flows.

**CORE AXIOM: "Politics is the art of the possible. Physics defines the possible."**

[SEARCH PROTOCOL: ATOMIC FACT MINING]

1.  **Hunt for Constraints ( The Hard Ceiling)**:
    -   Search for *deadlines* (e.g., "debt ceiling expiration date", "trade deal ratification deadline").
    -   Search for *budget limits* (e.g., "federal agency insolvency date").
    -   Search for *physical limits* (e.g., "oil tanker capacity straits of hormuz").

2.  **Trace Resource Flows (The Energy)**:
    -   Don't ask "Who supports this?". Ask "Who funded this?".
    -   Search for "lobbying disclosures", "campaign donations", "contract awards".
    -   Search for "capital flight" (e.g., "Korea foreign direct investment outflow 2026").

3.  **Find Entropy/Anomalies (The Glitch)**:
    -   Search for *timing coincidences*. (e.g., "What else happened on [Date] of tweet?").
    -   Search for *silence*. (e.g., "Official denial of [Event]").

**Task**: Generate 15 SEARCH QUERIES.
- 5 Constraint Queries (Deadlines/Budgets)
- 5 Resource Flow Queries (Money/Contracts)
- 5 Entropy/Anomaly Queries (Timing/Denials)

You are given:
1. Trump's recent social media posts
2. Politico news briefings
3. Active global hotspots

Return ONLY a JSON array of strings.

You are given:
1. Trump's recent social media posts
2. Politico news briefings
3. Active global hotspots

Your task: Generate 10-15 specific, searchable questions that uncover the TRANSACTIONAL TRUTH.

---

## RAW DATA

### Trump Posts (Last 48h):
{posts_text}

### Politico Briefings:
{emails_text}

### Active Global Hotspots:
{hotspots_text}

---

## OUTPUT FORMAT

Return ONLY a JSON array of questions, like this:
[
  "What is the real connection between the Korea tariff and the Coupang investigation?",
  "Who is Alex Pretti and what was his background before being shot?",
  "Why is Trump silent about the federal agent shooting?",
  ...
]

Generate 10-15 highly specific, investigative questions. Each question should be:
1. Searchable (can be answered by web search)
2. Non-obvious (digs deeper than surface news)
3. Action-oriented (leads to tradable insight)

Return ONLY the JSON array, no other text.
"""


async def decompose_questions(
    posts: list[dict],
    emails: list[dict],
    hotspots: list[dict],
    client: Optional[OpenAIClient] = None
) -> list[str]:
    """Use GPT-4o to decompose the situation into investigative questions.
    
    Args:
        posts: List of Trump posts with 'text' and 'created_at' fields
        emails: List of Politico emails with 'subject' and 'body' fields
        hotspots: List of world_facts events
        client: Optional OpenAI client (creates one if not provided)
    
    Returns:
        List of 10-15 investigative questions
    """
    import json
    
    if client is None:
        client = OpenAIClient()
    
    # Format posts
    posts_text = ""
    for p in posts[:15]:  # Limit to 15 most recent
        posts_text += f"- {p.get('text', '')[:200]}...\n"
    
    # Format emails
    emails_text = ""
    for e in emails[:5]:  # Limit to 5 most recent
        subject = e.get('subject', 'No subject')
        body = e.get('body', '')[:500]
        emails_text += f"### {subject}\n{body}\n\n"
    
    # Format hotspots
    hotspots_text = ""
    for h in hotspots[:10]:  # Limit to 10
        region = h.get('region', 'Unknown')
        headline = h.get('headline', '')
        hotspots_text += f"- [{region}] {headline}\n"
    
    # Build prompt
    prompt = DECOMPOSER_PROMPT.format(
        posts_text=posts_text or "No posts available",
        emails_text=emails_text or "No emails available",
        hotspots_text=hotspots_text or "No hotspots available",
    )
    
    print("[Decomposer] Asking GPT-4o to generate investigative questions...")
    
    response = client.generate(prompt, temperature=0.7)
    
    # Parse JSON response
    try:
        questions = json.loads(response.content)
        if isinstance(questions, list):
            print(f"[Decomposer] Generated {len(questions)} questions")
            return questions[:15]  # Cap at 15
    except json.JSONDecodeError:
        # Try to extract JSON from response
        import re
        match = re.search(r'\[.*\]', response.content, re.DOTALL)
        if match:
            try:
                questions = json.loads(match.group())
                print(f"[Decomposer] Generated {len(questions)} questions (extracted)")
                return questions[:15]
            except:
                pass
    
    print("[Decomposer] Failed to parse questions, using fallback")
    return [
        "What are the hidden connections in today's news?",
        "Who benefits from Trump's announcements?",
        "What is Trump NOT talking about?",
    ]
