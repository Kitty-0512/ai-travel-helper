CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS agent_trace (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id VARCHAR(64) NOT NULL,
    user_id VARCHAR(128),
    step INT NOT NULL,
    action VARCHAR(64) NOT NULL,
    tool_name VARCHAR(64),
    input JSONB NOT NULL DEFAULT '{}'::jsonb,
    output JSONB NOT NULL DEFAULT '{}'::jsonb,
    duration INT NOT NULL DEFAULT 0,
    status VARCHAR(32) NOT NULL,
    created_time TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_trace_request_id
    ON agent_trace (request_id, step);

CREATE INDEX IF NOT EXISTS idx_agent_trace_user_id_created_time
    ON agent_trace (user_id, created_time DESC);
