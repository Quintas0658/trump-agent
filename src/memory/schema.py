"""Database schema definitions for Supabase tables."""

from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class HypothesisStatus(str, Enum):
    """Lifecycle status of a hypothesis."""
    PROPOSED = "PROPOSED"
    STRENGTHENED = "STRENGTHENED"
    WEAKENED = "WEAKENED"
    VERIFIED = "VERIFIED"
    REFUTED = "REFUTED"
    EXPIRED = "EXPIRED"


class EventStatus(str, Enum):
    """Status of an event in the grounding pipeline."""
    RAW = "RAW"           # From proactive sweep, unverified against specific signal
    VERIFIED = "VERIFIED"  # Confirmed against a specific pulse/intent
    STALE = "STALE"       # No longer relevant or refuted


class ActionType(str, Enum):
    """Types of real-world actions (for Judgment 0)."""
    RESOURCE_DEPLOYMENT = "resource_deployment"    # Military, personnel movement
    LEGAL_DOCUMENT = "legal_document"              # Executive orders, memos
    PERSONNEL_CHANGE = "personnel_change"          # Appointments, firings
    DIPLOMATIC_ACTION = "diplomatic_action"        # Official statements, sanctions
    IRREVERSIBLE_EVENT = "irreversible_event"      # Arrests, strikes


class SourceReference(BaseModel):
    """Reference to an information source."""
    source_id: str
    url: Optional[str] = None
    quote: Optional[str] = None
    reliability_rating: float = 0.5


class Event(BaseModel):
    """M-EVENT: Verified factual event (Append-Only)."""
    id: Optional[str] = None
    statement: str
    occurred_at: Optional[datetime] = None
    sources: list[SourceReference] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    action_type: Optional[ActionType] = None  # If this is a real-world action
    status: EventStatus = EventStatus.RAW
    created_at: datetime = Field(default_factory=datetime.utcnow)
    retracted: bool = False


class EntityState(BaseModel):
    """M-ENTITY: Current state of an entity (Versioned, Append-Only)."""
    id: Optional[str] = None
    entity: str
    status: str
    as_of: Optional[datetime] = None
    confidence: float = 0.5
    source_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class EvidenceRef(BaseModel):
    """Reference to supporting/refuting evidence."""
    type: str  # "event", "claim", "pattern", "inference"
    ref_id: str
    layer: str  # "L1", "L2", "L3", "L4", "L5"
    weight: float = 0.5


class Hypothesis(BaseModel):
    """M-HYPOTHESIS: System-generated inference with lifecycle."""
    id: Optional[str] = None
    statement: str
    based_on: list[EvidenceRef] = Field(default_factory=list)
    falsifiable_condition: str
    verification_deadline: Optional[datetime] = None
    status: HypothesisStatus = HypothesisStatus.PROPOSED
    support_count: int = 0
    refute_count: int = 0
    confidence: float = 0.5
    created_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None


class ClaimStatus(str, Enum):
    """Processing status of a claim pulse."""
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"


class Claim(BaseModel):
    """M-CLAIM: What someone said (stored as-is, no truth judgment)."""
    id: Optional[str] = None
    claim_text: str
    attributed_to: str
    source_url: Optional[str] = None
    claimed_at: Optional[datetime] = None
    batch_id: Optional[str] = None
    processing_status: ClaimStatus = ClaimStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.utcnow)


# SQL for Supabase setup
SUPABASE_SCHEMA = """
-- Events table (M-EVENT)
CREATE TABLE IF NOT EXISTS events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    statement TEXT NOT NULL,
    occurred_at TIMESTAMPTZ,
    sources JSONB DEFAULT '[]',
    entities TEXT[] DEFAULT '{}',
    tags TEXT[] DEFAULT '{}',
    action_type VARCHAR,
    status VARCHAR DEFAULT 'RAW',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    retracted BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_events_occurred ON events(occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_events_entities ON events USING GIN(entities);
CREATE INDEX IF NOT EXISTS idx_events_tags ON events USING GIN(tags);

-- Entity states table (M-ENTITY)
CREATE TABLE IF NOT EXISTS entity_states (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity VARCHAR NOT NULL,
    status VARCHAR NOT NULL,
    as_of TIMESTAMPTZ,
    confidence FLOAT DEFAULT 0.5,
    source_id VARCHAR,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_entity_states_entity ON entity_states(entity, created_at DESC);

-- Hypotheses table (M-HYPOTHESIS)
CREATE TABLE IF NOT EXISTS hypotheses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    statement TEXT NOT NULL,
    based_on JSONB DEFAULT '[]',
    falsifiable_condition TEXT NOT NULL,
    verification_deadline TIMESTAMPTZ,
    status VARCHAR DEFAULT 'PROPOSED',
    support_count INT DEFAULT 0,
    refute_count INT DEFAULT 0,
    confidence FLOAT DEFAULT 0.5,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    resolved_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_hypotheses_status ON hypotheses(status);
CREATE INDEX IF NOT EXISTS idx_hypotheses_deadline ON hypotheses(verification_deadline);

-- Claims table (M-CLAIM)
CREATE TABLE IF NOT EXISTS claims (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    claim_text TEXT NOT NULL,
    attributed_to VARCHAR NOT NULL,
    source_url VARCHAR,
    claimed_at TIMESTAMPTZ,
    batch_id UUID,
    processing_status VARCHAR DEFAULT 'PENDING',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_claims_attributed ON claims(attributed_to, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_claims_status ON claims(processing_status);
"""
