"""Hypothesis store - Lifecycle management for system inferences."""

from datetime import datetime
from typing import Optional
from supabase import Client, create_client

from src.config import config
from src.memory.schema import Hypothesis, HypothesisStatus, EvidenceRef
from src.memory.event_store import parse_iso_datetime


class HypothesisStore:
    """Store for hypotheses with lifecycle management.
    
    Hypotheses follow a state machine:
    PROPOSED -> STRENGTHENED/WEAKENED -> VERIFIED/REFUTED/EXPIRED
    """
    
    def __init__(self, client: Optional[Client] = None):
        if client:
            self.client = client
        elif config.SUPABASE_URL and config.SUPABASE_ANON_KEY:
            self.client = create_client(config.SUPABASE_URL, config.SUPABASE_ANON_KEY)
        else:
            self.client = None
            print("[!] Supabase credentials missing. HypothesisStore operating in NO-OP mode.")
    
    def insert(self, hypothesis: Hypothesis) -> str:
        """Insert a new hypothesis. Returns the hypothesis ID."""
        if not self.client:
            return "mock-hypothesis-id"
        data = {
            "statement": hypothesis.statement,
            "based_on": [e.model_dump() for e in hypothesis.based_on],
            "falsifiable_condition": hypothesis.falsifiable_condition,
            "verification_deadline": hypothesis.verification_deadline.isoformat() 
                if hypothesis.verification_deadline else None,
            "status": hypothesis.status.value,
            "confidence": hypothesis.confidence,
        }
        
        result = self.client.table("hypotheses").insert(data).execute()
        return result.data[0]["id"]
    
    def update_status(
        self, 
        hypothesis_id: str, 
        new_status: HypothesisStatus,
        support_delta: int = 0,
        refute_delta: int = 0
    ) -> None:
        if not self.client:
            return
        """Update hypothesis status and evidence counts.
        
        Note: While this is an UPDATE, we're only updating lifecycle fields,
        not the core content. The hypothesis statement itself is immutable.
        """
        update_data = {
            "status": new_status.value,
        }
        
        if new_status in [HypothesisStatus.VERIFIED, HypothesisStatus.REFUTED, 
                          HypothesisStatus.EXPIRED]:
            update_data["resolved_at"] = datetime.utcnow().isoformat()
        
        # Get current counts and increment
        current = self.get_by_id(hypothesis_id)
        if current:
            update_data["support_count"] = current.support_count + support_delta
            update_data["refute_count"] = current.refute_count + refute_delta
        
        self.client.table("hypotheses") \
            .update(update_data) \
            .eq("id", hypothesis_id) \
            .execute()
    
    def get_by_id(self, hypothesis_id: str) -> Optional[Hypothesis]:
        """Get a hypothesis by ID."""
        if not self.client:
            return None
        result = self.client.table("hypotheses") \
            .select("*") \
            .eq("id", hypothesis_id) \
            .limit(1) \
            .execute()
        
        if result.data:
            return self._to_hypothesis(result.data[0])
        return None
    
    def get_pending(self) -> list[Hypothesis]:
        """Get all pending hypotheses (not yet resolved)."""
        if not self.client:
            return []
        try:
            result = self.client.table("hypotheses") \
                .select("*") \
                .in_("status", [
                    HypothesisStatus.PROPOSED.value,
                    HypothesisStatus.STRENGTHENED.value,
                    HypothesisStatus.WEAKENED.value,
                ]) \
                .order("verification_deadline", desc=False) \
                .execute()
            
            return [self._to_hypothesis(row) for row in result.data]
        except Exception as e:
            print(f"[!] HypothesisStore.get_pending error (table may not exist): {e}")
            return []
    
    def get_expired_unresolved(self) -> list[Hypothesis]:
        """Get hypotheses past their verification deadline but not resolved."""
        if not self.client:
            return []
        try:
            now = datetime.utcnow().isoformat()
            
            result = self.client.table("hypotheses") \
                .select("*") \
                .in_("status", [
                    HypothesisStatus.PROPOSED.value,
                    HypothesisStatus.STRENGTHENED.value,
                    HypothesisStatus.WEAKENED.value,
                ]) \
                .lte("verification_deadline", now) \
                .execute()
            
            return [self._to_hypothesis(row) for row in result.data]
        except Exception as e:
            print(f"[!] HypothesisStore.get_expired_unresolved error: {e}")
            return []
    
    def get_recent_resolved(self, limit: int = 10) -> list[Hypothesis]:
        """Get recently resolved hypotheses for scorecard."""
        if not self.client:
            return []
        try:
            result = self.client.table("hypotheses") \
                .select("*") \
                .in_("status", [
                    HypothesisStatus.VERIFIED.value,
                    HypothesisStatus.REFUTED.value,
                    HypothesisStatus.EXPIRED.value,
                ]) \
                .order("resolved_at", desc=True) \
                .limit(limit) \
                .execute()
            
            return [self._to_hypothesis(row) for row in result.data]
        except Exception as e:
            print(f"[!] HypothesisStore.get_recent_resolved error: {e}")
            return []
    
    def _to_hypothesis(self, row: dict) -> Hypothesis:
        """Convert database row to Hypothesis model."""
        return Hypothesis(
            id=row["id"],
            statement=row["statement"],
            based_on=[EvidenceRef(**e) for e in (row["based_on"] or [])],
            falsifiable_condition=row["falsifiable_condition"],
            verification_deadline=parse_iso_datetime(row["verification_deadline"]) 
                if row["verification_deadline"] else None,
            status=HypothesisStatus(row["status"]),
            support_count=row["support_count"],
            refute_count=row["refute_count"],
            confidence=row["confidence"],
            created_at=parse_iso_datetime(row["created_at"]),
            resolved_at=parse_iso_datetime(row["resolved_at"]) 
                if row["resolved_at"] else None,
        )
