-- Prediction Tracking System
-- 用于追踪 Agent 预测并验证准确率

-- 创建 predictions 表
CREATE TABLE IF NOT EXISTS predictions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 预测内容
    question TEXT NOT NULL,           -- "美伊会在30天内动武吗？"
    prediction TEXT NOT NULL,         -- "70%概率会动武"
    confidence INTEGER CHECK (confidence BETWEEN 1 AND 100),  -- 置信度 1-100
    reasoning TEXT,                   -- 推理依据
    
    -- 分类
    category TEXT NOT NULL CHECK (category IN ('military', 'trade', 'personnel', 'market', 'policy', 'other')),
    region TEXT,                      -- MENA | ASIA | DOMESTIC | GLOBAL
    
    -- 时间约束
    made_at DATE NOT NULL DEFAULT CURRENT_DATE,
    resolve_by DATE NOT NULL,         -- 验证截止日期
    
    -- 关联
    related_post_ids UUID[],          -- 触发预测的 trump_posts
    related_fact_ids UUID[],          -- 相关的 world_facts
    report_id UUID,                   -- 来源报告 ID (daily_reports)
    
    -- 验证结果
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'correct', 'wrong', 'cancelled', 'ambiguous')),
    resolution_notes TEXT,            -- 验证说明
    resolved_at DATE,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 索引：快速查询 pending 预测
CREATE INDEX IF NOT EXISTS idx_predictions_pending 
ON predictions(status, resolve_by) 
WHERE status = 'pending';

-- 索引：按日期查询
CREATE INDEX IF NOT EXISTS idx_predictions_made_at 
ON predictions(made_at DESC);

-- 获取预测统计的函数
CREATE OR REPLACE FUNCTION get_prediction_stats(days_back INTEGER DEFAULT 30)
RETURNS TABLE (
    total_predictions INTEGER,
    correct_count INTEGER,
    wrong_count INTEGER,
    pending_count INTEGER,
    accuracy_rate NUMERIC,
    category_stats JSONB
) AS $$
BEGIN
    RETURN QUERY
    WITH stats AS (
        SELECT 
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE status = 'correct') as correct,
            COUNT(*) FILTER (WHERE status = 'wrong') as wrong,
            COUNT(*) FILTER (WHERE status = 'pending') as pending
        FROM predictions
        WHERE made_at >= CURRENT_DATE - days_back
    ),
    cat_stats AS (
        SELECT jsonb_object_agg(
            category,
            jsonb_build_object(
                'total', cat_total,
                'correct', cat_correct,
                'accuracy', CASE WHEN cat_total > 0 THEN ROUND(cat_correct::NUMERIC / NULLIF(cat_total - cat_pending, 0) * 100, 1) ELSE 0 END
            )
        ) as by_category
        FROM (
            SELECT 
                category,
                COUNT(*) as cat_total,
                COUNT(*) FILTER (WHERE status = 'correct') as cat_correct,
                COUNT(*) FILTER (WHERE status = 'pending') as cat_pending
            FROM predictions
            WHERE made_at >= CURRENT_DATE - days_back
            GROUP BY category
        ) sub
    )
    SELECT 
        stats.total::INTEGER,
        stats.correct::INTEGER,
        stats.wrong::INTEGER,
        stats.pending::INTEGER,
        CASE WHEN stats.total - stats.pending > 0 
             THEN ROUND(stats.correct::NUMERIC / (stats.total - stats.pending) * 100, 1) 
             ELSE 0 END,
        COALESCE(cat_stats.by_category, '{}'::JSONB)
    FROM stats, cat_stats;
END;
$$ LANGUAGE plpgsql;

-- 启用 RLS
ALTER TABLE predictions ENABLE ROW LEVEL SECURITY;

-- RLS 策略
CREATE POLICY "Allow all operations for authenticated users" ON predictions
    FOR ALL USING (true) WITH CHECK (true);

-- 注释
COMMENT ON TABLE predictions IS '存储 Agent 的预测，用于追踪准确率和自我改进';
COMMENT ON COLUMN predictions.question IS '预测的问题，如"美伊会动武吗？"';
COMMENT ON COLUMN predictions.status IS 'pending=待验证, correct=正确, wrong=错误, cancelled=取消, ambiguous=模糊';
