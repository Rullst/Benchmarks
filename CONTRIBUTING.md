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
  README.md     how it is configured and why, with a "Production settings"
                section: each setting (logging, pool, prepared statements,
                middleware, server and workers) with the documentation it
                follows
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
| `/queries?queries=N` | 200, `application/json` | a JSON array of N `{"id":…,"randomNumber":…}` rows of `world`, ids random in 1-10,000 |
| `/updates?queries=N` | 200, `application/json` | the same, after giving each row a new random `randomNumber` (1-10,000) and writing it to the database |
| `/fortunes` | 200, `text/html; charset=utf-8` | the HTML table below |

`/queries`, `/updates` and `/fortunes` follow the TechEmpower Framework
Benchmarks round 23 [test requirements](https://github.com/TechEmpower/FrameworkBenchmarks/wiki/Project-Information-Framework-Tests-Overview)
(tests 3, 4 and 5), with the suite's own conformance check:

- `queries`: an integer clamped to 1-500; missing, empty, non-numeric or
  below 1 counts as 1, above 500 as 500.
- `/queries`: read each row with its own query through the framework's
  database layer (no `WHERE id IN (...)`, no `ANY`, no single query for
  several rows, no caching). Pipelining separate statements is allowed.
- `/updates`: read each row with its own query (as for `/queries`), set a new
  random `randomNumber` and write every row to the database before
  responding. Writing them with one statement per row, in a batch or in a
  transaction is allowed; say in the folder README what the implementation
  does. Return the rows with their new values.
- `/fortunes`: read every row of `fortune` (no `ORDER BY`, no caching), add
  a fortune with id 0 and the message `Additional fortune added at request
  time.`, sort by message (code point order) and render this document with
  the framework's template engine, which must escape the messages:

  ```html
  <!DOCTYPE html><html><head><title>Fortunes</title></head><body><table><tr><th>id</th><th>message</th></tr><tr><td>11</td><td>&lt;script&gt;alert(&quot;This should not be displayed in a browser alert box.&quot;);&lt;/script&gt;</td></tr><tr><td>4</td><td>A bad random number generator: 1, 1, 1, 1, 1, 4.33e+67, 1, 1, 1</td></tr> … <tr><td>12</td><td>フレームワークのベンチマーク</td></tr></table></body></html>
  ```

  The full expected document is `FORTUNES_HTML` in
  [bench/conformance.py](bench/conformance.py).

Equivalence rules, checked by `bench/conformance.py`:

- the media type must match; a `charset` parameter, if present, must be UTF-8
  (`/fortunes` must declare `charset=utf-8`);
- JSON bodies are compared as parsed values, so key order and whitespace may
  differ;
- the HTML body is compared byte for byte after trailing whitespace is removed
  (template files usually end with a newline);
- `/db-single` must query the database on every request: the check changes
  the row between requests and the response must follow. Do not cache it;
- `/queries` and `/updates` are checked with `queries` missing, empty, `foo`,
  `0`, `-3`, `1`, `20`, `500` and `501`: the row count, the shape of every
  row, and that each value is the one in the database (for `/updates`, after
  the request; rows that were not returned must not change; a row id that
  comes twice in one response may end with either value). At least 90% of
  the rows `/updates` returns must have a new value in the database, and
  `queries=500` must return at least 400 different rows;
- `pg_stat_statements` counts the statements each request runs: at least N
  `SELECT`s on `world` for `/queries` and `/updates`, `UPDATE`s that change
  at least as many rows as the response has different ids whose value
  changed (an ORM that tracks changes may skip a row whose new random value
  equals the old one), and at least one
  `SELECT` of the 12 fortunes without `ORDER BY` for every `/fortunes`
  request;
- the `/fortunes` body is compared as parsed HTML with the expected document:
  the same doctype, elements (without attributes) and text, in the same
  order. Whitespace between elements and at the ends of a text may differ,
  and character references are decoded first, so `&#39;`, `&#x27;` and
  `&apos;` (or a plain `'`) are equal, as in TechEmpower's checker. An
  unescaped `<script>` parses as an element and fails;
- several requests on one HTTP/1.1 keep-alive connection must work.

The tables are `world(id integer primary key, randomnumber integer not
null)` and `fortune(id integer primary key, message varchar(2048) not null)`
([bench/db/init.sql](bench/db/init.sql)).

### Phase-2 endpoints

The contract of the five application endpoints is
[docs/v3-spec.md](docs/v3-spec.md) (sections 2-6; section 10
is the per-framework checklist and section 9 the expected mechanism for
each framework). In short:

| Name (bench.json) | Requests | Answer |
| --- | --- | --- |
| `world` | `GET /world/{id}` | `{"id":…,"randomNumber":…}`, `application/json`, read by primary key on every request; 404 without a row; 400, 404 or 422 for a non-integer id |
| `worlds` | `GET /worlds?min=&max=&limit=&page=` | a JSON array of the rows `min..max` ordered by id, page `page` of `limit` rows, in one query; defaults 1, 10000, 20, 1; ranges 1-10000, 1-100, 1-1000 and `min <= max`, otherwise 400 or 422; unknown parameters ignored |
| `world-update` | `PUT /world/{id}`, `{"randomNumber": n}` | the row as stored after setting `randomnumber` (1-10000) the ORM's usual way (or one `UPDATE … RETURNING`); malformed JSON, a missing, non-integer (a JSON string such as `"5"` included) or out-of-range value: 400 or 422 and nothing written; 404 without a row. No cookies are sent: exempt the route from a global CSRF check the documented way |
| `form` | `GET /form`, then `POST /form` (urlencoded `name`, `randomNumber` and the CSRF field) | `GET`: a page with `<form method="post" action="/form">`, inputs `name` and `randomNumber` and the framework's hidden CSRF field; `POST`: `<!DOCTYPE html><html><head><title>Form</title></head><body><h1>Hello, {name}</h1><p>{randomNumber}</p></body></html>`, the name escaped, `text/html; charset=utf-8`; a forged post: 400, 403, 419 or 422; invalid fields: 200, 302, 303, 400 or 422, never the success page |
| `me` | `GET /login`, `POST /login` (urlencoded `username`, `password`, the hidden fields), then `GET /me` | login: 200, 204, 302 or 303 and session cookies (wrong password: 200, 302, 303, 400, 401 or 422 and no session); `/me`: `{"id":…,"username":…,"displayName":…}` with the user's row read on every request; without a session 401, 403, 302 or 303 |

The harness behaves like a browser: it keeps every cookie a response sets
(attributes such as `Secure`, `Path` and the `__Host-` prefix are ignored:
it talks plain HTTP to 127.0.0.1), submits every hidden field of the first
form whose action is the page's path (or empty), and sends `Origin:
http://127.0.0.1:8080` and `Sec-Fetch-Site: same-origin` with every form
post. One session's cookies and hidden fields must stay valid for many posts
and requests: the load replays them. Accounts: `user1`..`user1000` in
`users(id, username, display_name, password_bcrypt, password_argon2id)`,
password `bench-password` ([bench/db/phase2.sql](bench/db/phase2.sql); the
file's comment gives the hash prefixes each framework's hasher expects).

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

The rule is the same for every folder, the Rullst ones included. Where the
documentation recommends nothing, keep the framework's (or the driver's)
default, even when another setting would be faster, and say so in the
README. List every setting you checked in the README's "Production settings"
section with a link to the documentation it follows.

