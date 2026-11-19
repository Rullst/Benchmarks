-- The session table of connect-pg-simple 10, the PostgreSQL store of
-- express-session (docs/v3-spec.md, section 2.2): the package's
-- table.sql, without its `WITH (OIDS=FALSE)`, which is the default. Created
-- here so that the server creates nothing at start-up (the store's
-- createTableIfMissing is off by default).
CREATE TABLE "session" (
  "sid" varchar NOT NULL COLLATE "default",
  "sess" json NOT NULL,
  "expire" timestamp(6) NOT NULL
);

ALTER TABLE "session" ADD CONSTRAINT "session_pkey" PRIMARY KEY ("sid") NOT DEFERRABLE INITIALLY IMMEDIATE;

CREATE INDEX "IDX_session_expire" ON "session" ("expire");
