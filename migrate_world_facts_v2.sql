-- World Facts Schema v2.0
-- Adds 2-level topic tags and proper source aggregation

-- Add new columns if not exist
ALTER TABLE world_facts 
ADD COLUMN IF NOT EXISTS source_urls TEXT[] DEFAULT '{}';

ALTER TABLE world_facts 
ADD COLUMN IF NOT EXISTS topic_l1 TEXT;

ALTER TABLE world_facts 
ADD COLUMN IF NOT EXISTS topic_l2 TEXT;

-- Create indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_facts_topic_l1 ON world_facts(topic_l1);
CREATE INDEX IF NOT EXISTS idx_facts_topic_l2 ON world_facts(topic_l2);

-- Migrate existing data: set topic_l1 based on region
UPDATE world_facts SET topic_l1 = 
    CASE 
        WHEN region = 'DOMESTIC' THEN 'DOMESTIC'
        WHEN region = 'ASIA' THEN 'TRADE'
        WHEN region = 'MENA' THEN 'MILITARY'
        WHEN region = 'EUROPE' THEN 'DIPLOMATIC'
        WHEN region = 'LATAM' THEN 'DIPLOMATIC'
        ELSE 'OTHER'
    END
WHERE topic_l1 IS NULL;

-- Set topic_l2 based on common keywords in event_summary
UPDATE world_facts SET topic_l2 = 'Korea_Tariff'
WHERE topic_l2 IS NULL AND (event_summary ILIKE '%korea%' AND event_summary ILIKE '%tariff%');

UPDATE world_facts SET topic_l2 = 'Minnesota_Incident'
WHERE topic_l2 IS NULL AND event_summary ILIKE '%minnesota%' OR event_summary ILIKE '%pretti%';

UPDATE world_facts SET topic_l2 = 'Iran_Tension'
WHERE topic_l2 IS NULL AND event_summary ILIKE '%iran%';

UPDATE world_facts SET topic_l2 = 'Indiana_Election'
WHERE topic_l2 IS NULL AND event_summary ILIKE '%indiana%';

-- Default for remaining
UPDATE world_facts SET topic_l2 = 'General'
WHERE topic_l2 IS NULL;
