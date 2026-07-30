-- Agent Memory: long-term user travel preferences
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS user_memory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(64) NOT NULL,
    memory_type VARCHAR(32) NOT NULL,
    content TEXT NOT NULL,
    structured JSONB NOT NULL DEFAULT '{}'::jsonb,
    embedding vector(1536),
    source_session_id VARCHAR(32),
    created_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_user_memory_user_active
    ON user_memory (user_id, is_active);

CREATE INDEX IF NOT EXISTS idx_user_memory_structured
    ON user_memory USING GIN (structured);

-- HNSW requires rows; create after some data exists is fine, but init-time is OK for empty table
CREATE INDEX IF NOT EXISTS idx_user_memory_embedding
    ON user_memory USING hnsw (embedding vector_cosine_ops);
