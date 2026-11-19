-- Phase 2 (docs/v3-spec.md): the accounts that POST /login signs in
-- and GET /me returns. Loaded after init.sql (the entrypoint runs the files of
-- bench/db in name order). Every account has the password "bench-password".
--
-- The same password is stored twice, so that each implementation can verify
-- it with its framework's standard hasher (login is not timed):
--   password_bcrypt    bcrypt, cost 10, "$2b$" prefix ("$2y$" for PHP,
--                      "{bcrypt}" + hash for Spring's DelegatingPasswordEncoder,
--                      "bcrypt$" + hash for Django's BCryptPasswordHasher)
--   password_argon2id  Argon2id PHC string, m=19456 KiB, t=2, p=1 ("argon2" +
--                      hash for Django's Argon2PasswordHasher)
-- One salt for every row: this is test data, not a password store.
CREATE TABLE users (
    id integer PRIMARY KEY,
    username varchar(64) NOT NULL UNIQUE,
    display_name varchar(128) NOT NULL,
    password_bcrypt varchar(60) NOT NULL,
    password_argon2id varchar(128) NOT NULL
);

INSERT INTO users (id, username, display_name, password_bcrypt, password_argon2id)
SELECT i, 'user' || i, 'User ' || i,
       '$2b$10$KIGY8KzqKXbBh/rmPdxcyO.mmg1KeFoutObsrA1/IOw6zV2LbHByK',
       '$argon2id$v=19$m=19456,t=2,p=1$WNtlfcc3BPbFivhPPWjIBw$69So9YIBDSFyqaIdsQ9S/EcNzbQinxZCpmjHlyIc/iA'
FROM generate_series(1, 1000) AS i;

ANALYZE users;
