-- Schema and data shared by every implementation. The /db-single endpoint
-- reads the row with id = 1 on every request; the conformance check changes
-- its randomnumber to prove the value is read from the database each time.
CREATE TABLE world (
    id integer PRIMARY KEY,
    randomnumber integer NOT NULL
);

INSERT INTO world (id, randomnumber)
SELECT i, 1 + (i * 7919) % 10000
FROM generate_series(1, 10000) AS i;

ANALYZE world;
