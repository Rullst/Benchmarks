-- Tables Axum's session store uses (docs/v3-spec.md, section 2.2): the
-- schema and table that tower-sessions-sqlx-store 0.16's
-- PostgresStore::migrate() creates, written here so that the server creates
-- nothing at start-up. The harness applies this file once per job and empties
-- the tables it creates at the start of every round.
CREATE SCHEMA IF NOT EXISTS "tower_sessions";

CREATE TABLE "tower_sessions"."session" (
    id text PRIMARY KEY NOT NULL,
    data bytea NOT NULL,
    expiry_date timestamptz NOT NULL
);
