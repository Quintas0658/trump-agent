-- Trump Policy Analysis Agent - Database Schema
-- Run this in your Supabase SQL Editor

-- 1. M-EVENT: Verified real-world actions
CREATE TABLE IF NOT EXISTS events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    statement TEXT NOT NULL,
    occurred_at TIMESTAMPTZ,
    sources JSONB DEFAULT '[]',   -- [{source_id, url, quote}]
    entities TEXT[] DEFAULT '{}',  -- ["Trump", "Mexico"]
    tags TEXT[] DEFAULT '{}',      -- ["trade", "tariff"]
    action_type VARCHAR,           -- deployment, legal, personnel
    status VARCHAR DEFAULT 'RAW',  -- RAW (from sweep), VERIFIED (from pulse)
    created_at TIMESTAMPTZ DEFAULT NOW(),
    retracted BOOLEAN DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_events_occurred ON events(occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_events_entities ON events USING GIN(entities);
CREATE INDEX IF NOT EXISTS idx_events_status ON events(status);

-- 2. M-ENTITY: Versioned entity states
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

-- 3. M-HYPOTHESIS: System inferences and predictions
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

-- 4. M-CLAIM: Raw attributed statements (unverified)
CREATE TABLE IF NOT EXISTS claims (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    claim_text TEXT NOT NULL,
    attributed_to VARCHAR NOT NULL,
    source_url VARCHAR,
    claimed_at TIMESTAMPTZ,
    batch_id UUID,                -- For grouping pulses
    processing_status VARCHAR DEFAULT 'PENDING', -- PENDING, PROCESSING, COMPLETED
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_claims_attributed ON claims(attributed_to, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_claims_status ON claims(processing_status);

-- 5. TRUMP_POSTS: Raw posts from Truth Social (for memory persistence)
CREATE TABLE IF NOT EXISTS trump_posts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    post_id VARCHAR UNIQUE NOT NULL,       -- Apify's original ID
    text TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    fetched_at TIMESTAMPTZ DEFAULT NOW(),
    media_urls JSONB DEFAULT '[]',
    entities TEXT[] DEFAULT '{}'           -- Extracted entities
);

CREATE INDEX IF NOT EXISTS idx_posts_created ON trump_posts(created_at DESC);

-- 6. DAILY_REPORTS: Strategic analysis reports (for cross-day continuity)
CREATE TABLE IF NOT EXISTS daily_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_date DATE UNIQUE NOT NULL,
    report_content TEXT NOT NULL,
    key_hypotheses JSONB DEFAULT '[]',     -- [{hypothesis, confidence, deadline}]
    key_entities TEXT[] DEFAULT '{}',
    summary TEXT,                          -- 1-2 sentence summary for quick recall
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_reports_date ON daily_reports(report_date DESC);
