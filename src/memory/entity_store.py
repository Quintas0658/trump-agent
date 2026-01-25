"""Entity state store - Versioned storage for actor states."""

from datetime import datetime
from typing import Optional
from supabase import Client, create_client

from src.config import config
from src.memory.schema import EntityState
from src.memory.event_store import parse_iso_datetime


class EntityStore:
    """Versioned store for entity states (M-ENTITY layer).
    
    Always append new versions, never update existing records.
    Query by entity and get the most recent version.
    """
    
    def __init__(self, client: Optional[Client] = None):
        if client:
            self.client = client
        elif config.SUPABASE_URL and config.SUPABASE_ANON_KEY:
            self.client = create_client(config.SUPABASE_URL, config.SUPABASE_ANON_KEY)
        else:
            self.client = None
            print("[!] Supabase credentials missing. EntityStore operating in NO-OP mode.")
    
    def insert(self, entity_state: EntityState) -> str:
        """Insert a new entity state version. Returns the record ID."""
        if not self.client:
            return "mock-entity-id"
        data = {
            "entity": entity_state.entity,
            "status": entity_state.status,
            "as_of": entity_state.as_of.isoformat() if entity_state.as_of else None,
            "confidence": entity_state.confidence,
            "source_id": entity_state.source_id,
        }
        
        result = self.client.table("entity_states").insert(data).execute()
        return result.data[0]["id"]
    
    def get_current(self, entity: str) -> Optional[EntityState]:
        """Get the most recent state for an entity."""
        if not self.client:
            return None
        try:
            result = self.client.table("entity_states") \
                .select("*") \
                .eq("entity", entity) \
                .order("created_at", desc=True) \
                .limit(1) \
                .execute()
            
            if result.data:
                return self._to_entity_state(result.data[0])
            return None
        except Exception as e:
            print(f"[!] EntityStore.get_current error: {e}")
            return None
    
    def get_history(self, entity: str, limit: int = 5) -> list[EntityState]:
        """Get recent state history for an entity (for conflict resolution)."""
        if not self.client:
            return []
        result = self.client.table("entity_states") \
            .select("*") \
            .eq("entity", entity) \
            .order("created_at", desc=True) \
            .limit(limit) \
            .execute()
        
        return [self._to_entity_state(row) for row in result.data]
    
    def get_all_entities(self) -> list[str]:
        """Get list of all tracked entities."""
        if not self.client:
            return []
        try:
            result = self.client.table("entity_states") \
                .select("entity") \
                .execute()
            
            # Deduplicate
            return list(set(row["entity"] for row in result.data))
        except Exception as e:
            print(f"[!] EntityStore.get_all_entities error (table may not exist): {e}")
            return []
    
    def _to_entity_state(self, row: dict) -> EntityState:
        """Convert database row to EntityState model."""
        return EntityState(
            id=row["id"],
            entity=row["entity"],
            status=row["status"],
            as_of=parse_iso_datetime(row["as_of"]) if row["as_of"] else None,
            confidence=row["confidence"],
            source_id=row["source_id"],
            created_at=parse_iso_datetime(row["created_at"]),
        )
