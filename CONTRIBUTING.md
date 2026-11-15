# Contributing

Contributions are welcome, especially from people who run one of the measured
frameworks in production and know how its community deploys it. If an
implementation does not follow its framework's production guidance, please
open an issue or a pull request with the change and a link to that guidance.

## Adding or changing a framework

Each implementation is one folder under `frameworks/`:

```text
frameworks/<name>/
  bench.json    manifest (below)
  Dockerfile    builds and runs the production server
  README.md     how it is configured and why
  ...           application code and lockfile
```

### Endpoints

The server listens on `0.0.0.0:$PORT` and answers `GET` on:

| Endpoint | Status and media type | Body |
| --- | --- | --- |
| `/text` | 200, `text/plain` | `Hello World` (byte-identical) |
| `/json` | 200, `application/json` | `{"message":"Hello World"}` |
| `/db-single` | 200, `application/json` | `{"id":1,"randomNumber":N}`, where N is the current `randomnumber` of the row with `id = 1` in the `world` table |
| `/html` | 200, `text/html` | `<!DOCTYPE html><html><head><title>Benchmark</title></head><body><h1>Hello World</h1></body></html>` |

Equivalence rules, checked by `bench/conformance.py`:

- the media type must match; a `charset` parameter, if present, must be UTF-8;
- JSON bodies are compared as parsed values, so key order and whitespace may
  differ;
- the HTML body is compared byte for byte after trailing whitespace is removed
  (template files usually end with a newline);
- `/db-single` must query the database on every request: the check changes
  the row between requests and the response must follow. Do not cache it;
- several requests on one HTTP/1.1 keep-alive connection must work.

The `world` table is `world(id integer primary key, randomnumber integer not
null)` ([bench/db/init.sql](bench/db/init.sql)).

### Environment

The harness starts the container with the host network, 2 vCPUs and 2 GiB of
RAM, and sets:

| Variable | Value |
| --- | --- |
| `PORT` | `8080` |
| `DATABASE_URL` | `postgres://bench:bench@127.0.0.1:5432/bench` |
| `DB_POOL_SIZE` | `16`: the total number of database connections for the server; divide it across processes if the server runs several |
| `BENCH_WORKERS` | `2`: the number of vCPUs the server has |

Use the framework's own production recommendations for everything else:

- a release or production build, with versions pinned and a lockfile
  committed (base images pinned to an exact version);
- the framework's standard database layer (its ORM where it has one) and its
  standard template engine;
- its documented production server and worker settings, sized for 2 vCPUs;
- logging off, or at the framework's production default if it cannot be
  turned off (say so in the README);
- no response caching, no endpoint-specific tricks, and no tuning that the
  framework's documentation would not recommend to its users.

The Dockerfile may write `name version` lines to `/bench/versions.txt` in the
image; the results then show the resolved versions instead of the manifest's.

### bench.json

```json
{
  "name": "Actix Web",
  "language": "Rust",
  "group": "rust",
  "framework": "actix-web",
  "framework_version": "4.19.0",
  "version_package": "actix-web",
  "runtime": "Rust 1.99.1 (release build, thin LTO)",
  "server": "actix-web HttpServer",
  "workers": "Default: one worker per available CPU (2)",
  "database_layer": "SQLx 0.9 (Actix Web has no ORM)",
  "template_engine": "Askama 0.16",
  "logging": "none",
  "startup_timeout_s": 120
}
```

`group` is `rust`, `full-stack` or `reference`. Optional fields: `variant`
(a label when a framework has more than one implementation), `env` (extra
environment variables for the container), `build_args_from_env` (environment
variables passed to `docker build` as build arguments, such as
`RULLST_VERSION`), `maturity_note` (shown with the results, for example for
an early 0.x framework) and `notes`.

### Checking your folder

```sh
python3 bench/harness.py validate
python3 bench/harness.py conformance --framework <name>
```

`conformance` builds the image, starts PostgreSQL and prints the result of
every check. Pull requests run the same check for every changed framework
folder. A maintainer can add the `benchmark-trial` label to a pull request
to run a one-round measurement of the changed frameworks.

Add the folder to the implementations table in the README.

## Changing the harness

The harness is Python (standard library only) under `bench/`. Run the unit
tests with `python3 -m unittest discover -s bench/tests`. Changes to the
method (tiers, limits, metrics) should update the README's method section in
the same pull request.

Do not edit `benchmarks_results.md`, the README's results table or the files
under `results/` by hand: `bench/aggregate.py` generates them.

## Shared runners

The Rullst organization shares one pool of GitHub-hosted runners between
Rullst/Rullst and this repository, so long benchmark runs can delay Rullst's
pull request checks and releases:

- measurements use at most 3 runners at a time and Linux runners only (no
  macOS runners);
- one measurement runs at a time; a new trigger waits instead of cancelling
  a running one;
- scheduled and manual runs do not start while Rullst/Rullst runs a release,
  its release admission or a long verification workflow (fuzzing, Kani, Miri,
  sanitizers, property tests, DAST), or while more than 10 of its jobs are
  queued (`bench/yield_check.py`); a manual run can override this with the
  `force` input;
- run full measurements at night or at weekends (UTC-3) when possible; the
  nightly schedule starts at 01:00 UTC-3.

## Commits

Use [Conventional Commits](https://www.conventionalcommits.org/)
(`feat(fastapi): ...`, `fix(harness): ...`), with short, technical messages.
