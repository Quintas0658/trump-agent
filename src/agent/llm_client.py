"""Gemini LLM client - Wrapper for Google Cloud Vertex AI."""

from dataclasses import dataclass
from typing import Optional
import vertexai
from vertexai.generative_models import GenerativeModel, GenerationConfig

from src.config import config
from src.agent import prompts


@dataclass
class LLMResponse:
    """Response from the LLM."""
    content: str
    model: str
    usage: Optional[dict] = None


class GeminiClient:
    """Client for Google Vertex AI.
    
    Uses gemini-2.0-flash for high-performance strategic analysis.
    """
    
    def __init__(self, project_id: str = "trump-analyst", location: str = "us-central1"):
        self.project_id = project_id
        self.location = location
        self.model_name = "gemini-2.0-flash"
        
        # Initialize vertexai
        vertexai.init(project=self.project_id, location=self.location)
        self.model = GenerativeModel(self.model_name)
    
    def generate(
        self, 
        prompt: str, 
        temperature: float = 0.7,
        max_tokens: int = 4096,
        model: Optional[str] = None,
        **kwargs
    ) -> LLMResponse:
        """Generate a response from Vertex AI."""
        
        # Use specific model if provided, otherwise default
        active_model = GenerativeModel(model) if model else self.model
        
        generation_config = GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        )
        
        try:
            response = active_model.generate_content(
                prompt,
                generation_config=generation_config,
            )
            
            return LLMResponse(
                content=response.text,
                model=model or self.model_name,
                usage={
                    "prompt_tokens": response.usage_metadata.prompt_token_count if hasattr(response, 'usage_metadata') else None,
                    "completion_tokens": response.usage_metadata.candidates_token_count if hasattr(response, 'usage_metadata') else None,
                }
            )
        except Exception as e:
            raise RuntimeError(f"Vertex AI error: {e}") from e
    
    def extract_entities(self, text: str) -> list[str]:
        """Extract key entities from text."""
        prompt = f"""Extract key entities (people, countries, organizations, topics) from this text.
Return ONLY a comma-separated list of entity names, nothing else.

TEXT: "{text}"

ENTITIES:"""
        
        response = self.generate(prompt, temperature=0.1)
        entities = [e.strip() for e in response.content.split(",") if e.strip()]
        return entities
    
    def analyze_for_actions(self, text: str, search_context: str, memory_context: str = "") -> dict:
        """Analyze text to detect real-world actions using shared prompt."""
        prompt = prompts.JUDGMENT_0_PROMPT.format(
            tweet=text, search_context=search_context, memory_context=memory_context
        )
        
        response = self.generate(prompt, temperature=0.2)
        import json
        try:
            content = response.content.strip()
            if "```json" in content: content = content.split("```json")[1].split("```")[0]
            elif "```" in content: content = content.split("```")[1]
            return json.loads(content)
        except:
            return {"judgment_0": "LANGUAGE_ONLY", "actions_found": [], "reasoning": "Parse error"}

    def generate_thesis_and_competing(self, tweet, context, actions):
        """Strategic thesis generation using shared prompt."""
        prompt = prompts.JUDGMENT_2_PROMPT.format(
            tweet=tweet, context=context, actions=actions
        )
        # Use Thinking Model for deep strategic analysis
        # Note: Thinking models may not support temperature, so we let it default (None)
        # or use a standard value. We'll try passing model arg.
        response = self.generate(
            prompt, 
            temperature=0.7,  # Thinking models can handle creativity
            model="gemini-2.0-flash-thinking-exp-01-21"
        )
        import json
        try:
            content = response.content.strip()
            if "```json" in content: content = content.split("```json")[1].split("```")[0]
            elif "```" in content: content = content.split("```")[1]
            return json.loads(content)
        except: return {"main_thesis": "Error", "thesis_evidence": [], "thesis_confidence": 0}

    def generate_falsifiable_condition(self, thesis, context):
        """Standard falsifiable condition logic using shared prompt."""
        prompt = prompts.JUDGMENT_3_PROMPT.format(
            thesis=thesis, context=context
        )
        response = self.generate(prompt, temperature=0.3)
        import json
        try:
            content = response.content.strip()
            if "```json" in content: content = content.split("```json")[1].split("```")[0]
            elif "```" in content: content = content.split("```")[1]
            return json.loads(content)
        except: return {"falsifiable_condition": "Error", "deadline_days": 7}

    def red_team_challenge(self, thesis, evidence):
        """Standard red team logic using shared prompt."""
        prompt = prompts.RED_TEAM_PROMPT.format(
            thesis=thesis, evidence=evidence
        )
        response = self.generate(prompt, temperature=0.6)
        import json
        try:
            content = response.content.strip()
            if "```json" in content: content = content.split("```json")[1].split("```")[0]
            elif "```" in content: content = content.split("```")[1]
            return json.loads(content)
        except: return {"challenges": [], "overall_severity": "low"}


def get_gemini_client(mock: bool = False) -> GeminiClient:
    """Get the Vertex AI integrated client."""
    if mock:
        from src.agent.llm_client import MockGeminiClient
        return MockGeminiClient()
    return GeminiClient()

class MockGeminiClient:
    """Fallback mock client."""
    def generate(self, prompt, model: Optional[str] = None, **kwargs):
        return LLMResponse(content='{"status": "mock"}', model=model or "mock")
    def extract_entities(self, text): return ["MockEntity"]
    def analyze_for_actions(self, t, c): return {"has_actions": False}
    def generate_thesis_and_competing(self, t, c, a): return {"main_thesis": "Mock"}
    def generate_falsifiable_condition(self, t, c): return {"falsifiable_condition": "Mock"}
    def red_team_challenge(self, t, e): return {"challenges": []}
