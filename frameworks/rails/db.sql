-- The sessions table of `bin/rails generate authentication` (Rails 8.1): the
-- SQL its migration (create_table :sessions with t.references :user,
-- foreign_key: true, ip_address, user_agent and timestamps) runs on
-- PostgreSQL. The harness applies this file once per job and empties the
-- table at the start of every round (docs/v3-spec.md, section 2.2);
-- the server creates nothing at start-up.
CREATE TABLE "sessions" (
    "id" bigserial PRIMARY KEY,
    "user_id" bigint NOT NULL,
    "ip_address" character varying,
    "user_agent" character varying,
    "created_at" timestamp(6) NOT NULL,
    "updated_at" timestamp(6) NOT NULL,
    CONSTRAINT "fk_rails_758836b4f0" FOREIGN KEY ("user_id") REFERENCES "users" ("id")
);

CREATE INDEX "index_sessions_on_user_id" ON "sessions" ("user_id");
