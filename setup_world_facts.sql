-- World Facts Table: Historical events for Agent context
-- Run this in Supabase SQL Editor after setup_supabase.sql

-- WORLD_FACTS: Global events timeline for Agent memory
CREATE TABLE IF NOT EXISTS world_facts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_date DATE NOT NULL,                    -- When it happened
    event_summary TEXT NOT NULL,                 -- Brief factual description
    actors TEXT[] DEFAULT '{}',                  -- ["Trump", "Iran", "Maduro"]
    location VARCHAR,                            -- Where it happened
    event_type VARCHAR NOT NULL,                 -- military_action, sanction, tariff, diplomacy, protest, policy
    region VARCHAR,                              -- MENA, LATAM, EUROPE, ASIA, DOMESTIC
    source_urls TEXT[] DEFAULT '{}',             -- Evidence links
    verified BOOLEAN DEFAULT FALSE,              -- Has this been fact-checked?
    significance VARCHAR DEFAULT 'MEDIUM',       -- LOW, MEDIUM, HIGH, CRITICAL
    created_at TIMESTAMPTZ DEFAULT NOW(),
    notes TEXT                                   -- Optional analyst notes
);

CREATE INDEX IF NOT EXISTS idx_facts_date ON world_facts(event_date DESC);
CREATE INDEX IF NOT EXISTS idx_facts_type ON world_facts(event_type);
CREATE INDEX IF NOT EXISTS idx_facts_region ON world_facts(region);
CREATE INDEX IF NOT EXISTS idx_facts_actors ON world_facts USING GIN(actors);

-- Initial Data: January 2026 World Events

-- IRAN
INSERT INTO world_facts (event_date, event_summary, actors, location, event_type, region, significance, verified) VALUES
('2026-01-01', 'Iran nationwide protests erupt over economic crisis, government begins violent crackdown', ARRAY['Iran', 'Khamenei'], 'Iran', 'protest', 'MENA', 'CRITICAL', true),
('2026-01-23', 'Trump announces US naval armada (USS Abraham Lincoln) sailing to Middle East', ARRAY['Trump', 'Iran', 'US Navy'], 'Middle East', 'military_action', 'MENA', 'CRITICAL', true),
('2026-01-23', 'US Treasury (OFAC) sanctions 9 Iranian oil "shadow fleet" vessels', ARRAY['US Treasury', 'Iran'], 'Global', 'sanction', 'MENA', 'HIGH', true),
('2026-01-23', 'Iran Supreme Leader Khamenei reportedly relocates to underground shelter', ARRAY['Khamenei', 'Iran'], 'Iran', 'policy', 'MENA', 'HIGH', false);

-- VENEZUELA
INSERT INTO world_facts (event_date, event_summary, actors, location, event_type, region, significance, verified) VALUES
('2026-01-03', 'US launches "Operation Absolute Resolve" - captures Venezuelan President Maduro', ARRAY['Trump', 'Maduro', 'US Military'], 'Venezuela', 'military_action', 'LATAM', 'CRITICAL', true),
('2026-01-04', 'Delcy Rodriguez sworn in as Venezuela acting president after Maduro capture', ARRAY['Rodriguez', 'Venezuela'], 'Venezuela', 'policy', 'LATAM', 'HIGH', true),
('2026-01-04', 'Secretary Rubio says US will not recognize Rodriguez presidency', ARRAY['Rubio', 'Rodriguez', 'Venezuela'], 'Washington DC', 'diplomacy', 'LATAM', 'HIGH', true),
('2026-01-09', 'US delegation visits Venezuela to assess reopening of US Embassy in Caracas', ARRAY['US State Department', 'Venezuela'], 'Caracas', 'diplomacy', 'LATAM', 'MEDIUM', true);

-- TARIFFS & TRADE
INSERT INTO world_facts (event_date, event_summary, actors, location, event_type, region, significance, verified) VALUES
('2026-01-14', 'US imposes 25% tariff on semiconductors (national security)', ARRAY['Trump', 'US Commerce'], 'USA', 'tariff', 'DOMESTIC', 'HIGH', true),
('2026-01-21', 'Trump withdraws tariff threat on 8 European countries after Greenland framework deal with NATO', ARRAY['Trump', 'NATO', 'Rutte', 'Denmark'], 'Europe', 'diplomacy', 'EUROPE', 'HIGH', true),
('2026-01-24', 'Trump threatens 100% tariff on Canada if it signs trade deal with China', ARRAY['Trump', 'Canada', 'China'], 'USA', 'tariff', 'ASIA', 'HIGH', true),
('2026-01-01', 'US average effective tariff rate reaches 17.5% (highest since 1932)', ARRAY['US Commerce', 'Trump'], 'USA', 'tariff', 'DOMESTIC', 'CRITICAL', true);

-- INTERNATIONAL ORGANIZATIONS
INSERT INTO world_facts (event_date, event_summary, actors, location, event_type, region, significance, verified) VALUES
('2026-01-07', 'Trump orders US withdrawal from 66 international organizations (35 non-UN + 31 UN entities)', ARRAY['Trump', 'UN', 'WHO'], 'Washington DC', 'policy', 'GLOBAL', 'CRITICAL', true),
('2026-01-07', 'US formally withdraws from WHO', ARRAY['Trump', 'WHO'], 'Geneva', 'policy', 'GLOBAL', 'CRITICAL', true),
('2026-01-07', 'US withdraws from Paris Climate Agreement', ARRAY['Trump'], 'USA', 'policy', 'GLOBAL', 'HIGH', true),
('2026-01-07', 'US declares OECD Global Tax Deal has no force in the US', ARRAY['Trump', 'OECD'], 'USA', 'policy', 'GLOBAL', 'HIGH', true);

-- RUSSIA
INSERT INTO world_facts (event_date, event_summary, actors, location, event_type, region, significance, verified) VALUES
('2026-01-07', 'Trump approves "Sanctioning Russia Act of 2025" - secondary sanctions on Russian oil buyers', ARRAY['Trump', 'Graham', 'Russia'], 'Washington DC', 'sanction', 'EUROPE', 'HIGH', true);

-- GAZA
INSERT INTO world_facts (event_date, event_summary, actors, location, event_type, region, significance, verified) VALUES
('2026-01-21', 'US Treasury (OFAC) designates 6 Gaza-based organizations for supporting Hamas', ARRAY['US Treasury', 'Hamas', 'Gaza'], 'Gaza', 'sanction', 'MENA', 'MEDIUM', true),
('2026-01-23', 'Trump announces "Board of Peace" at Davos for Gaza conflict resolution', ARRAY['Trump', 'WEF'], 'Davos', 'diplomacy', 'MENA', 'MEDIUM', true);

-- DOMESTIC
INSERT INTO world_facts (event_date, event_summary, actors, location, event_type, region, significance, verified) VALUES
('2026-01-24', 'US-Mexico Security Implementation Group formed to combat fentanyl crisis', ARRAY['Trump', 'Mexico'], 'Washington DC', 'diplomacy', 'LATAM', 'MEDIUM', true);
