-- Session persistence: save past trip planning conversations
CREATE TABLE IF NOT EXISTS travel_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id VARCHAR(32) NOT NULL UNIQUE,
    user_id VARCHAR(64) NOT NULL,
    destination VARCHAR(50) NOT NULL,
    days INT NOT NULL DEFAULT 1,
    styles JSONB NOT NULL DEFAULT '[]'::jsonb,
    itinerary JSONB,
    messages JSONB NOT NULL DEFAULT '[]'::jsonb,
    places_detail JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_travel_sessions_user_time
    ON travel_sessions (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_travel_sessions_session_id
    ON travel_sessions (session_id);
