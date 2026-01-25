"""Truth Social scraper - Fetches Trump's posts via Apify."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import httpx

from src.config import config


@dataclass
class TruthPost:
    """A single Truth Social post."""
    id: str
    text: str
    created_at: datetime
    media_urls: list[str]
    reply_count: int
    repost_count: int
    like_count: int
    is_repost: bool
    original_author: Optional[str] = None


class TruthSocialScraper:
    """Fetches Trump's Truth Social posts using Apify actor.
    
    Uses: https://apify.com/curious_coder/truth-social-scraper
    """
    
    APIFY_BASE_URL = "https://api.apify.com/v2"
    TASK_ID = "lissome_jolt~truth-social-scraper-task"
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or config.APIFY_API_KEY
        self.client = httpx.Client(timeout=180.0) # Longer timeout for sync run
    
    def fetch_recent_posts(
        self, 
        username: str = "realDonaldTrump",
        max_posts: int = 5
    ) -> list[TruthPost]:
        """Fetch recent posts synchronously using the specific task."""
        if not self.api_key:
            print("[!] APIFY_API_KEY missing. Returning empty list.")
            return []
            
        url = f"{self.APIFY_BASE_URL}/actor-tasks/{self.TASK_ID}/run-sync-get-dataset-items"
        
        # Override input configuration
        run_input = {
            "username": username,
            "maxPosts": max_posts,
        }
        
        try:
            print(f"[*] Triggering Apify sync task for {username}...")
            response = self.client.post(
                url,
                params={"token": self.api_key},
                json=run_input,
            )
            response.raise_for_status()
            
            items = response.json()
            print(f"[*] Successfully fetched {len(items)} posts from Truth Social.")
            return [self._parse_post(item) for item in items]
        except httpx.HTTPError as e:
            print(f"Failed to fetch from Apify: {e}")
            return []
    
    def _parse_post(self, item: dict) -> TruthPost:
        """Parse a raw API response into a TruthPost."""
        # Handle different date formats
        created_at_str = item.get("createdAt") or item.get("created_at", "")
        try:
            created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            created_at = datetime.utcnow()
        
        # Extract media URLs
        media_urls = []
        media = item.get("media") or item.get("mediaAttachments") or []
        for m in media:
            if isinstance(m, dict):
                url = m.get("url") or m.get("previewUrl")
                if url:
                    media_urls.append(url)
        
        return TruthPost(
            id=str(item.get("id", "")),
            text=item.get("content") or item.get("text", ""),
            created_at=created_at,
            media_urls=media_urls,
            reply_count=item.get("repliesCount", 0),
            repost_count=item.get("reblogsCount", 0),
            like_count=item.get("favouritesCount", 0),
            is_repost=item.get("reblog") is not None,
            original_author=item.get("reblog", {}).get("account", {}).get("username") 
                if item.get("reblog") else None,
        )
    
    def close(self):
        """Close the HTTP client."""
        self.client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self.close()


# Mock implementation for testing without API
class MockTruthSocialScraper:
    """Mock scraper for testing."""
    
    def fetch_recent_posts(self, username: str = "realDonaldTrump", max_posts: int = 20) -> list[TruthPost]:
        """Return mock posts for testing."""
        return [
            TruthPost(
                id="123456",
                text="Just had a GREAT call with President Delcy of Venezuela. She understands STRENGTH! 🇺🇸🇻🇪",
                created_at=datetime(2026, 1, 12, 14, 22),
                media_urls=[],
                reply_count=1234,
                repost_count=5678,
                like_count=23456,
                is_repost=False,
            ),
            TruthPost(
                id="123457",
                text="Good news from Iran. They have stopped killing people...",
                created_at=datetime(2026, 1, 16, 10, 30),
                media_urls=[],
                reply_count=987,
                repost_count=4321,
                like_count=19876,
                is_repost=False,
            ),
        ]
