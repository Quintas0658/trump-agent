-- Evaluation Harness Schema
-- Tables for daily snapshots and evaluation logs

-- 1. Daily Snapshots: Frozen inputs for each day
CREATE TABLE IF NOT EXISTS daily_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_date DATE UNIQUE NOT NULL,
    posts_json JSONB NOT NULL,           -- X(t-1): Trump posts
    context_json JSONB NOT NULL,         -- Y(t-1): Context/news
    markdown_content TEXT,               -- Human-readable version
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for date lookups
CREATE INDEX IF NOT EXISTS idx_snapshots_date ON daily_snapshots(snapshot_date DESC);

-- 2. Evaluation Log: Records F, G outputs and scores
CREATE TABLE IF NOT EXISTS evaluation_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    eval_date DATE NOT NULL,
    snapshot_id UUID REFERENCES daily_snapshots(id),
    
    -- Outputs
    agent_output TEXT,                   -- F[X+Y]: Our agent's report
    baseline_output TEXT,                -- G[X+Y]: Gemini baseline (manual paste)
    ground_truth_json JSONB,             -- Y(t): Actual news next day
    
    -- Scores (JSON for flexibility)
    horizontal_scores JSONB,             -- {info_density, specificity, logic_chain, omission_rate}
    vertical_scores JSONB,               -- {prediction_hits, prediction_total, alpha_correct_pct}
    
    -- Verdict
    winner VARCHAR(10),                  -- 'F', 'G', or 'TIE'
    notes TEXT,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    scored_at TIMESTAMPTZ
);

-- Index for date lookups
CREATE INDEX IF NOT EXISTS idx_evaluation_date ON evaluation_log(eval_date DESC);
