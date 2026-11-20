-- The users_tokens table of `mix phx.gen.auth` (Phoenix 1.8): the SQL its
-- migration (create table(:users_tokens) with user_id references(:users,
-- on_delete: :delete_all), token, context, sent_to, authenticated_at and
-- inserted_at, and its two indexes) runs on PostgreSQL. The generated
-- migration also creates the users table; the shared users table
-- (bench/db/phase2.sql) is used instead. The harness applies this file once
-- per job and empties the table at the start of every round
-- (docs/v3-spec.md, section 2.2); the server creates nothing at
-- start-up.
CREATE TABLE "users_tokens" (
    "id" bigserial,
    "user_id" bigint NOT NULL CONSTRAINT "users_tokens_user_id_fkey" REFERENCES "users"("id") ON DELETE CASCADE,
    "token" bytea NOT NULL,
    "context" varchar(255) NOT NULL,
    "sent_to" varchar(255),
    "authenticated_at" timestamp(0),
    "inserted_at" timestamp(0) NOT NULL,
    PRIMARY KEY ("id")
);
CREATE INDEX "users_tokens_user_id_index" ON "users_tokens" ("user_id");
CREATE UNIQUE INDEX "users_tokens_context_token_index" ON "users_tokens" ("context", "token");
