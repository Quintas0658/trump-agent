"""Claim store - Storage for attributed statements (M-CLAIM layer)."""

from datetime import datetime
from typing import Optional, List
import re
from supabase import Client, create_client

from src.config import config
from src.memory.schema import Claim
from src.memory.event_store import parse_iso_datetime


class ClaimStore:
    """Store for attributed statements (M-CLAIM layer).
    
    Claims are stored as-is without a truth judgment. 
    They represent what someone said at a specific time.
    """
    
    def __init__(self, client: Optional[Client] = None):
        if client:
            self.client = client
        elif config.SUPABASE_URL and config.SUPABASE_ANON_KEY:
            self.client = create_client(config.SUPABASE_URL, config.SUPABASE_ANON_KEY)
        else:
            self.client = None
            print("[!] Supabase credentials missing. ClaimStore operating in NO-OP mode.")
    
    def insert(self, claim: Claim) -> str:
        """Insert a new claim. Returns the claim ID."""
        if not self.client:
            return "mock-claim-id"
            
        data = {
            "claim_text": claim.claim_text,
            "attributed_to": claim.attributed_to,
            "source_url": claim.source_url,
            "claimed_at": claim.claimed_at.isoformat() if claim.claimed_at else None,
            "batch_id": claim.batch_id,
            "processing_status": claim.processing_status.value,
        }
        
        result = self.client.table("claims").insert(data).execute()
        return result.data[0]["id"]
    
    def get_recent_by_actor(self, actor: str, limit: int = 10) -> List[Claim]:
        """Get recent claims attributed to a specific actor."""
        if not self.client:
            return []
            
        result = self.client.table("claims") \
            .select("*") \
            .eq("attributed_to", actor) \
            .order("created_at", desc=True) \
            .limit(limit) \
            .execute()
        
        return [self._to_claim(row) for row in result.data]
    
    def search_claims(self, query: str, limit: int = 10) -> List[Claim]:
        """Search claim text (basic text search)."""
        if not self.client:
            return []
            
        result = self.client.table("claims") \
            .select("*") \
            .ilike("claim_text", f"%{query}%") \
            .order("created_at", desc=True) \
            .limit(limit) \
            .execute()
        
        return [self._to_claim(row) for row in result.data]
    
    def _to_claim(self, row: dict) -> Claim:
        """Convert database row to Claim model."""
        from src.memory.schema import ClaimStatus
        
        return Claim(
            id=row["id"],
            claim_text=row["claim_text"],
            attributed_to=row["attributed_to"],
            source_url=row.get("source_url"),
            claimed_at=parse_iso_datetime(row["claimed_at"]) if row.get("claimed_at") else None,
            batch_id=row.get("batch_id"),
            processing_status=ClaimStatus(row["processing_status"]) if row.get("processing_status") else ClaimStatus.PENDING,
            created_at=parse_iso_datetime(row["created_at"]),
        )

    def get_pending_claims(self, limit: int = 50, hours: int = 24) -> List[Claim]:
        """Get claims that have not been processed yet within the time window."""
        if not self.client:
            return []
        
        from datetime import datetime, timedelta
        cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
            
        result = self.client.table("claims") \
            .select("*") \
            .eq("processing_status", "PENDING") \
            .gte("created_at", cutoff) \
            .order("created_at", desc=True) \
            .limit(limit) \
            .execute()
        
        return [self._to_claim(row) for row in result.data]

    def update_status(self, claim_id: str, status: str) -> None:
        """Update the processing status of a claim."""
        if not self.client:
            return
        self.client.table("claims").update({"processing_status": status}).eq("id", claim_id).execute()
