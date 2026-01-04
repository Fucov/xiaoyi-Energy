-- 启用 pgvector 扩展
CREATE EXTENSION IF NOT EXISTS vector;

-- 研报主表
CREATE TABLE IF NOT EXISTS reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_id VARCHAR(50) UNIQUE,
    publish_date DATE NOT NULL,
    institution VARCHAR(100),
    analyst_name VARCHAR(50),
    title TEXT NOT NULL,
    report_type VARCHAR(30),
    category VARCHAR(50),
    abstract TEXT,
    key_points TEXT[],
    source_url TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 研报-股票关联表
CREATE TABLE IF NOT EXISTS report_stocks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_id UUID REFERENCES reports(id) ON DELETE CASCADE,
    stock_code VARCHAR(20) NOT NULL,
    stock_name VARCHAR(50),
    rating VARCHAR(20),
    rating_prev VARCHAR(20),
    target_price DECIMAL(10,2),
    current_price DECIMAL(10,2),
    eps_current DECIMAL(10,4),
    eps_next DECIMAL(10,4),
    created_at TIMESTAMP DEFAULT NOW()
);

-- 研报分块表（用于向量检索）
CREATE TABLE IF NOT EXISTS report_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_id UUID REFERENCES reports(id) ON DELETE CASCADE,
    chunk_index INTEGER,
    content TEXT NOT NULL,
    embedding vector(1536),
    created_at TIMESTAMP DEFAULT NOW()
);

-- 对话历史表
CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(200),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 对话消息表
CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL, -- user / assistant / system
    content TEXT NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_reports_publish_date ON reports(publish_date);
CREATE INDEX IF NOT EXISTS idx_reports_institution ON reports(institution);
CREATE INDEX IF NOT EXISTS idx_report_stocks_code ON report_stocks(stock_code);
CREATE INDEX IF NOT EXISTS idx_report_stocks_rating ON report_stocks(rating);
CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id);

-- 向量索引（用于相似度搜索）
CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON report_chunks 
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- 输出初始化完成信息
DO $$
BEGIN
    RAISE NOTICE '✅ 小易猜猜数据库初始化完成！';
END $$;
