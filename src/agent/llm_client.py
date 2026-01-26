"""Gemini LLM client - Wrapper for Google Cloud Vertex AI using new GenAI SDK."""

import os
from dataclasses import dataclass
from typing import Optional

# New SDK imports
from google import genai
from google.genai.types import GenerateContentConfig, ThinkingConfig

from src.config import config
from src.agent import prompts


@dataclass
class LLMResponse:
    """Response from the LLM."""
    content: str
    model: str
    usage: Optional[dict] = None
    thoughts_token_count: Optional[int] = None  # Track thinking tokens
    function_call: Optional[object] = None  # For ReAct function calling


class GeminiClient:
    """Client for Google Vertex AI using the new GenAI SDK.
    
    Uses gemini-2.5-flash with Thinking mode for deep strategic analysis.
    """
    
    def __init__(self, project_id: str = "trump-analyst", location: str = "us-central1"):
        self.project_id = project_id
        self.location = location
        self.model_name = "gemini-2.0-flash"  # Default for fast operations
        self.thinking_model = "gemini-2.5-flash"  # For deep analysis with Thinking
        
        # Initialize new GenAI client with Vertex AI
        os.environ["GOOGLE_CLOUD_PROJECT"] = self.project_id
        os.environ["GOOGLE_CLOUD_LOCATION"] = self.location
        os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"
        self.client = genai.Client()
    
    def generate(
        self, 
        prompt: str, 
        temperature: float = 0.7,
        max_tokens: int = 4096,
        model: Optional[str] = None,
        thinking_budget: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """Generate a response from Vertex AI with optional Thinking mode."""
        
        active_model = model or self.model_name
        
        # Build config with optional thinking
        config_kwargs = {}
        if thinking_budget is not None:
            config_kwargs["thinking_config"] = ThinkingConfig(thinking_budget=thinking_budget)
        
        try:
            response = self.client.models.generate_content(
                model=active_model,
                contents=prompt,
                config=GenerateContentConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                    **config_kwargs
                ) if config_kwargs else None,
            )
            
            # Extract thinking token count if available
            thoughts_tokens = None
            if hasattr(response, 'usage_metadata') and hasattr(response.usage_metadata, 'thoughts_token_count'):
                thoughts_tokens = response.usage_metadata.thoughts_token_count
            
            return LLMResponse(
                content=response.text,
                model=active_model,
                usage={
                    "prompt_tokens": response.usage_metadata.prompt_token_count if hasattr(response, 'usage_metadata') else None,
                    "completion_tokens": response.usage_metadata.candidates_token_count if hasattr(response, 'usage_metadata') else None,
                },
                thoughts_token_count=thoughts_tokens
            )
        except Exception as e:
            raise RuntimeError(f"Vertex AI error: {e}") from e
    
    def generate_with_tools(
        self,
        messages: list,
        tools=None,
        temperature: float = 0.7,
        max_tokens: int = 8192,
        model: str = None,
        thinking_budget: int = None,
    ) -> LLMResponse:
        """Generate a response with function calling support for ReAct loop.
        
        Args:
            messages: Conversation history as list of dicts with role/content
            tools: Tool object with function declarations
            temperature: Sampling temperature
            max_tokens: Max output tokens
            model: Model to use (defaults to thinking_model)
            thinking_budget: Token budget for thinking mode
            
        Returns:
            LLMResponse with either content or function_call populated
        """
        from google.genai.types import Content, Part
        
        active_model = model or self.thinking_model
        
        # Convert messages to Content objects
        contents = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            # Handle function responses
            if role == "function":
                # Function result format for Gemini
                contents.append(Content(
                    role="function",
                    parts=[Part.from_function_response(
                        name=msg.get("name", "unknown"),
                        response={"result": content}
                    )]
                ))
            elif role == "assistant" and msg.get("function_call"):
                # Assistant's function call
                fc = msg["function_call"]
                contents.append(Content(
                    role="model",
                    parts=[Part.from_function_call(
                        name=fc["name"],
                        args=fc["arguments"]
                    )]
                ))
            else:
                # Regular user/assistant message
                gemini_role = "model" if role == "assistant" else "user"
                if content:  # Only add if content exists
                    contents.append(Content(
                        role=gemini_role,
                        parts=[Part.from_text(text=content)]
                    ))
        
        # Build config with tools inside
        config_kwargs = {"temperature": temperature, "max_output_tokens": max_tokens}
        if thinking_budget is not None:
            config_kwargs["thinking_config"] = ThinkingConfig(thinking_budget=thinking_budget)
        if tools:
            config_kwargs["tools"] = [tools]
        
        try:
            response = self.client.models.generate_content(
                model=active_model,
                contents=contents,
                config=GenerateContentConfig(**config_kwargs),
            )
            
            # Check for function call in response
            function_call = None
            content_text = ""
            
            if response.candidates and response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    if hasattr(part, 'function_call') and part.function_call:
                        function_call = part.function_call
                    elif hasattr(part, 'text') and part.text:
                        content_text += part.text
            
            # Extract thinking tokens
            thoughts_tokens = None
            if hasattr(response, 'usage_metadata') and hasattr(response.usage_metadata, 'thoughts_token_count'):
                thoughts_tokens = response.usage_metadata.thoughts_token_count
            
            return LLMResponse(
                content=content_text,
                model=active_model,
                usage={
                    "prompt_tokens": response.usage_metadata.prompt_token_count if hasattr(response, 'usage_metadata') else None,
                    "completion_tokens": response.usage_metadata.candidates_token_count if hasattr(response, 'usage_metadata') else None,
                },
                thoughts_token_count=thoughts_tokens,
                function_call=function_call,
            )
            
        except Exception as e:
            raise RuntimeError(f"Vertex AI (tools) error: {e}") from e
    
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
        """Strategic thesis generation with Thinking mode enabled."""
        import re
        
        # Strip HTML tags from input to prevent pollution
        def strip_html(text):
            if not text:
                return text
            clean = re.sub(r'<[^>]+>', '', str(text))
            return clean.strip()
        
        clean_tweet = strip_html(tweet)
        clean_context = strip_html(context)
        
        prompt = prompts.JUDGMENT_2_PROMPT.format(
            tweet=clean_tweet, context=clean_context, actions=actions
        )
        # Use Gemini 2.5 Flash with explicit Thinking budget for deep reasoning
        response = self.generate(
            prompt, 
            temperature=0.5, 
            model=self.thinking_model,  # gemini-2.5-flash
            thinking_budget=4096  # Enable deep thinking
        )
        
        # Log thinking tokens if available
        if response.thoughts_token_count:
            print(f"[Thinking] Model used {response.thoughts_token_count} tokens for reasoning.")
        else:
            print("[Thinking] No thinking token count returned (may not be supported in this config).")
        
        import json
        try:
            content = response.content.strip()
            # Debug: Log first 500 chars of raw response
            print(f"[DEBUG J2] Raw response (first 500 chars): {content[:500]}...")
            
            if "```json" in content: content = content.split("```json")[1].split("```")[0]
            elif "```" in content: content = content.split("```")[1]
            parsed = json.loads(content)
            
            # Ensure pillars key exists
            if 'pillars' not in parsed:
                print("[DEBUG J2] 'pillars' key missing, checking for alternative keys...")
                # Handle legacy format or error cases
                if 'main_thesis' in parsed:
                    parsed['pillars'] = [{
                        'title': 'Analysis Result',
                        'summary': parsed.get('main_thesis', 'Unknown'),
                        'confidence': parsed.get('thesis_confidence', 0.5),
                        'evidence': parsed.get('thesis_evidence', [])
                    }]
            
            return parsed
        except Exception as e:
            print(f"[DEBUG J2] JSON parse failed: {e}")
            return {"pillars": [], "main_thesis": "Error", "thesis_evidence": [], "thesis_confidence": 0}

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