The Dockerfile may write `name version` lines to `/bench/versions.txt` in the
image; the results then show the resolved versions instead of the manifest's.

If you cannot run the ecosystem's dependency resolver locally, give the
Dockerfile a stage named `lockfile` (`FROM ... AS lockfile`) that resolves the
dependencies and ends with the lockfile at `/` (for example
`FROM scratch AS lockfile` + `COPY --from=resolve /app/Gemfile.lock /`). The
pull request check builds that stage and uploads its output as the
`lockfile-<name>` artifact; commit the file it contains. The image itself
must build from the committed lockfile.

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
  "endpoints": ["text", "json", "db-single", "html", "queries", "updates", "fortunes",
                "world", "worlds", "world-update", "form", "me"],
  "db_setup": "db.sql",
  "phase2": {
    "validation": "web::Path, web::Query, web::Json and web::Form; ranges checked by hand",
    "csrf": {"design": "token", "mechanism": "actix-csrf 0.8 (double-submit cookie)", "source": "library"},
    "session": {"store": "cookie-encrypted", "mechanism": "actix-session CookieSessionStore", "source": "documented"},
    "write_csrf": null
  },
  "startup_timeout_s": 120
}
```

`group` is `rust`, `full-stack` or `reference`. Optional fields: `endpoints`
(the endpoints the folder serves: `text`, `json`, `db-single` and `html`,
plus any of `queries`, `updates`, `fortunes`, `world`, `worlds`,
`world-update`, `form` and `me`; when it is absent, only the first four),
`db_setup` (a `.sql` file in the folder that creates the tables the
framework owns, such as its session table, written from the framework's own
migration; the harness applies it in one transaction before the conformance
check and empties the tables it created at the start of every round; it must
not touch `world`, `fortune` or `users` or contain transaction control, and
must not create a table Axum's `db.sql` creates, `tower_sessions.session`),
`phase2` (required once a phase-2 endpoint is listed: `validation`, the
mechanism; `csrf` with `design` `token` or `fetch-metadata`, `mechanism` and
`source`, required with `form`; `session` with `store` `cookie-signed`,
`cookie-encrypted`, `postgresql` or `memory`, `mechanism` and `source`,
required with `me`; `source` is `built-in`, `generator`, `stdlib`,
`documented` or `library`; `write_csrf`, `null` or `{"cookie": …,
"header": …}` for a framework whose production stack refuses every
cookieless write: the harness then sends that cookie from `GET /form` and
its value in that header with `PUT /world/{id}`), `variant`
(a label when a framework has more than one implementation), `default_variant`
(`true` for the variant the published results name after the framework alone), `env` (extra
environment variables for the container), `build_args_from_env` (environment
variables passed to `docker build` as build arguments, such as
`RULLST_VERSION`), `maturity_note` (shown with the results, for example for
an early 0.x framework), `notes`, `jit` (`true` for a runtime whose JIT
compiles hot code at run time after profiling it: the HotSpot JVM, .NET's
tiered compilation, V8 for Node.js, Ruby with YJIT, PHP with the OPcache JIT
turned on; it gets a 15 s warm-up per endpoint instead of 5 s),
`structure_note` (what else runs inside the server's 2 vCPUs, such as a
proxy in front of the application server, or a runtime version worth
naming; shown with the results), `database_note` (a database behaviour the
results must label on every database row, such as a new connection per
request), and `role` with `role_note`: `ranked` (the
default), `diagnostic` (shown with a score next to the reference, without a
position, for example Rullst's minimal configuration) or `control` (the A/A
control, with `control_of` naming the folder it copies).

The A/A control, `frameworks/axum-control`, is a byte-identical copy of
`frameworks/axum` except for `bench.json` and `README.md`; `harness.py
validate` fails otherwise. A change to Axum's folder copies every changed file
there in the same commit. Its scores give the A/A term of the tie margins of
the rankings (the README's "Ties" explains the other two).

### Checking your folder

```sh
export WRK="$(bench/install-loadgen.sh "$HOME/.local/bin")"  # wrk 4.2.0, for the concurrent step
python3 bench/harness.py validate
python3 bench/harness.py conformance --framework <name>
```

`conformance` builds the image, starts PostgreSQL and prints the result of
every check: first one request at a time, then a concurrent step that sends
each declared endpoint its measurement workload with 125 connections for
3 s and requires zero errors (any response that is not 2xx, any transport
error or timeout fails it). It checks, and `run` measures, only the endpoints `endpoints`
lists. While the database and application endpoints are being added to every
folder, a folder without them is measured on the others and listed as
incomplete in the Database or Application ranking (and so overall); once
every folder serves them, `endpoints` will be required to list all twelve.
`python3 bench/harness.py db-check` loads the database and applies every
folder's `db_setup` file in a rolled-back transaction, without building
images. Pull requests run the same check for every changed framework
folder. A maintainer can add the `benchmark-trial` label to a pull request
to run a one-round measurement of the changed frameworks.

Add the folder to the implementations table in the README.

Per-runtime conventions, so that implementations on the same runtime are
configured alike:

- Node.js: the active LTS release, `NODE_ENV=production`, one process per
  vCPU with the built-in `node:cluster` module (`BENCH_WORKERS`), and
  `DB_POOL_SIZE / BENCH_WORKERS` database connections per process.
- Python: `BENCH_WORKERS` server processes, threads or event loop per the
  server's documentation, and the pool divided across processes.
- Ruby and PHP: `BENCH_WORKERS` processes where the server sizes processes
  by CPU; otherwise its documented production default, explained in the
  folder README.

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

- measurements use Linux runners only (no macOS runners) and at most 8 at a
  time: the yield guard (`bench/yield_check.py`) allows 8 while Rullst/Rullst
  has at most 2 queued and 8 running jobs and 3 otherwise; the `max_parallel`
  input (`auto` by default) can set 1-8 for a manual run;
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
