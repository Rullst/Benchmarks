-- The session records Topcoat's `session` feature leaves to the application
-- (docs/v3-spec.md, section 2.2): Topcoat issues the token and hands
-- back its SHA-256 hash and expiry; the app stores them with the user id and
-- reads them through Toasty (`UserSession` in src/browser.rs). Written here so
-- that the server creates nothing at start-up. The harness applies this file
-- once per job and empties the table at the start of every round.
CREATE TABLE user_sessions (
    token_hash text PRIMARY KEY,
    user_id integer NOT NULL,
    expires_at bigint NOT NULL
);
