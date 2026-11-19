-- The session table of @nestjs/authentication's SessionStore
-- (docs/v2-phase2-spec.md, section 2.2). The package keeps sessions in memory
-- unless the application registers a store and ships no migration, so the
-- columns are its SessionRecord's (src/session.store.ts, src/auth-session.entity.ts):
-- the SHA-256 of the cookie token, the user, the absolute expiry and the last
-- activity (idle timeout), the second-factor state and the app's metadata.
-- Created here so that the server creates nothing at start-up.
CREATE TABLE auth_session (
    id text PRIMARY KEY,
    user_id text NOT NULL,
    created_at timestamptz NOT NULL,
    expires_at timestamptz NOT NULL,
    last_active_at timestamptz NOT NULL,
    mfa text,
    metadata jsonb
);

-- listUserSessions() and deleteUserSessions() ("sign out everywhere").
CREATE INDEX auth_session_user_id ON auth_session (user_id);
