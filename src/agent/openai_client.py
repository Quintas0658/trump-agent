"""OpenAI Client - Wrapper for GPT-4o API calls."""

import os
from dataclasses import dataclass
from typing import Optional
from openai import OpenAI


@dataclass
class GPTResponse:
    """Response from GPT-4o."""
    content: str
    model: str
    usage: Optional[dict] = None


class OpenAIClient:
    """Client for OpenAI GPT-4o API.
    
    Used for question decomposition (breaking complex situations into 
    investigative questions).
    """
    
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key or api_key == "your-openai-api-key-here":
            raise ValueError("OPENAI_API_KEY not set in .env file")
        
        self.client = OpenAI(api_key=api_key)
        self.model = "gpt-4o"  # Fast and capable
    
    def generate(
        self, 
        prompt: str, 
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> GPTResponse:
        """Generate a response from GPT-4o."""
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        
        return GPTResponse(
            content=response.choices[0].message.content,
            model=self.model,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
            }
        )
