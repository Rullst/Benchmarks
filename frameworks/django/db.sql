-- The table of Django's database session backend (django.contrib.sessions,
-- SESSION_ENGINE's default): the output of
-- `manage.py sqlmigrate sessions 0001` for PostgreSQL, without its
-- BEGIN/COMMIT. The harness applies this file once per job and empties the
-- table at the start of every round (docs/v3-spec.md, section 2.2);
-- the server creates nothing at start-up.
CREATE TABLE "django_session" (
    "session_key" varchar(40) NOT NULL PRIMARY KEY,
    "session_data" text NOT NULL,
    "expire_date" timestamp with time zone NOT NULL
);
CREATE INDEX "django_session_session_key_c0390e0f_like" ON "django_session" ("session_key" varchar_pattern_ops);
CREATE INDEX "django_session_expire_date_a5c62663" ON "django_session" ("expire_date");
