-- ============================================================
-- AI-Screening Enginee — Supabase PostgreSQL Schema
-- Run this in: Supabase Dashboard → SQL Editor → New Query
-- ============================================================

-- 1. Users Table (Registration)
CREATE TABLE IF NOT EXISTS users (
    username        TEXT PRIMARY KEY,
    password_hash   TEXT NOT NULL,
    salt            TEXT NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Sessions Table (Login tokens)
CREATE TABLE IF NOT EXISTS sessions (
    token       TEXT PRIMARY KEY,
    username    TEXT NOT NULL REFERENCES users(username) ON DELETE CASCADE,
    expires_at  TIMESTAMPTZ NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Index for fast session lookup
CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token);
CREATE INDEX IF NOT EXISTS idx_sessions_username ON sessions(username);

-- 3. User Activity Tracking Table
CREATE TABLE IF NOT EXISTS user_activity (
    id          BIGSERIAL PRIMARY KEY,
    username    TEXT NOT NULL REFERENCES users(username) ON DELETE CASCADE,
    action      TEXT NOT NULL,        -- 'register', 'login', 'logout', 'rank_candidates', etc.
    role_id     TEXT DEFAULT 'default',
    metadata    JSONB DEFAULT '{}',   -- Extra info (IP, device, etc.)
    timestamp   TIMESTAMPTZ DEFAULT NOW()
);

-- Index for fast user activity lookup
CREATE INDEX IF NOT EXISTS idx_activity_username ON user_activity(username);
CREATE INDEX IF NOT EXISTS idx_activity_action ON user_activity(action);
CREATE INDEX IF NOT EXISTS idx_activity_timestamp ON user_activity(timestamp DESC);

-- ─── Row Level Security (RLS) ───────────────────────────────
-- Allow backend (service_role key) full access
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_activity ENABLE ROW LEVEL SECURITY;

-- Service role bypass (backend has full access)
CREATE POLICY "service_role_users" ON users FOR ALL USING (true);
CREATE POLICY "service_role_sessions" ON sessions FOR ALL USING (true);
CREATE POLICY "service_role_activity" ON user_activity FOR ALL USING (true);
