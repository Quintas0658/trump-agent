"""Trump Policy Analysis Agent - Configuration"""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Application configuration from environment variables."""
    
    # Supabase
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_ANON_KEY: str = os.getenv("SUPABASE_ANON_KEY", "")
    
    # Search API
    TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")
    
    # Data Ingestion
    APIFY_API_KEY: str = os.getenv("APIFY_API_KEY", "")
    
    # LLM
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    
    # Agent Settings
    MAX_SEARCH_LOOPS: int = 3
    MAX_PARALLEL_QUERIES: int = 5
    CONFIDENCE_THRESHOLD: float = 0.6
    
    # Judgment thresholds
    DIPLOMATIC_CONFIDENCE_CAP: float = 0.5
    MILITARY_CONFIDENCE_CAP: float = 0.5
    PUBLIC_POLICY_CONFIDENCE_CAP: float = 0.75
    
    # Reasoning depth
    MAX_REASONING_DEPTH: int = 2  # Allow up to 2nd order inference
    
    @classmethod
    def validate(cls) -> list[str]:
        """Validate required configuration. Returns list of missing keys."""
        missing = []
        if not cls.SUPABASE_URL:
            missing.append("SUPABASE_URL")
        if not cls.SUPABASE_ANON_KEY:
            missing.append("SUPABASE_ANON_KEY")
        if not cls.TAVILY_API_KEY:
            missing.append("TAVILY_API_KEY")
        if not cls.GOOGLE_API_KEY:
            missing.append("GOOGLE_API_KEY")
        return missing


config = Config()
