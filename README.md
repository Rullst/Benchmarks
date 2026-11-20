# Rullst Benchmarks

An HTTP benchmark suite that compares [Rullst](https://github.com/Rullst/Rullst)
with other web frameworks under the same conditions. Every number is measured
by a GitHub Actions workflow on GitHub-hosted runners, so anyone can rerun it,
and every number on this page is generated from the measurement output.

- Dashboard: <https://rullst.win/Benchmarks/>
- Full results tables: [benchmarks_results.md](benchmarks_results.md)
- Machine-readable results: <https://rullst.win/Benchmarks/data/latest.json> (see [Machine-readable results](#machine-readable-results))

## What this benchmark does not measure

- **Logins and password hashing.** The harness signs in before measuring;
  `GET /me` measures resolving a session and loading the signed-in user, not
  the login itself.
- **Large or unusual request input.** Request bodies are small JSON objects
  and urlencoded forms: no multipart forms, file uploads, streaming or
  large payloads.
- **One common session store or CSRF mechanism.** `POST /form` and `GET /me`
  measure each framework's own default (a database, a signed or encrypted
  cookie, or process memory; a token or fetch-metadata check), which the
  results print next to the numbers.
- **Real deployments.** No TLS and no network latency: client, server and
  database share a single small virtual machine (4 vCPUs, 2 of them for the
  server) and talk over loopback. Tiers are short (10 s to 2 minutes).
