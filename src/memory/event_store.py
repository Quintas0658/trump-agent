"""Event store - Append-only storage for verified facts."""

from datetime import datetime
from typing import Optional
import re
from supabase import create_client, Client

from src.config import config
from src.memory.schema import Event, ActionType, EventStatus


def parse_iso_datetime(s: str) -> datetime:
    """Parse ISO datetime string with robust handling for various formats.
    
    Python 3.10's fromisoformat() doesn't handle all valid ISO 8601 formats,
    particularly those with non-standard microsecond precision or timezone offsets.
    """
    if not s:
        return None
    
    # Normalize the string: handle microseconds with varying precision
    # Match pattern: datetime part + optional fractional seconds + optional timezone
    match = re.match(
        r'(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2})'  # Main datetime
        r'(?:\.(\d+))?'  # Optional fractional seconds
        r'(Z|[+-]\d{2}:?\d{2})?$',  # Optional timezone
        s
    )
    
    if not match:
        # Fall back to fromisoformat for non-matching formats
        return datetime.fromisoformat(s)
    
    main_part, frac, tz = match.groups()
    
    # Normalize fractional seconds to 6 digits (microseconds)
    if frac:
        frac = frac[:6].ljust(6, '0')
        main_part = f"{main_part}.{frac}"
    
    # Normalize timezone
    if tz == 'Z':
        tz = '+00:00'
    elif tz and len(tz) == 5:  # +0000 format
        tz = f"{tz[:3]}:{tz[3:]}"
    
    if tz:
        main_part = f"{main_part}{tz}"
    
    return datetime.fromisoformat(main_part)


class EventStore:
    """Append-only store for verified events (M-EVENT layer)."""
    
    def __init__(self, client: Optional[Client] = None):
        if client:
            self.client = client
        elif config.SUPABASE_URL and config.SUPABASE_ANON_KEY:
            self.client = create_client(config.SUPABASE_URL, config.SUPABASE_ANON_KEY)
        else:
            self.client = None
            print("[!] Supabase credentials missing. Memory store operating in NO-OP mode.")
    
    def insert(self, event: Event) -> str:
        """Insert a new event. Returns the event ID."""
        if not self.client:
            return "mock-id"
        data = {
            "statement": event.statement,
            "occurred_at": event.occurred_at.isoformat() if event.occurred_at else None,
            "sources": [s.model_dump() for s in event.sources],
            "entities": event.entities,
            "tags": event.tags,
            "action_type": event.action_type.value if event.action_type else None,
            "status": event.status.value,
            "retracted": event.retracted,
        }
        
        result = self.client.table("events").insert(data).execute()
        return result.data[0]["id"]
    
    def get_recent(self, limit: int = 10) -> list[Event]:
        """Get most recent events."""
        if not self.client:
            return []
        result = self.client.table("events") \
            .select("*") \
            .order("created_at", desc=True) \
            .limit(limit) \
            .execute()
        
        return [self._to_event(row) for row in result.data]
    
    def get_by_entity(self, entity: str, limit: int = 5) -> list[Event]:
        """Get events involving a specific entity."""
        if not self.client:
            return []
        result = self.client.table("events") \
            .select("*") \
            .contains("entities", [entity]) \
            .order("occurred_at", desc=True) \
            .limit(limit) \
            .execute()
        
        return [self._to_event(row) for row in result.data]
    
    def get_actions_in_window(
        self, 
        start: datetime, 
        end: datetime
    ) -> list[Event]:
        """Get real-world actions (for Judgment 0) within a time window."""
        if not self.client:
            return []
        result = self.client.table("events") \
            .select("*") \
            .not_.is_("action_type", "null") \
            .gte("occurred_at", start.isoformat()) \
            .lte("occurred_at", end.isoformat()) \
            .order("occurred_at", desc=True) \
            .execute()
        
        return [self._to_event(row) for row in result.data]
    
    def mark_retracted(self, event_id: str) -> None:
        """Mark an event as retracted (soft delete - never hard delete)."""
        # Actually we insert a new record noting the retraction
        # to maintain append-only semantics
        self.client.table("events").insert({
            "statement": f"RETRACTION: Event {event_id} has been retracted",
            "tags": ["retraction"],
            "entities": [],
        }).execute()
    
    def _to_event(self, row: dict) -> Event:
        """Convert database row to Event model."""
        from src.memory.schema import SourceReference
        
        return Event(
            id=row["id"],
            statement=row["statement"],
            occurred_at=parse_iso_datetime(row["occurred_at"]) if row["occurred_at"] else None,
            sources=[SourceReference(**s) for s in (row["sources"] or [])],
            entities=row["entities"] or [],
            tags=row["tags"] or [],
            action_type=ActionType(row["action_type"]) if row["action_type"] else None,
            status=EventStatus(row["status"]) if row.get("status") else EventStatus.RAW,
            created_at=parse_iso_datetime(row["created_at"]),
            retracted=row["retracted"],
        )
