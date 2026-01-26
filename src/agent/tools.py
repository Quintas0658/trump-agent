"""Tool definitions for ReAct Agent with Gemini Function Calling."""

from typing import List
from google.genai.types import FunctionDeclaration, Tool


# ============================================
# Tool 1: Search News (Tavily)
# ============================================
SEARCH_NEWS = FunctionDeclaration(
    name="search_news",
    description="""Search for recent news articles using Tavily search engine.
Use this tool when you need:
- Current events context about a topic
- Verification of claims made in posts
- Background information on entities mentioned
- Breaking news that might be relevant to the analysis""",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query. Be specific, e.g., 'Tom Homan Minnesota visit January 2026'"
            }
        },
        "required": ["query"]
    }
)


# ============================================
# Tool 2: Recall Past Analysis (Memory)
# ============================================
RECALL_PAST_ANALYSIS = FunctionDeclaration(
    name="recall_past_analysis",
    description="""Retrieve previous analysis reports from memory.
Use this tool when you need:
- To check if a topic was analyzed before
- To verify if prior predictions came true
- To identify ongoing narrative patterns
- To compare today's messaging with yesterday's""",
    parameters={
        "type": "object",
        "properties": {
            "days_ago": {
                "type": "integer",
                "description": "How many days back to look (1 = yesterday, 7 = one week ago)"
            },
            "search_term": {
                "type": "string",
                "description": "Optional keyword to search within past reports (e.g., 'Canada tariff')"
            }
        },
        "required": ["days_ago"]
    }
)


# ============================================
# Tool 3: Get Entity History (Future expansion)
# ============================================
GET_ENTITY_HISTORY = FunctionDeclaration(
    name="get_entity_history",
    description="""Get historical context and past mentions of a specific person or organization.
Use this tool when you need:
- Background on a political figure
- Historical relationship between entities
- Past positions or statements by an entity""",
    parameters={
        "type": "object",
        "properties": {
            "entity_name": {
                "type": "string",
                "description": "Name of the entity (e.g., 'Ilhan Omar', 'Tom Homan', 'National Trust for Historic Preservation')"
            }
        },
        "required": ["entity_name"]
    }
)


# ============================================
# Combined Tool Set for Agent
# ============================================
def get_agent_tools() -> Tool:
    """Get the complete tool set for the ReAct agent."""
    return Tool(
        function_declarations=[
            SEARCH_NEWS,
            RECALL_PAST_ANALYSIS,
            GET_ENTITY_HISTORY,
        ]
    )


def get_tool_names() -> List[str]:
    """Get list of available tool names."""
    return [
        "search_news",
        "recall_past_analysis",
        "get_entity_history",
    ]