- **Servers faster than the load generator.** When a run is client-bound
  (the load generator or PostgreSQL used the client vCPUs fully), its
  requests/s measure the client side rather than the server. The rankings
  then compare requests per CPU-second of the server and PostgreSQL
  together, and flag a run as not comparable when that would extrapolate
  from a server far below saturation
  ([How the scores are computed](#how-the-scores-are-computed)).
- **Scaling beyond 2 vCPUs.** Every server gets 2 vCPUs. Runtimes built to
  spread work over many cores (the BEAM behind Phoenix, the JVM behind
  Spring Boot, .NET behind ASP.NET Core) are measured where that design
  helps least, and their fixed per-process costs (JIT and GC threads,
  schedulers) weigh more on 2 vCPUs than on 16.
- **Latency at a fixed, realistic request rate.** wrk is a closed-loop load
  generator: each connection sends its next request when the previous one is
  answered, so the latencies are those of a saturated server with 125-500
  requests in flight, not those of a server at, say, 30% load, and a slow
  response delays the requests behind it instead of being recorded as a
  queue (coordinated omission).
- **JIT steady state.** Runtimes with a JIT compiler get a longer warm-up
  (15 s per endpoint instead of 5 s), but a 10 s run after it does not
  guarantee their fastest compiled code; a longer run might rank them higher.
- **A database on another host.** PostgreSQL runs on the same virtual
  machine, over loopback. A real database on another host adds a network
  round trip to every query, which favours implementations that send fewer
  queries or pipeline them, and changes which side is the limit.
- **HTTP/2, TLS and compression.** Everything is HTTP/1.1 with keep-alive,
  in plain text, without response compression.

## Results

<!-- results:start -->
> Measured on 2026-11-15 with **Rullst 13.0.0-alpha.5** on GitHub-hosted runners (INTEL(R) XEON(R) PLATINUM 8573C, 4 vCPUs, 16 GiB RAM; each server limited to 2 vCPUs and 2 GiB). Values are medians of 5 rounds. "vs Axum" is the ratio to the Axum baseline measured in alternating rounds on the same runner, which cancels most of the difference between runners; compare ratios rather than absolute numbers across runs. These results update automatically when a new Rullst version is published on crates.io. Last update: 2026-11-15.
>
> **Note:** This measurement found a throughput problem in the production stack that `cargo rullst new` generates: Rullst as generated reached 0.31× Axum's requests/s on /json, while the minimal configuration reached 1.00×. A fix is planned for Rullst 13.0.0-alpha.6. These results update automatically when a new Rullst version is published.

Source: [workflow run 43731095115](https://github.com/Rullst/Benchmarks/actions/runs/43731095115). Full tables, ranges and flags: [benchmarks_results.md](benchmarks_results.md); dashboard: <https://rullst.win/Benchmarks/>.

| Implementation | Version | Language | /json req/s | vs Axum | /db-single req/s | vs Axum | /html req/s | Tier 2 p99 (ms) | Idle RAM (MiB) | Peak RAM (MiB) | Tier 4 errors | req/s per MiB |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Axum – baseline | 0.8.9 | Rust | 186,759 | 1.00 | 19,658 | 1.00 | 186,891 | 3.02 | 1.1 | 10.7 | 0 | 17,454.1 |
| Actix Web | 4.19.0 | Rust | 190,569 | 0.97 | 19,370 | 0.98 | 191,126 | 2.92 | 1.3 | 9.5 | 0 | 20,059.9 |
| Loco | 1.3.1 | Rust | 65,740 | 0.42 | 15,323 | 1.01 | 59,368 | 7.10 | 3.0 | 13.9 | 0 | 4,729.5 |
| Rullst (as generated) | 13.0.0-alpha.5 | Rust | 59,139 | 0.31 | 17,531 | 0.77 | 57,206 | 11.30 | 1.6 | 12.6 | 0 | 4,693.6 |
| Rullst (minimal) | 13.0.0-alpha.5 | Rust | 114,422 | 1.00 | 9,935 | 1.00 | 109,272 | 4.83 | 1.2 | 11.3 | 0 | 10,125.8 |
| Topcoat | 0.12.1 | Rust | 218,610 | 0.83 | 41,049 | 1.42 | 204,761 | 3.10 | 1.3 | 11.1 | 0 | 19,694.6 |
| ASP.NET Core | 10.0.15 | C# | 71,839 | 0.62 | 4,091 | 0.41 | 38,234 | 8.03 | 26.4 | 108.7 | 0 | 660.9 |
| Django | 6.1.3 | Python | 5,990 | 0.02 | 2,480 | 0.08 | 5,162 | 102.90 | 104.1 | 116.6 | 0 | 51.4 |
| Laravel | 13.42.0 | PHP | 1,169 | 0.01 | 312 | 0.01 | 898 | 315.44 | 37.4 | 80.2 | 0 | 14.6 |
| NestJS | 12.5.0 | TypeScript | 126,809 | 0.48 | 19,516 | 0.67 | 58,469 | 2.93 | 162.9 | 263.2 | 0 | 481.8 |
| Phoenix | 1.8.16 | Elixir | 26,831 | 0.17 | 12,930 | 0.88 | 20,294 | 13.39 | 135.9 | 153.7 | 0 | 174.6 |
| Ruby on Rails | 8.1.4.1 | Ruby | 1,682 | 0.02 | 1,441 | 0.14 | 1,511 | 416.58 | 102.5 | 369.3 | 0 | 4.6 |
| Spring Boot | 4.1.2 | Java | 32,571 | 0.21 | 8,965 | 0.59 | 16,279 | 12.49 | 213.9 | 377.2 | 0 | 86.3 |
| FastAPI | 0.163.0 | Python | 17,577 | 0.07 | – | – | 14,292 | 20.09 | 167.7 | 225.2 | 0 | 78.1 |
| Fastify | 5.12.8 | JavaScript | 154,630 | 0.59 | 22,840 | 0.78 | 117,739 | 3.16 | 72.8 | 165.0 | 0 | 937.1 |
| Gin | 1.12.0 | Go | 78,542 | 0.51 | 19,765 | 1.32 | 76,162 | 9.50 | 3.5 | 19.8 | 0 | 3,966.8 |

Corrections (left-out results are shown as –):

- **FastAPI**: /db-single is not measured in this run: under load every request timed out because of a defect in this implementation (the session dependency's cleanup waited for a thread-pool slot held by requests waiting for a database connection), so the number says nothing about FastAPI. Fixed in Rullst/Benchmarks#8; the next run (Rullst 13.0.0-alpha.6) measures it again.

### Rankings

- **Speed (Tier 1):** requests per second on each of the four endpoints with 125 connections for 10 s; the score is the geometric mean of the four ratios to Axum.
- **Under pressure (Tier 2):** requests per second on /json with 300 connections for 30 s.
- **Memory (Tier 3):** the most RAM the server used while answering /json with 200 connections; lower is better, so the table shows the RAM ratio and the score is its inverse.
- **Endurance (Tier 4):** requests per second on /json with 500 connections for 2 minutes; errors, timeouts, RAM still growing and stops are listed with it.
- **Startup:** time from starting the container to its first answer; lower is better. The harness checks every 0.25 s, so times below 0.25 s count as equal.
- **Overall:** the geometric mean of the five category scores, each weighted equally (1/5), with every score oriented so that higher is better and Axum at 1.00. The weighting is a choice; the per-category positions are the detail.

Each cell is the position and the ratio to Axum (seconds for Startup). "(tie)": the load generator was the limit (client-bound) for both and the results are within 10% of each other, or the start-up times are within 0.25 s, so they share the position. Axum is the reference and has no position. "incomplete": a result is missing or left out, so there is no position rather than one computed from fewer metrics.

| Implementation | Overall | Speed | Under pressure | Memory (RAM) | Endurance | Startup |
| --- | --- | --- | --- | --- | --- | --- |
| Actix Web | 1: 1.01 | 1 (tie): 0.98× | 1 (tie): 0.97× | 1: 0.88× | 1 (tie): 0.97× | 1 (tie): 0.01 s |
| Axum – baseline | reference: 1.00 | reference: 1.00× | reference: 1.00× | reference: 1.00× | reference: 1.00× | reference: 0.01 s |
| Rullst (minimal) | 2: 0.98 | 1 (tie): 0.99× | 1 (tie): 1.00× | 3: 1.08× | 1 (tie): 1.00× | 1 (tie): 0.02 s |
| Topcoat | 3: 0.91 | 3: 0.94× | 3: 0.83× | 2: 1.06× | 3: 0.85× | 1 (tie): 0.01 s |
| Gin | 4: 0.62 | 4: 0.66× | 6: 0.51× | 6: 1.84× | 6: 0.51× | 1 (tie): 0.01 s |
| Loco | 5: 0.59 | 6: 0.51× | 8: 0.43× | 5: 1.32× | 8: 0.43× | 1 (tie): 0.01 s |
| Rullst (as generated) | 6: 0.49 | 9: 0.38× | 10: 0.29× | 4: 1.14× | 9: 0.29× | 1 (tie): 0.01 s |
| Fastify | 7: 0.42 | 5: 0.60× | 5: 0.60× | 11: 15.65× | 5: 0.63× | 7 (tie): 0.28 s |
| ASP.NET Core | 8: 0.38 | 7: 0.48× | 4: 0.62× | 8: 10.23× | 4: 0.63× | 9 (tie): 0.61 s |
| NestJS | 9: 0.25 | 8: 0.44× | 7: 0.49× | 13: 24.79× | 7: 0.50× | 11 (tie): 1.06 s |
| Phoenix | 10: 0.16 | 10: 0.24× | 11: 0.16× | 10: 13.73× | 11: 0.17× | 11 (tie): 1.08 s |
| Spring Boot | 11: 0.12 | 11: 0.20× | 9: 0.29× | 15: 35.92× | 10: 0.27× | 15: 4.12 s |
| Django | 12: 0.056 | 12: 0.031× | 13: 0.024× | 9: 10.37× | 13: 0.024× | 9 (tie): 0.76 s |
| Ruby on Rails | 13: 0.031 | 13: 0.025× | 14: 0.014× | 14: 34.16× | 14: 0.014× | 14: 1.38 s |
| Laravel | 14: 0.030 | 14: 0.007× | 15: 0.006× | 7: 7.42× | 15: 0.006× | 7 (tie): 0.41 s |
| FastAPI | incomplete | incomplete | 12: 0.072× | 12: 20.97× | 12: 0.068× | 11 (tie): 1.07 s |
<!-- results:end -->

## What is measured

Every implementation serves the same endpoints on port 8080. The first four
measure framework overhead; the next three, added in November 2026, follow
the [TechEmpower Framework Benchmarks](https://github.com/TechEmpower/FrameworkBenchmarks/wiki/Project-Information-Framework-Tests-Overview)
(round 23) multiple-queries, updates and fortunes tests and measure database
work through the framework's ORM and template engine; the last five (v3
phase 2, [docs/v3-spec.md](docs/v3-spec.md)) measure what an
application does with a request: route parameters, query strings, JSON and
form bodies, validation, a write of one record, CSRF verification and a
signed-in session. An implementation serves the endpoints after `/html` once
its `bench.json` lists them (`"endpoints"`); until then it is "not
implemented yet" for them.

| Endpoint | Response |
| --- | --- |
| `GET /text` | `Hello World`, `text/plain` |
| `GET /json` | `{"message":"Hello World"}`, `application/json` |
| `GET /db-single` | the row with `id = 1` of the `world` table, read from PostgreSQL on every request, as `{"id":1,"randomNumber":N}`, `application/json` |
| `GET /html` | `<!DOCTYPE html><html><head><title>Benchmark</title></head><body><h1>Hello World</h1></body></html>`, `text/html`, rendered by the framework's template engine with `World` passed as a variable |
| `GET /queries?queries=N` | N random rows of `world` (ids 1 to 10,000), each read with its own query, as a JSON array of `{"id":…,"randomNumber":…}`, `application/json`. N is clamped to 1-500; a missing or invalid value counts as 1. Measured with N = 20 |
| `GET /updates?queries=N` | N random rows, each read with its own query, given a new random `randomNumber` (1-10,000), written back to the database before the response, and returned as for `/queries`. Writing the rows in a batch or a transaction is allowed (TechEmpower's rules); each folder README says what its implementation does. Measured with N = 20 |
| `GET /fortunes` | every row of the `fortune` table (TechEmpower's 12 rows, one of them a `<script>` and one in Japanese) plus one added at request time (id 0, `Additional fortune added at request time.`), sorted by message and rendered as an HTML table by the framework's template engine, which escapes the messages; `text/html; charset=utf-8` |
| `GET /world/{id}` | the row with that id, read by primary key through the ORM on every request, as `{"id":…,"randomNumber":…}`; 404 for an id without a row, 400, 404 or 422 for one that is not an integer. Measured with the 10,000 ids in a shuffled order |
| `GET /worlds?min=&max=&limit=&page=` | the rows with `min <= id <= max`, ordered by id, `limit` rows of page `page`, as a JSON array, in one query (defaults 1, 10,000, 20, 1; `limit` 1-100, `page` 1-1000). Parameters are validated with the framework's mechanism: a value that is not an integer, out of range, or `min > max` is answered 400 or 422. Measured with 2,000 random 1,000-id windows, 20 rows per page, pages 1-5 |
| `PUT /world/{id}` | body `{"randomNumber": n}` (a JSON integer 1-10,000), validated (400 or 422 otherwise, a JSON string such as `"5"` included, with nothing written); the row is changed the ORM's usual way and returned as stored. A public JSON API call, sent without cookies (Rullst as generated, which refuses cookieless writes, gets its CSRF cookie and header). Measured with the 10,000 ids shuffled, random values |
| `POST /form` | an urlencoded form (`name`, 1-64 characters, and `randomNumber`, 1-10,000) checked by the framework's CSRF protection and validated, answered with a page that greets the name (escaped) rendered by the template engine. Sent like a browser that loaded `GET /form` once: its cookies and hidden fields, `Origin` and `Sec-Fetch-Site: same-origin`. Measured with 125 such sessions |
| `GET /me` | `{"id":…,"username":…,"displayName":…}` for the signed-in user: the framework's default session mechanism, then the user's row read through the ORM on every request; 401, 403 or a redirect without a session. Measured with 125 sessions, one login each (`user1`..`user125`, made after Tier 4 and not timed) |

Each `/form` and `/me` result is shown with the implementation's CSRF design
(`token`, a secret the form echoes, or `fetch-metadata`, `Sec-Fetch-Site` and
`Origin` checks) and session store (`postgresql`, `cookie-signed`,
`cookie-encrypted` or `memory`), and where the mechanism comes from
(built-in, the framework's generator, the language's standard library, a
package the framework's documentation recommends, or the most-used library).

**Write contention ("hot rows").** After the other runs, `PUT /world/{id}`
runs again with 125 connections for 10 s, but on ids 1-10 only, so requests
wait for each other's row locks. Its errors, timeouts and p99 latency are
reported next to Axum's; it is not part of any ranking.

The tiers:

| Tier | Load | Reported | Used for |
| --- | --- | --- | --- |
| 1 | 125 connections for 10 s on each endpoint, each warmed up immediately before (reads before writes; the application endpoints and the hot-rows run come last) | requests/s, p50 and p99 latency, errors, server CPU, server efficiency, CPU per request of the server and of PostgreSQL | the Hello world, Database and Application scores |
| 2 | 300 connections for 30 s on `/json` | requests/s, p50 and p99 latency, errors and timeouts, server efficiency | the Stability check (pass or fail) |
| 4 | 500 connections for 2 minutes on `/json` | requests/s, p99, errors and timeouts, server efficiency, RAM growth, whether the server stopped | the Stability check (pass, warn or fail) |
| 3 | idle for 10 s after start-up; then, after Tiers 1, 2 and 4 and a 10 s idle period, 200 connections for 15 s on `/json` | idle RAM; the RAM high-water mark under load, idle and loaded CPU | the Memory score |

**Efficiency.** Every load run measures the server's CPU use and
PostgreSQL's (each container's cgroup), so the results report three costs
per request: server efficiency (requests per server CPU-second), the
server's and PostgreSQL's CPU time per request together ("CPU µs/req"), and
PostgreSQL's alone ("PG µs/req"). The last one is how much database work a
framework's queries cause: preparing statements or not, extra round trips,
connection set-up. Tiers 2 to 4 stay on `/json`: they measure behaviour
under more connections, memory and stability, which the database endpoints
would mostly turn into a measurement of PostgreSQL on the shared vCPUs.

Each metric is also reported as a ratio to the Axum baseline measured on the
same runner (see below). The results also list requests/s per MiB of peak RAM
as one column; it is not used to rank anything.

**Rankings.** `bench/rankings.py` computes one ranking per category from
those ratios ([How the scores are computed](#how-the-scores-are-computed)):

| Category | What it scores | Score |
| --- | --- | --- |
| Hello world | Tier 1 `/text`, `/json`, `/html` | geometric mean of the three capacity ratios |
| Database | Tier 1 `/db-single`, `/queries`, `/updates`, `/fortunes` | geometric mean of the four capacity ratios |
| Application | Tier 1 `GET /world/{id}`, `GET /worlds`, `PUT /world/{id}`, `POST /form`, `GET /me` | geometric mean of the five capacity ratios |
| Memory (high-water mark) | Tier 3's RAM high-water mark after the load tiers | Axum's / the implementation's, both at least 64 MiB |
| Startup | time to the first answer | Axum's / the implementation's, both at least 1 s |
| Stability (a check, not a score) | Tiers 2 and 4 | fail: a stop, or a round with more than 1% errors (timeouts included); warn: RAM still growing at the end of Tier 4; otherwise pass |

Every score is a ratio to Axum (1.00), higher is better, and the three
throughput scores are efficiency-aware: a run counts with its requests/s
ratio when neither server was client-bound, and with its ratio of requests
per CPU-second of the server and PostgreSQL together when either was. A
run with more than 1% errors has no score in its category. Ties come from
an A/A control (an identical copy of Axum, measured like everything else)
and from how much each implementation's scores differ between its jobs
([How the scores are computed](#how-the-scores-are-computed)).
An overall ranking (the geometric mean of the five scores) is computed for
review with a table of the positions under other weightings; it is
published only when `scoring.publish_overall` in
[bench/config.json](bench/config.json) is `true` (it is `false`: the
maintainer has not decided to publish one). The per-category rankings are
always shown.

## Method

Each framework is measured by its own jobs, each on a GitHub-hosted
`ubuntu-latest` runner (4 vCPUs, 16 GiB of RAM): 3 jobs per implementation
by default (the `jobs_per_framework` input; `publication.min_jobs` in
[bench/config.json](bench/config.json) is the minimum for publishing), so
every implementation is measured on three machines, often with different
CPU models. Ratios to Axum cancel most, not all, of the difference between
runners; the tie margins below are derived from what remains. Each job
records `lscpu`, the CPU model, the kernel, the memory, the Docker version,
image digests and tool versions with the results, and every results row
names the CPU model of each of its jobs.

1. **Build.** The job builds the framework's image and the Axum baseline's
   image from their folders under `frameworks/`, with pinned base images and
   lockfiles.
2. **Database.** PostgreSQL 18.6 (image pinned by digest) starts with a
   `world` table of 10,000 rows and the 12-row `fortune` table
   ([bench/db/init.sql](bench/db/init.sql)) and 1,000 accounts in `users`
   (`user1`..`user1000`, one bcrypt and one Argon2id hash of the same
   password, [bench/db/phase2.sql](bench/db/phase2.sql)), with
   `synchronous_commit = off` (as in TechEmpower's configuration: `/updates`
   measures the writes, not the runner's disk flushes) and
   `pg_stat_statements` loaded. Tables a framework owns (its session or token
   table) come from the folder's `db.sql` (`"db_setup"` in `bench.json`,
   written from the framework's own migration), applied once by the harness:
   no implementation creates or migrates tables at start-up, which is
   timed.
3. **Conformance.** Each implementation is started and checked: status, media
   type and body of every endpoint, HTTP/1.1 keep-alive, and that
   `/db-single` follows changes made to the row between requests (so it reads
   the database every time). For `/queries`, `/updates` and `/fortunes`,
   `pg_stat_statements` counts the statements each request runs: each row
   must be read by its own `SELECT`, the updated rows must be in the
   database, and `/fortunes` must read the table on every request without
   `ORDER BY` (the rules are in [CONTRIBUTING.md](CONTRIBUTING.md)). The
   phase-2 endpoints are checked against the database the same way (the
   response follows rows changed between requests, `/worlds` runs one query,
   every `PUT` with a new value runs an `UPDATE`, refused writes write
   nothing), together with validation (a JSON number sent as a string is
   refused), the CSRF check
   (a forged cross-site post, a changed token and a post without the cookies
   are refused, and one session's cookies and token stay valid for repeated
   posts) and sessions (each session returns its own user, re-read on every
   request). Statement tracking is then turned off for the measurement. An
   implementation that fails is reported as failed with the reason and is
   not measured. After the one-request-at-a-time checks pass, a short
   **concurrent step** sends every declared endpoint its measurement
   workload with 125 connections for 3 s (`concurrent_check` in
   `bench/config.json`, [bench/load_check.py](bench/load_check.py)), with
   wrk's status hook on: any response that is not 2xx (3xx included), any
   transport error or timeout fails conformance. This catches what only
   shows under load (a pool that times out waiting for a connection, a
   server that closes connections).
4. **Rounds.** The framework and Axum then alternate for 5 rounds per job,
   in ABBA order (framework first in odd rounds, Axum first in even rounds;
   a second job starts with Axum), so that a drift during the job (a runner
   warming up or throttling) does not always fall on the same side. Each
   round restores the `world` table to its initial values and rewrites it
   (`VACUUM FULL`, so earlier `/updates` runs leave no dead rows behind),
   empties the framework's own tables (its sessions), starts a fresh
   container, waits for it to answer and measures it idle. Each phase-1
   endpoint is then warmed up immediately before its own Tier 1 run (125
   connections, with wrk's status hook so that a 3xx shows up as a warm-up
   error; 5 s, or 15 s for a runtime whose JIT compiles code while running:
   below), left idle for 2 s and measured. Then come Tier 2, Tier 4, a 10 s
   idle period and Tier 3's load (the Memory high-water mark). The
   application endpoints come last: the harness obtains the sessions they
   need (125 `GET /form` pages and 125 logins, 8 at a time, not timed), and
   warms up and measures each one the same way, then runs the hot-rows test.
   They run last because logging in hashes passwords, and a memory-hard hash
   leaves memory in the allocator (Axum went from 1 MiB to about 1 GiB after
   125 Argon2id logins in the first trial), which would distort the RAM
   measured in Tiers 3 and 4. Warm-up errors are reported with the results.
   Results are medians over rounds, with the lowest and highest round shown
   as the spread.

   **Longer warm-up for JIT runtimes.** A folder whose runtime compiles hot
   code at run time after profiling it sets `"jit": true` in its
   `bench.json` and gets 15 s of warm-up per endpoint instead of 5 s: the
   HotSpot JVM (Spring Boot), .NET's tiered compilation (ASP.NET Core), V8
   (NestJS, Fastify) and Ruby's YJIT (Rails). Runtimes that compile ahead of
   time (Rust, Go), the BEAM's JIT (it compiles each module when it is
   loaded, without profiling) and the CPython and PHP versions used here
   (their JITs are off) keep 5 s. The longer warm-up costs only time; it
   cannot make a non-JIT runtime slower.
5. **Ratios.** For every round pair, each metric of the framework is divided
   by Axum's value from the paired round on the same runner; the reported
   ratio is the median of those per-round ratios, pooled over every job of
   the implementation. Runner-to-runner differences (CPU model, noisy
   neighbours) largely cancel out in the ratio, so compare ratios rather
   than absolute numbers across jobs and runs.
6. **A/A control.** `frameworks/axum-control` is a byte-identical copy of
   the Axum baseline (`harness.py validate` checks it), measured in its own
   jobs exactly like every other implementation. Its ratios should all be
   1.00, so how far they land from 1.00 is the noise of a ratio on one
   runner; it is one of the three terms of the tie margins (below) and is
   listed, unranked, with the results.

Fixed settings, the same for every implementation:

- **CPU split.** The server container gets 2 vCPUs (`--cpuset-cpus`; both
  threads of one physical core when the runner exposes SMT siblings). The
  load generator, PostgreSQL and the harness use the other 2 vCPUs. The job
  stops if the runner has fewer than 4 vCPUs. PostgreSQL's CPU use is
  measured in every run (its container's cgroup). Giving PostgreSQL a vCPU of
  its own was measured and not adopted: see [CPU split](#cpu-split).
- **Memory.** The server container is limited to 2 GiB (`--memory`), like a
  small cloud instance; runtimes that size their heap from the container
  limit see the same limit.
- **Network.** All containers use the host network (no Docker port proxy).
- **Load generator.** [wrk](https://github.com/wg/wrk) 4.2.0, built on the
  runner from its source tarball (checked by SHA-256; wrk publishes no
  binaries; the results record the binary's SHA-256 and the compiler), with
  a 5 s request timeout and one thread per client vCPU, as a host process
  pinned to the client vCPUs. It sends one fixed request on the endpoints up
  to `/fortunes` and on Tiers 2-4, and on the phase-2 endpoints cycles
  through requests the harness built beforehand (ids, query strings, bodies,
  each session's cookies and CSRF token) with a fixed seed, so every
  implementation gets the same mix. On the phase-2 endpoints, in every
  warm-up and in the concurrent conformance step, a Lua hook counts every
  response that is not 2xx (3xx included) as an error; the measured runs of
  the fixed-request endpoints run without it, because it costs client CPU
  that would make more of those runs client-bound, so there wrk counts
  statuses of 400 and above, and the warm-up just before each run and the
  conformance check would show a redirect.
  wrk opens `connections / threads` connections per thread: 124 of Tier 1's
  125 with two threads (the results record `connections_open`). It was chosen
  over bombardier (one fixed request per run) and oha (no per-request
  headers) because it varies URL, headers and body together and does the most
  requests per client CPU-second ([measurements](docs/v3-spec.md#7-load-generator));
  its licence (Apache 2.0 plus a naming condition on changed derivatives)
  does not affect running it unmodified.
- **Database pool.** 16 connections per server (`DB_POOL_SIZE`), split
  across processes for multi-process servers.
- **Workers.** Sized for the 2 vCPUs the server has (`BENCH_WORKERS=2`), the
  way each framework's production guidance says to size them.
- **Logging.** No per-request logging in any implementation (no access
  log, no logger middleware); application logs stay at the framework's
  production level, which writes nothing per request. Where a framework
  cannot turn off its access log, it stays on and the folder README says
  so. Container output is discarded (`--log-driver none`) during
  measurement. Every folder README has a "Production settings" section that
  lists each setting (logging, pool, prepared statements, middleware,
  workers) with the documentation it follows.
- **RAM** is the container's cgroup `memory.current` minus inactive file
  cache (what `docker stats` shows), sampled every 100 ms. CPU is the
  container's cgroup CPU time, in cores (2.00 means both vCPUs busy).

Flags in the results:

- **PostgreSQL-bound** and **load-generator-bound** (together:
  client-bound): the client vCPUs, which the load generator and PostgreSQL
  share, were at least 90% busy during the run (`saturation_threshold` in
  `bench/config.json`). It is PostgreSQL-bound when PostgreSQL's container
  used more of that CPU than the load generator, and load-generator-bound
  otherwise. The server might have answered more requests, so its
  requests/s understate it; the rankings then use efficiency (below). The
  90% threshold is a hard cut: a run at 89% counts as server-limited and one
  at 91% as client-bound. Instead of a hysteresis band, every table shows
  both the requests/s ratio and the efficiency ratio, and each score says
  which one it used, so a run near the threshold can be read both ways.
- **RAM still growing**: in Tier 4, RAM rose by more than 10% and 8 MiB
  between the middle and the last tenth of the test. For garbage-collected
  runtimes this can be heap growth rather than a leak, so it is a warning in
  the Stability check, not a failure.
- **stopped**: the server process exited (crash or out-of-memory kill) during
  a round. The phase is reported.

### How the scores are computed

**Capacity ratio of a run.** For every round pair (the framework's round and
the paired Axum round on the same runner):

- neither run client-bound: both servers were the limit, and the requests/s
  ratio is the capacity ratio;
- either run client-bound (PostgreSQL-bound or load-generator-bound): the
  ratio of requests per CPU-second of **the server and PostgreSQL
  together**. A framework is charged for the PostgreSQL work its queries
  cause: a database run that is PostgreSQL-bound is mostly PostgreSQL's
  CPU, and a framework whose queries cost PostgreSQL more (no prepared
  statements, an extra round trip per query, a new connection per request)
  scores lower even when its own server code is cheap. Until 19 November
  2026 the scores used server CPU alone, which left PostgreSQL's cost out;
  it is included now. On runs without database work PostgreSQL's CPU is
  close to zero and this is the server efficiency;
- **not comparable**: a side was load-generator-bound while its server used
  less than 75% of its vCPUs (`MIN_SERVER_SHARE` in `bench/measure.py`).
  Its efficiency was then measured far below the load it could take, and
  efficiency changes with load (see [CPU split](#cpu-split)), so it is not
  used as its capacity.

`results[].ratios["<run>.capacity"]` holds the median over the comparable
pairs, with `pairs`, `cpu_rounds`, `not_comparable_rounds`,
`postgresql_rounds` and `load_generator_rounds`.

**Category scores.** A throughput category's score is the geometric mean of
its runs' capacity ratios; "*" marks a score where a run used CPU
efficiency in most of its comparable pairs. A run is left without a score,
and so is its category for that implementation, when:

- most of its round pairs were not comparable ("not comparable");
- its median error rate is above 1% ("errors"; any response that is not
  2xx, any transport error or timeout; every request the load sends is
  valid, so fast error responses would otherwise raise a score). This
  applies to every scored run in every category;
- it is missing, left out by a correction or not served yet ("incomplete").

Memory and Startup are costs: the score is Axum's value divided by the
implementation's, with floors (every high-water mark counts as at least
64 MiB, every start-up as at least 1 s), so that differences far below what
matters in production (11 MiB against 14 MiB, 0.01 s against 0.4 s) do not
move a score. Stability is a check, not a score: Tiers 2 and 4 pass, warn
(RAM still growing) or fail (a stop, or a round with more than 1% errors).

**Ties.** Every implementation has one score per job (runner) in each
category, computed from that job's rounds; its **between-job spread** is the
half-range of the logarithms of those scores. Two scores tie when the gap
between them, in natural-log units, is at most the largest of:

- **(a) the A/A margin:** the largest deviation from 1.00 of the A/A
  control's scores in that category (per job, and pooled over its jobs);
- **(b) their combined spread:** the root of the sum of squares of the two
  implementations' between-job spreads;
- **(c) the pooled floor:** the median between-job spread of the ranked
  implementations measured on at least two jobs in that category.

An implementation whose jobs all ran on one CPU model (or on a model the
runner did not report) counts with at least the pooled floor as its spread,
because its own spread cannot include the difference between CPU models; an
implementation with a score from a single job counts with the floor. The A/A
control alone is not enough: each of its jobs compares two identical servers
on the same runner, so it cannot show how the ratio between two different
frameworks changes from one CPU model to another. Scores within the margin
of the best score of their group share a position ("(tie)"); each score is
compared with that best score and, when the group's other members have a
wider spread than its own, counts with the widest of them, so that equal
scores always share a position. A score within the largest of (a), its own
spread and (c) of 1.00 is marked "≈": not distinguishable from Axum.
Start-up times within the 0.25 s readiness check interval also share a
position. The overall score and the other weightings use the same rule with
the per-job geometric means. The A/A margin and the floor of each category
are printed above the rankings; "±" after a score is the margin of the
comparison that set its position, and the detailed tables in
[benchmarks_results.md](benchmarks_results.md) list each job's score and CPU
model, the spread used and that comparison.

**Unranked rows.** Axum is the reference (1.00). Rullst's minimal
configuration, the A/A control and the Axum variant without SQLx's
connection test are diagnostics: they get scores, labelled, without a
position, so they never push a ranked implementation down.

**Overall.** The geometric mean of the five category scores with equal
weights, and the positions under other weightings (throughput only,
Database and Application only, without Hello world, throughput counted
twice), are computed for review and published only when
`scoring.publish_overall` is `true`. An implementation that fails the
Stability check has no overall position. The weighting is a choice; the
sensitivity table shows how much the order depends on it.

### CPU split

PostgreSQL shares the 2 client vCPUs with the load generator. On the
database endpoints both compete for them, so most `/db-single` runs were
client-bound. (This experiment ran with bombardier, the load generator
before wrk.) Giving PostgreSQL a vCPU of its own (server 2, load generator 1,
PostgreSQL 1) was measured for Axum, alternating both splits on one runner
(a temporary `cpu-split-experiment` workflow, November 2026):

| Run | Split | req/s | Server CPU (cores) | Efficiency (req/CPU-s) | Load generator CPU (cores) | PostgreSQL CPU (cores) | Client-bound |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| /json | shared | 155,420 | 1.93 | 80,424 | 1.99 | 0.00 | 2/2 |
| /json | own vCPU | 98,205 | 1.39 | 70,526 | 1.00 | 0.00 | 2/2 |
| /db-single | shared | 14,763 | 1.08 | 13,631 | 0.50 | 1.49 | 2/2 |
| /db-single | own vCPU | 10,897 | 0.78 | 14,054 | 0.45 | 1.00 | 2/2 |
| /queries?queries=20 | shared | 1,062 | 1.13 | 940 | 0.06 | 1.93 | 2/2 |
| /queries?queries=20 | own vCPU | 754 | 0.64 | 1,185 | 0.05 | 1.00 | 2/2 |
| /updates?queries=20 | shared | 485 | 1.03 | 473 | 0.04 | 1.96 | 2/2 |
| /updates?queries=20 | own vCPU | 338 | 0.56 | 605 | 0.03 | 1.00 | 2/2 |
| /fortunes | shared | 22,792 | 1.73 | 13,174 | 0.58 | 1.41 | 2/2 |
| /fortunes | own vCPU | 16,660 | 1.34 | 12,451 | 0.50 | 1.00 | 2/2 |
| Tier 2 /json | shared | 153,294 | 1.92 | 79,884 | 1.98 | 0.00 | 2/2 |
| Tier 2 /json | own vCPU | 96,661 | 1.38 | 70,274 | 0.99 | 0.00 | 2/2 |

Medians of two rounds per split, alternating on one runner
([run 44555335441](https://github.com/venelouis/Benchmarks/actions/runs/44555335441),
in the maintainer's fork). Its own vCPU did not make any run server-bound.
The load generator alone on one vCPU caps `/json` at about 98,000 req/s
instead of 155,000, and PostgreSQL alone on one vCPU is the limit of every
database endpoint, at 25-30% fewer requests/s. Sharing two vCPUs lets
whichever side needs the CPU use it (the load generator on `/json`,
PostgreSQL on `/queries` and `/updates`). **Decision: the split stays shared**
(server 2 vCPUs, load generator and PostgreSQL 2 vCPUs). The database
endpoints are limited by PostgreSQL, which the results show as
PostgreSQL-bound with PostgreSQL's CPU use next to them, and the rankings
compare those runs by requests per CPU-second of the server and PostgreSQL
together. `BENCH_DATABASE_CPUS=1` (or `database.cpus` in
`bench/config.json`) reproduces the other split.

The same runs show how much efficiency depends on the load. With less load
(the own-vCPU split), Axum's server efficiency was 9-14% lower on `/text`,
`/json` and `/html` and 26-28% higher on `/queries` and `/updates`; the
efficiency the rankings use (requests per CPU-second of the server and
PostgreSQL together) moved by -12% on `/json`, +7% on `/db-single`, -2% on
`/fortunes` and +33-34% on `/queries` and `/updates` (where PostgreSQL ran
on one vCPU instead of two: fewer queries in parallel cost it less CPU
each). Efficiency ratios therefore compare servers well when both sides run
at similar loads, which the paired rounds on one runner give when both are
limited the same way. When one side is limited by its own server and the
other by PostgreSQL, the side that loaded PostgreSQL less can look up to
about a third cheaper on `/queries` and `/updates` for that reason alone,
and differences of that size between such implementations are not
significant. That is also why a server far below saturation is not compared
by efficiency at all ([How the scores are computed](#how-the-scores-are-computed)).

## Fairness

The rule is the same for every implementation, Rullst included: **what the
framework's own documentation recommends for production.** How well each
folder follows it is a judgement made by one maintainer
([Authorship](#authorship)); the folder READMEs give the sources, so each
choice can be checked and challenged.

- Each implementation follows its own framework's production
  recommendations: release or production build, pinned versions and
  lockfiles, the framework's standard database layer (its ORM where it has
  one) and template engine, and its documented way to run in production.
  Each folder README has a "Production settings" section: logging,
  database pool and driver settings (prepared statements, connection
  checks), middleware, server and workers, each with the documentation it
  follows. Where the documentation recommends nothing, the framework's
  default stays, even when another setting would be faster.
- **Defaults differ, and the results show it.** Following each framework's
  documentation does not make the stacks equal. Examples the results let you
  see: Laravel on PHP-FPM opens a new PostgreSQL connection for every
  request (its documentation does not recommend persistent PDO connections;
  its database rows are labelled); SQLx, which Axum, Actix Web, Loco and
  Rullst use, tests pooled connections with a round trip, while Topcoat's
  and Gin's drivers mostly do not (the unranked Axum variant without the
  test bounds that cost); node-postgres, under Fastify and NestJS, sends
  unprepared statements, as its documentation advises for simple queries;
  Rails uses 6 of its 16 connections (2 Puma workers × 3 threads, Rails'
  production default). PostgreSQL's CPU per request is printed for every
  database run so these costs are visible.
- **Structural differences.** Some containers run more than the
  application server inside the server's 2 vCPUs: Rails behind Thruster,
  Laravel behind nginx with PHP-FPM; Django and FastAPI run on different
  Python versions, each the one its documentation recommends. The results
  list them under "Structural differences".
- **Phase-2 mechanisms.** Each phase-2 endpoint uses the framework's
  standard mechanism for each concern, in this order: built into the
  framework, written by its generator, the language's standard library, a
  package its documentation recommends, the most-used maintained package.
  Where the framework documents how to scope them, sessions, CSRF and
  authentication apply only to `/form`, `/login` and `/me`, so the other
  endpoints keep their stack; Rullst as generated keeps its global
  production stack, as `cargo rullst new` generates it, and NestJS's CSRF
  check (`app.enableCsrfProtection()`) is global because Nest offers no
  per-route form. The folder READMEs name what each uses.
- **Settings the load needs.** The harness signs in 125 users from one
  address at the start of every round, so the login rate limits that
  generators add are relaxed (Rails' generated `rate_limit` is left out;
  Rullst's generated `credential_rate_limit` allows 1,000 instead of 10
  attempts per minute), and Laravel and Django use the stored hashes' bcrypt
  cost so that a login does not rehash and rewrite the password. Validation
  layers that read `"5"` as a number in a JSON body (Spring Boot's Jackson,
  ASP.NET Core, Fastify's Ajv, Laravel, Pydantic, Django forms, Rails,
  Ecto) are configured or extended to refuse it. Each folder README says
  what it changed and why.
- **Rullst is measured as generated and ranked as generated.** Rullst as
  generated by `cargo rullst new` and `cargo rullst deploy` (its default
  production middleware included) is the ranked Rullst. Rullst's minimal
  configuration (its router, ORM and `html!` without that middleware,
  comparable to the Axum app) is shown next to the reference as an unranked
  diagnostic: it takes no position in any ranking. The results say whether
  the measured Rullst came from crates.io or from a git revision.
- **The method treats every implementation the same way**: the same
  harness, CPU split, rounds in ABBA order against Axum on the same runner,
  warm-up rule by runtime class, error gate and tie margins. That does
  not remove what 2 vCPUs, one shared machine and a closed-loop load
  generator favour ([What this benchmark does not
  measure](#what-this-benchmark-does-not-measure)).
- Improvements from people who use a framework in production are welcome;
  see [CONTRIBUTING.md](CONTRIBUTING.md).

## Authorship

One person, the maintainer of Rullst, wrote every implementation in this
repository, with the help of AI coding assistants, and also designed the
method. Nobody from the other frameworks' communities has reviewed their
folders yet. The maintainer has tried to follow each framework's production
documentation, and the folder READMEs cite it, but an expert in a framework
will know things that its documentation does not say.

If you use one of these frameworks in production, please review its folder:
the configuration, the code of each endpoint and the README's "Production
settings". Pull requests that bring an implementation closer to what its
community runs in production are welcome, whichever way they move its
numbers; see [CONTRIBUTING.md](CONTRIBUTING.md).

## Limitations

- **Shared, virtual runners.** GitHub-hosted runners are virtual machines on
  shared hosts, with different CPU models from job to job. Absolute numbers
  differ between runs and between jobs of the same run; the per-round ratio
  to Axum and the three jobs per implementation reduce this but do not
  remove it. The tie margins take what is left from the A/A control and from
  how much each implementation's scores differ between its jobs: differences
  smaller than the margin are within the noise. Three jobs give a rough
  estimate of that spread, and an implementation whose three jobs happen to
  run on one CPU model gets the pooled floor instead of its own.
- **The load generator limits the top.** With 2 vCPUs, the load generator
  (and PostgreSQL on the database endpoints) cannot saturate the fastest
  servers. Those results are flagged, and the rankings compare them by CPU
  efficiency, which depends somewhat on the load ([CPU split](#cpu-split)).
- **Short tiers.** Tests last 10 s to 2 minutes, after a 5 s warm-up per
  endpoint (15 s for JIT runtimes). They do not show long-term stability, and
  runtimes with a JIT compiler may not reach their best speed.
- **One small machine.** Client, server and database share one virtual
  machine and talk over loopback: no network latency, no TLS, HTTP/1.1 with
  keep-alive only.
- **Small endpoints.** `/text`, `/json` and `/html` measure framework
  overhead (routing, serialization, templates, middleware). `/db-single`,
  `/queries`, `/updates` and `/fortunes` add database work through the ORM
  and a template over database rows, but they are still small, fixed
  workloads on a 10,000-row table; a real application's code and data
  usually dominate. Tiers 2 to 4 use `/json` only.
- **`/form` and `/me` compare defaults.** Each framework uses its own CSRF
  design and its default session store for a signed-in user: a database
  store costs a query (and some write the session on every request), a
  cookie store a signature check or decryption, an in-memory session a map
  lookup. Axum, the reference, uses a PostgreSQL store (tower-sessions), so
  `/me` ratios above 1.00 for cookie stores partly measure that choice. The
  results print the design and the store next to the numbers; a faster or
  slower library or store would change them. Laravel keeps its `cookie`
  session driver rather than its default `database` driver: the load sends
  no cookies to `/html`, so the database driver would insert a session row
  on every `/html` request, an artifact of the load generator.
- **Hot rows are reported, not ranked.** The contention run shows lock waits
  on 10 rows; it does not model a real application's write pattern.
- **One configuration per framework.** Experts may know better settings; the
  folders document the choices so they can be challenged.

## Automatic updates

A nightly check (01:00 UTC-3) reads the newest `rullst` version on crates.io,
prereleases included. When that version has not been measured yet, the
workflow measures every implementation with it (5 rounds on each of 3 jobs
per implementation) and commits the results to `main`: this README's table,
[benchmarks_results.md](benchmarks_results.md) and the JSON files under
[results/](results/). The dashboard is then rebuilt. Each measured Rullst
version keeps its own results file, so the history shows how Rullst's
numbers change between releases. If Rullst cannot be built or fails
conformance with the new version, nothing is published, the failure is
recorded in `results/attempts.json` and the workflow run fails, so a
maintainer can fix the benchmark app and rerun it by hand.

**Publication gate.** A scheduled or manual publication also refuses, and
publishes nothing, when (`publication_gate` in
[bench/aggregate.py](bench/aggregate.py), limits in `publication` in
[bench/config.json](bench/config.json)):

- an implementation was not measured, or was measured on fewer than 3 jobs
  or fewer than 5 rounds per job (a run recorded with a lower minimum is
  still held to 3);
- the jobs disagree on the harness commit, the configuration, the vCPU
  count, the load generator (its version, source tarball and compiler: the
  binary built on each runner is not byte-for-byte reproducible), the
  PostgreSQL version or the rounds;
- a scored run is above the 1% error limit, or an implementation fails the
  Stability check;
- the A/A control is missing, or its tie margin is above 5% in any
  category (the run was too noisy to rank);
- a category has no between-job spread (no ranked implementation has scores
  from two jobs), so its tie margins could not include the difference
  between runners;
- Rullst was not built from its crates.io release.

The workflow summary then lists the reasons; the results of the run stay
available as artifacts.

**Shared runners.** The Rullst organization shares one pool of hosted runners
between Rullst/Rullst and this repository. A measurement uses only Linux
runners, and one measurement runs at a time (a new trigger waits; it never
cancels a running measurement). Before a scheduled or manual run starts, it
checks the public Actions API of Rullst/Rullst and does not start while a
release, release admission or a long verification workflow is running there,
or while more than 10 jobs are queued; the next nightly check tries again. A
manual run can override this with the `force` input. The same check sets how
many frameworks are measured at once: 8 when Rullst/Rullst has at most 2
queued and at most 8 running jobs, otherwise 3, and never more than 8 (the
`max_parallel` input, `auto` by default and for the nightly run, can set 1-8
instead). Labelled pull request trials use 3.

## Machine-readable results

| URL | Content |
| --- | --- |
| <https://rullst.win/Benchmarks/data/latest.json> | the newest published results |
| <https://rullst.win/Benchmarks/data/versions.json> | index of every measured Rullst version, with the headline numbers of the Rullst variants and Axum |
| `https://rullst.win/Benchmarks/data/rullst/<version>.json` | the results for one Rullst version (same shape as `latest.json`) |

The same files are in this repository under `results/`, with each job's full
output (every round) under `results/raw/<version>/<framework>-job<N>.json`.

`latest.json` and the per-version files use the shape
`rullst.benchmarks.latest.v1`, which the Rullst website reads at build time
([website-maintenance.md](https://github.com/Rullst/Rullst/blob/main/docs/src/website-maintenance.md)).
Fields are only ever added to it:

```text
{
  "schema": "rullst.benchmarks.latest.v1",
  "measured_on": "2026-11-15",                 date the measurement started (UTC)
  "results": [                                 implementations that were measured
    {
      "framework": "Rullst",                   display name; a non-default variant is appended,
                                               e.g. "Rullst (minimal)"
      "version": "13.0.0-alpha.5",             measured framework version
      "json_rps": 90485.7,                     Tier 1 /json req/s (median of rounds)
      "db_single_rps": 16186.7,                Tier 1 /db-single req/s
      "avg_latency_ms": 1.21,                  Tier 1 /json mean latency
      "peak_ram_mib": 20.8,                    Tier 3 peak RAM
      "vs_axum": { "json_rps": 0.93, ... },    ratios to Axum on the same runner
      "load_generator_bound_rounds": { "json_rps": 5, ... },
      "slug", "name", "variant", "default_variant", "language", "group", "package",
      "framework_version", "versions": { "<package>": "<version>" },
      "runtime", "server", "workers", "database_layer", "template_engine", "logging",
      "maturity_note", "status", "problem", "is_baseline" (Axum only),
      "role": "ranked",                        ranked, diagnostic or control (bench.json), with
      "role_note", "structure_note", "jit",    the folder's notes and its warm-up class
      "dependency_source": { "kind", "label", "raw" },   Rullst rows: crates.io or a git revision
      "jobs": [ { "job", "status", "rounds", "cpu_model", "runner", "round_orders" } ],
      "runners": ["<cpu model>", ...],         the CPU model of each measured job
      "endpoints": ["text", ...],              the endpoints the implementation serves (bench.json)
      "metrics": { "<metric>": { "median", "min", "max", "spread", "n" } },
      "ratios":  { "<metric>": { "median", "min", "max", "spread", "n" },   pooled over every job
                   "tier1.<endpoint>.capacity": { ..., "pairs", "cpu_rounds", "not_comparable_rounds",
                                 "postgresql_rounds", "load_generator_rounds" } },   capacity ratios
                                               (How the scores are computed)
      "flags": { "rounds", "crashed_rounds", "ram_growing_rounds", "client_bound_rounds": { ... },
                 "limited_rounds": { "<run>": { "postgresql": n, "load-generator": n } },
                 "warmup_errors": { "<endpoint>": n } },
      "paired_baseline": { "<metric>": median },   Axum's medians from the same jobs (same runners)
                                               for tier1.<endpoint>.rps, tier2.rps, tier4.rps,
                                               tier3.load_ram_peak_mib and startup_s
      "rps_per_mib", "build", "environment"
    }
  ],
  "not_measured": [ same fields, no metrics; "status" is failed-conformance,
                    build-failed or missing and "problem" says why ],
  "metrics": { "<field>": "<definition>" },
  "auto_update": "...",
  "rullst_version": "13.0.0-alpha.5",
  "rullst_source": { "kind": "crates.io", ... },   where the measured Rullst came from
  "note": "...",                               a note about this Rullst version
                                               (bench/notes.json), or ""
  "note_pt_br": "...",                         the same note in Brazilian Portuguese, or ""
  "measured_from", "measured_to", "generated_at",   ISO 8601 UTC
  "run": { "id", "url", "sha", "event", "rounds", "jobs_per_framework", "jobs" },
  "runners": [ { "cpu_model", "jobs" } ],     how many jobs ran on each CPU model
  "publication_gate": { "passed", "problems": [...] },   why these results could not be published
                                               automatically (empty when they could)
  "baseline": "axum",
  "config": { tiers, server limits, pool size, load generator, database },
  "environment": { "cpu_model", "cpu_count", "memory_total_mib", "kernel", "os",
                   "runner_image", "docker", "load_generator", "postgres", "cpu_split" },
  "rankings": {                                per-category positions (bench/rankings.py)
    "reference": "axum",                       listed with score 1.0 and no position
    "tie_margins": { "<category>": { "margin", "percent", "scores" }, "overall": ... },
                                               from the A/A control: term (a) of the tie margins,
                                               in natural-log units, as a percentage, and the
                                               control's scores
    "tie_tolerance": 0.012,                    the overall A/A margin (null without A/A data)
    "startup_resolution_s": 0.25,              readiness check interval: start-up times this close
                                               share a position
    "settings": { "publish_overall", "max_error_rate", "memory_floor_mib", "startup_floor_s" },
    "method": { ... },                         the rules in words
    "categories": [                            hello, database, application, memory, startup, in that
                                               order
      {
        "key": "hello", "title": "Hello world", "tier": "Tier 1", "kind": "throughput",
        "description": "...", "runs": ["tier1.text", ...], "metrics": ["tier1.text.rps", ...],
        "lower_is_better": false,              true for memory and startup (costs)
        "tie_margin": { "margin", "percent", "scores" },   the A/A margin, as in tie_margins
        "tie_rule": { "aa_margin", "aa_percent", "floor", "floor_percent", "floor_from", "ranked" },
                                               the A/A margin and the pooled floor (natural-log
                                               units and percentages), how many ranked rows the
                                               floor comes from, and how many rows are ranked
        "entries": [                           scored rows by score, then the others
          {
            "slug", "framework",               "framework" as in results[]
            "position": 1,                     1, 1, 3 for a tie; null for every row that is not
                                               "ranked"
            "status": "ranked",                ranked, reference, diagnostic, A/A control,
                                               incomplete, not comparable, errors or not measured
            "role_note": "",
            "tie": true, "tied_with": ["<slug>", ...],   ranked rows sharing the position
            "score": 0.99,                     higher is better, Axum = 1.0; throughput categories:
                                               from the capacity ratios
            "ratio": 0.99,                     the requests/s ratio (throughput), or the RAM or
                                               start-up time ratio
            "within_reference_margin": true,   the score is within reference_margin of 1.00
            "reference_margin": { "margin", "percent" },   the largest of the A/A margin, the
                                               effective spread and the floor
            "spread": { "jobs", "scores", "cpu_models", "own", "own_percent", "same_cpu",
                        "effective", "effective_percent", "basis" },   the score of each scored job
                                               with its CPU model, the half-range of their
                                               logarithms ("own"), and the spread the margins use
                                               ("effective": own, or the floor; "basis" says which)
            "tie_check": { "against", "margin", "percent", "gap_percent", "tied", "group_spread_of" },
                                               the comparison that set the position: with the best
                                               score of the group above (absent for the first
                                               position); group_spread_of names the member whose
                                               wider spread it used, if any
            "efficiency_runs": ["tier1.json", ...],   runs scored by CPU efficiency
            "limited_runs": { "<run>": { "postgresql": n, "load-generator": n } },
            "client_bound", "client_bound_runs",   kept for older readers
            "detail": { ... },                 throughput: rps_ratio, capacity and basis per
                                               endpoint, error_rates, db_us_per_request and
                                               db_us_ratio; memory: value, reference, floor,
                                               peak_ram_mib; startup: value, reference, floor,
                                               startup_s
            "error_runs": { "<endpoint>": rate },   runs above the error limit
            "reason": ""                       why a row has no score
          }
        ]
      }
    ],
    "stability": { "key": "stability", "title", "tier", "description",
                   "entries": [ { "slug", "framework", "status", "result": "pass", "reasons": [...],
                                  "detail": { "tier2": {...}, "tier4": {...}, "crashed_rounds",
                                              "ram_growing_rounds", "rounds" } } ] },
    "publish_overall": false,                  when true, "overall" and "sensitivity" are included:
    "overall": { "weights": {...}, "tie_rule": {...}, "entries": [ { "slug", "framework", "position",
                 "status", "tie", "tied_with", "score", "categories", "missing", "stability", "reason",
                 "spread", "tie_check" } ] },
    "sensitivity": [ { "key", "title", "weights", "tie_rule", "entries": [ ... ] } ]   positions
                                               under other weightings
  },
  "results_schema": 1
}
```

`versions.json` (`rullst.benchmarks.versions.v1`) lists every measured Rullst
version with its date, run, file name and the headline medians and ratios of
the Rullst variants and Axum.

Metric names: `tier1.<endpoint>.rps`, `tier1.<endpoint>.latency_ms.mean`, `tier1.<endpoint>.latency_ms.p50`,
`tier1.<endpoint>.latency_ms.p99`, `tier1.<endpoint>.error_rate`,
`tier1.<endpoint>.server_cpu_cores`, `tier1.<endpoint>.rps_per_cpu` (server
efficiency, requests per server CPU-second), `tier1.<endpoint>.db_cpu_cores`
(PostgreSQL's CPU use), `tier1.<endpoint>.db_us_per_request` (PostgreSQL's
CPU microseconds per request), `tier1.<endpoint>.cpu_us_per_request` (the
server's and PostgreSQL's together), `tier1.<endpoint>.total_rps_per_cpu`
(requests per CPU-second of both) (all twelve endpoints); `tier2.rps`, `tier2.latency_ms.p50`,
`tier2.latency_ms.p99`, `tier2.error_rate`, `tier2.timeouts`,
`tier2.server_cpu_cores`, `tier2.rps_per_cpu`; `tier3.idle_ram_mib`,
`tier3.idle_cpu_cores`, `tier3.load_ram_peak_mib`, `tier3.load_cpu_cores`,
`tier3.rps`; `tier4.rps`, `tier4.latency_ms.p99`, `tier4.error_rate`,
`tier4.transport_errors`, `tier4.timeouts`, `tier4.server_cpu_cores`,
`tier4.rps_per_cpu`, `tier4.ram_mid_mib`, `tier4.ram_end_mib`,
`tier4.ram_growth_mib`; `startup_s`, `idle.tasks`, `after.ram_mib`,
`after.memory_peak_mib`. RAM is in MiB, latency in milliseconds, CPU in
cores, error rates as fractions. `ratios` has no entries for error counts and
rates or for PostgreSQL's CPU use; for Axum, whose ratios are 1 by definition,
it is empty. New fields may be added; a breaking change gets a new `schema`
name.

## Implementations

| Group | Implementation | Folder |
| --- | --- | --- |
| Rust | Axum (baseline) | [frameworks/axum](frameworks/axum) |
| Rust | Axum, A/A control (an identical copy; unranked) | [frameworks/axum-control](frameworks/axum-control) |
| Rust | Axum, SQLx `test_before_acquire` off (diagnostic; unranked) | [frameworks/axum-no-ping](frameworks/axum-no-ping) |
| Rust | Rullst, as generated | [frameworks/rullst](frameworks/rullst) |
| Rust | Rullst, minimal (diagnostic; unranked) | [frameworks/rullst-minimal](frameworks/rullst-minimal) |
| Rust | Actix Web | [frameworks/actix](frameworks/actix) |
| Rust | Loco | [frameworks/loco](frameworks/loco) |
| Rust | Topcoat (early 0.x) | [frameworks/topcoat](frameworks/topcoat) |
| Full-stack frameworks | Ruby on Rails | [frameworks/rails](frameworks/rails) |
| Full-stack frameworks | Laravel | [frameworks/laravel](frameworks/laravel) |
| Full-stack frameworks | Django | [frameworks/django](frameworks/django) |
| Full-stack frameworks | Phoenix | [frameworks/phoenix](frameworks/phoenix) |
| Full-stack frameworks | Spring Boot | [frameworks/spring-boot](frameworks/spring-boot) |
| Full-stack frameworks | ASP.NET Core | [frameworks/aspnet-core](frameworks/aspnet-core) |
| Full-stack frameworks | NestJS | [frameworks/nestjs](frameworks/nestjs) |
| Popular references | FastAPI | [frameworks/fastapi](frameworks/fastapi) |
| Popular references | Fastify | [frameworks/fastify](frameworks/fastify) |
| Popular references | Gin | [frameworks/gin](frameworks/gin) |

Each folder's README describes its configuration. The results list the exact
versions that were measured.

## Reproduce

On GitHub: fork the repository, open **Actions → Benchmark → Run workflow**,
and choose the frameworks (folder names, or `all`), the number of rounds, the
jobs per implementation and, optionally, a published `rullst` version.

On a Linux machine with Docker, cgroup v2, Python 3.10+ and at least 4 CPUs
(builds and load tests are heavy; 8 GiB of RAM or more is advisable):

```sh
export WRK="$(bench/install-loadgen.sh "$HOME/.local/bin")"  # builds wrk 4.2.0 (make, cc, OpenSSL headers)
python3 bench/harness.py conformance --framework rullst
python3 bench/harness.py run --framework rullst --rounds 1 --job 1 --out out/rullst-job1.json
python3 bench/aggregate.py --input out --summary report.md
```

Numbers from other hardware are not comparable with the published ones,
except as ratios to Axum measured on the same machine.

## History

**v1, v2 and v3.** v1 is the measurement made by hand on a laptop on 22 June
2026, kept in [history/2026-06-22-laptop.md](history/2026-06-22-laptop.md)
with an explanation of why it is not comparable. v2, the GitHub Actions
rebuild of 15 November 2026 (the results up to Rullst 13.0.0-alpha.5),
measured only `/text`, `/json`, `/db-single` (always the row with id = 1)
and `/html`. Its `/db-single` tier was client-bound in most rounds, because
PostgreSQL shared the client vCPUs with the load generator, and its README
table mixed absolute numbers from different runners. v3 (November 2026)
adds `/queries`, `/updates` and `/fortunes`, measures server efficiency and
PostgreSQL's CPU use in every run, scores client-bound runs by efficiency
(giving PostgreSQL its own vCPU was measured and did not remove the
client-bound runs), and leads the table with ratios, showing each absolute
number with Axum's from the same runner, as described in [Method](#method)
and [CPU split](#cpu-split). v3's second phase adds `GET /world/{id}`,
`GET /worlds`, `PUT /world/{id}`, `POST /form` and `GET /me` (request input,
validation, a write, CSRF and sessions), the Application category and the
hot-rows contention run, and replaces the load generator: **v3 numbers come
from wrk 4.2.0, v2 numbers from bombardier 2.0.2, so absolute requests/s and
latencies before and after are not comparable** (wrk needs less client CPU
per request, which raises client-bound results most). Ratios to Axum are
always measured with the same tool in the same job.

**v3 scoring revision (19 November 2026).** After an independent review of
the first full v3 trial, the scoring was rebuilt: client-bound runs are
compared by requests per CPU-second of the server **and PostgreSQL**
(PostgreSQL's cost was left out before), a load-generator-bound run whose
server used less than 75% of its vCPUs is not comparable, the 1% error limit
applies to every scored run, ties come from an A/A control instead of being
exact, Hello world replaces Speed (`/db-single` moved to Database), Tiers 2
and 4 became a pass/fail Stability check, Memory and Startup got floors,
Rullst's minimal configuration became an unranked diagnostic, the overall
ranking became optional (off), each endpoint is warmed up just before its
run (longer for JIT runtimes), rounds run in ABBA order, every
implementation runs on 2 jobs by default, and conformance gained a
concurrent step. Rankings from before the revision are not comparable with
later ones.

**Tie margins from the spread between jobs (20 November 2026).** A
validation trial gave A/A margins of 0.03-0.33%, while the same
implementations' ratios to Axum differed much more between trials on
different CPU models (NestJS's `/json`: 0.45× on a Xeon 6975P-C, 0.31× on an
EPYC 7763), so a 10-20% gap between two implementations measured on
different CPUs could be ranked as a difference. Ties now also use each
implementation's spread between its jobs and a pooled floor
([How the scores are computed](#how-the-scores-are-computed)), and the
official run measures every implementation on 3 jobs instead of 2. Positions
from before this change are not comparable with later ones.

## License

[MIT](LICENSE)
