-- Schema and data shared by every implementation.
--
-- world: 10,000 rows. /db-single reads the row with id = 1 on every request
-- (the conformance check changes its randomnumber to prove the value is read
-- from the database each time); /queries and /updates read random rows, and
-- /updates writes them back.
CREATE TABLE world (
    id integer PRIMARY KEY,
    randomnumber integer NOT NULL
);

INSERT INTO world (id, randomnumber)
SELECT i, 1 + (i * 7919) % 10000
FROM generate_series(1, 10000) AS i;

-- fortune: the twelve rows of the TechEmpower Framework Benchmarks fortunes
-- test, including a <script> message that must be escaped and one in Japanese.
CREATE TABLE fortune (
    id integer PRIMARY KEY,
    message varchar(2048) NOT NULL
);

INSERT INTO fortune (id, message) VALUES
    (1, 'fortune: No such file or directory'),
    (2, 'A computer scientist is someone who fixes things that aren''t broken.'),
    (3, 'After enough decimal places, nobody gives a damn.'),
    (4, 'A bad random number generator: 1, 1, 1, 1, 1, 4.33e+67, 1, 1, 1'),
    (5, 'A computer program does what you tell it to do, not what you want it to do.'),
    (6, 'Emacs is a nice operating system, but I prefer UNIX. — Tom Christaensen'),
    (7, 'Any program that runs right is obsolete.'),
    (8, 'A list is only as strong as its weakest link. — Donald Knuth'),
    (9, 'Feature: A bug with seniority.'),
    (10, 'Computers make very fast, very accurate mistakes.'),
    (11, '<script>alert("This should not be displayed in a browser alert box.");</script>'),
    (12, 'フレームワークのベンチマーク');

ANALYZE world;
ANALYZE fortune;

-- Query statistics for the conformance check (each row of /queries and
-- /updates read by its own query, /fortunes read from the database on every
-- request). The harness turns statement tracking off before measuring.
CREATE EXTENSION pg_stat_statements;
