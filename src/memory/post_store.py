"""Post store - Storage for Trump posts and daily reports (Memory persistence layer)."""

from datetime import datetime, timedelta, date
from typing import Optional, List, Dict, Any
from supabase import Client, create_client

from src.config import config


class PostStore:
    """Store for Trump posts and daily analysis reports.
    
    Provides persistent memory for:
    - Raw Truth Social posts (trump_posts table)
    - Daily strategic analysis reports (daily_reports table)
    """
    
    def __init__(self, client: Optional[Client] = None):
        if client:
            self.client = client
        elif config.SUPABASE_URL and config.SUPABASE_ANON_KEY:
            self.client = create_client(config.SUPABASE_URL, config.SUPABASE_ANON_KEY)
        else:
            self.client = None
            print("[!] Supabase credentials missing. PostStore operating in NO-OP mode.")
    
    # ==================== POSTS ====================
    
    def save_posts(self, posts: list) -> int:
        """Save posts to Supabase. Upserts to avoid duplicates.
        
        Args:
            posts: List of TruthPost objects (or dicts with post_id, text, created_at)
            
        Returns:
            Number of posts saved
        """
        if not self.client or not posts:
            return 0
        
        saved_count = 0
        for post in posts:
            try:
                # Check if it's a dict or an object
                if isinstance(post, dict):
                    post_id = post.get('id', '')
                    text = post.get('text', '')
                    created_at = post.get('created_at')
                else:
                    # It's a TruthPost or similar object
                    post_id = getattr(post, 'id', '')
                    text = getattr(post, 'text', '')
                    created_at = getattr(post, 'created_at', None)
                
                if isinstance(created_at, datetime):
                    created_at = created_at.isoformat()
                
                # Skip posts without valid ID
                if not post_id:
                    print(f"[!] Skipping post with empty ID")
                    continue
                
                data = {
                    "post_id": str(post_id),
                    "text": text,
                    "created_at": created_at,
                    "fetched_at": datetime.utcnow().isoformat(),
                }
                
                # Upsert using post_id as unique key
                self.client.table("trump_posts").upsert(
                    data, 
                    on_conflict="post_id"
                ).execute()
                saved_count += 1
                
            except Exception as e:
                print(f"[!] Error saving post: {e}")
                continue
        
        return saved_count
    
    def get_posts_in_range(self, start_date: date, end_date: date, limit: int = 100) -> List[Dict]:
        """Get posts within a date range."""
        if not self.client:
            return []
        
        result = self.client.table("trump_posts") \
            .select("*") \
            .gte("created_at", start_date.isoformat()) \
            .lte("created_at", end_date.isoformat()) \
            .order("created_at", desc=True) \
            .limit(limit) \
            .execute()
        
        return result.data
    
    # ==================== DAILY REPORTS ====================
    
    def save_daily_report(
        self, 
        report_date: date, 
        report_content: str, 
        summary: str = None,
        key_hypotheses: list = None,
        key_entities: list = None
    ) -> str:
        """Save a daily analysis report.
        
        Args:
            report_date: The date of the analysis
            report_content: Full markdown report content
            summary: 1-2 sentence summary for quick recall
            key_hypotheses: List of hypothesis dicts [{hypothesis, confidence, deadline}]
            key_entities: List of key entities mentioned
            
        Returns:
            The report ID
        """
        if not self.client:
            return "mock-report-id"
        
        data = {
            "report_date": report_date.isoformat(),
            "report_content": report_content,
            "summary": summary,
            "key_hypotheses": key_hypotheses or [],
            "key_entities": key_entities or [],
        }
        
        # Upsert using report_date as unique key
        result = self.client.table("daily_reports").upsert(
            data,
            on_conflict="report_date"
        ).execute()
        
        return result.data[0]["id"] if result.data else "saved"
    
    def get_past_report(self, days_ago: int = 1) -> Optional[Dict[str, Any]]:
        """Get a report from N days ago.
        
        Args:
            days_ago: Number of days in the past (1 = yesterday)
            
        Returns:
            Report dict with keys: report_date, report_content, summary, key_hypotheses, key_entities
            Or None if not found
        """
        if not self.client:
            return None
        
        target_date = (datetime.utcnow() - timedelta(days=days_ago)).date()
        
        result = self.client.table("daily_reports") \
            .select("*") \
            .eq("report_date", target_date.isoformat()) \
            .limit(1) \
            .execute()
        
        return result.data[0] if result.data else None
    
    def get_recent_reports(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get reports from the last N days.
        
        Args:
            days: Number of days to look back
            
        Returns:
            List of report dicts, newest first
        """
        if not self.client:
            return []
        
        cutoff = (datetime.utcnow() - timedelta(days=days)).date()
        
        result = self.client.table("daily_reports") \
            .select("*") \
            .gte("report_date", cutoff.isoformat()) \
            .order("report_date", desc=True) \
            .execute()
        
        return result.data
    
    def search_reports(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search report content (basic text search).
        
        Args:
            query: Search string
            limit: Max results
            
        Returns:
            Matching reports
        """
        if not self.client:
            return []
        
        result = self.client.table("daily_reports") \
            .select("*") \
            .ilike("report_content", f"%{query}%") \
            .order("report_date", desc=True) \
            .limit(limit) \
            .execute()
        
        return result.data
