-- The session registry's table (docs/v3-spec.md, section 2.2): the
-- PostgreSQL schema that `cargo rullst auth`'s
-- `*_create_rullst_auth_sessions_table` migration creates through
-- `SessionRegistry::create_table` (rullst-auth 13.0.0-alpha.6,
-- `session_registry/postgres.rs`), written here so that the server creates
-- nothing at start-up (it only `connect`s). The harness applies this file once
-- per job and empties the table at the start of every round.
CREATE TABLE IF NOT EXISTS rullst_auth_sessions (
    token_hash TEXT PRIMARY KEY NOT NULL CHECK (length(token_hash) = 64),
    public_id TEXT NOT NULL CHECK (length(public_id) = 22),
    user_id INTEGER NOT NULL,
    created_at BIGINT NOT NULL,
    last_seen_at BIGINT NOT NULL,
    expires_at BIGINT NOT NULL,
    browser TEXT NOT NULL,
    platform TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS rullst_auth_sessions_user ON rullst_auth_sessions (user_id, last_seen_at);
CREATE INDEX IF NOT EXISTS rullst_auth_sessions_expiry ON rullst_auth_sessions (expires_at);
