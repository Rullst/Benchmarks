# Rullst Benchmarks

An HTTP benchmark suite that compares [Rullst](https://github.com/Rullst/Rullst)
with other web frameworks under the same conditions. Every number is measured
by a GitHub Actions workflow on GitHub-hosted runners, so anyone can rerun it,
and every number on this page is generated from the measurement output.

- Dashboard: <https://rullst.win/Benchmarks/>
- Full results tables: [benchmarks_results.md](benchmarks_results.md)
- Machine-readable results: <https://rullst.win/Benchmarks/data/latest.json> (see [Machine-readable results](#machine-readable-results))

## What this benchmark does not measure

- **Request input.** Route parameters, query strings (other than `queries`
  on `/queries` and `/updates`), forms and request bodies, and validation.
- **Sessions and authentication.** Not measured; they are planned, with
  request input, for a second phase that is being designed separately.
- **Real deployments.** No TLS and no network latency: client, server and
  database share a single small virtual machine (4 vCPUs, 2 of them for the
  server) and talk over loopback. Tiers are short (10 s to 2 minutes).
- **Servers faster than the load generator.** When a run is client-bound
  (the load generator or PostgreSQL used its vCPUs fully), its requests/s
  measure the load generator rather than the server. The rankings compare
  such runs by server efficiency instead, and flag a run as not comparable
  when that is not possible ([Rankings and client-bound runs](#rankings-and-client-bound-runs)).

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
measure framework overhead; the last three, added in November 2026, follow
the [TechEmpower Framework Benchmarks](https://github.com/TechEmpower/FrameworkBenchmarks/wiki/Project-Information-Framework-Tests-Overview)
(round 23) multiple-queries, updates and fortunes tests and measure database
work through the framework's ORM and template engine:

| Endpoint | Response |
| --- | --- |
| `GET /text` | `Hello World`, `text/plain` |
| `GET /json` | `{"message":"Hello World"}`, `application/json` |
| `GET /db-single` | the row with `id = 1` of the `world` table, read from PostgreSQL on every request, as `{"id":1,"randomNumber":N}`, `application/json` |
| `GET /html` | `<!DOCTYPE html><html><head><title>Benchmark</title></head><body><h1>Hello World</h1></body></html>`, `text/html`, rendered by the framework's template engine with `World` passed as a variable |
| `GET /queries?queries=N` | N random rows of `world` (ids 1 to 10,000), each read with its own query, as a JSON array of `{"id":…,"randomNumber":…}`, `application/json`. N is clamped to 1-500; a missing or invalid value counts as 1. Measured with N = 20 |
| `GET /updates?queries=N` | N random rows, each read with its own query, given a new random `randomNumber` (1-10,000), written back to the database before the response, and returned as for `/queries`. Writing the rows in a batch or a transaction is allowed (TechEmpower's rules); each folder README says what its implementation does. Measured with N = 20 |
| `GET /fortunes` | every row of the `fortune` table (TechEmpower's 12 rows, one of them a `<script>` and one in Japanese) plus one added at request time (id 0, `Additional fortune added at request time.`), sorted by message and rendered as an HTML table by the framework's template engine, which escapes the messages; `text/html; charset=utf-8` |

The tiers:

| Tier | Load | Reported |
| --- | --- | --- |
| 1 | 125 connections for 10 s on each endpoint | requests/s, p50 and p99 latency, errors, server CPU, server efficiency, PostgreSQL CPU |
| 2 | 300 connections for 30 s on `/json` | requests/s, p50 and p99 latency, errors and timeouts, server efficiency |
| 3 | idle for 10 s, then 200 connections for 15 s on `/json` | idle and peak RAM, idle and loaded CPU |
| 4 | 500 connections for 2 minutes on `/json` | requests/s, p99, errors and timeouts, server efficiency, RAM growth, whether the server stopped |

**Server efficiency** is requests per server CPU-second: the requests/s of a
load run divided by the server's CPU use during it, in cores (both are
measured in every run). It is what a request costs the server, and it stays
comparable when the load generator or the database, not the server, was the
limit. Tiers 2 to 4 stay on `/json`: they measure behaviour under more
connections, memory and stability, which the database endpoints would mostly
turn into a measurement of PostgreSQL on the shared vCPUs.

Each metric is also reported as a ratio to the Axum baseline measured on the
same runner (see below). The results also list requests/s per MiB of peak RAM
as one column; it is not used to rank anything.

The rankings under [Results](#results) are computed by `bench/rankings.py`
from those ratios: one per category (Speed, Database, Under pressure, Memory,
Endurance, Startup) and an overall one, the geometric mean of the six category
scores with equal weights. The weighting is a choice; the per-category
rankings are the detail. In the throughput categories (Speed, Database, Under
pressure, Endurance) each run counts with its requests/s ratio, or with its
server efficiency ratio when either server's run was client-bound (see
[Rankings and client-bound runs](#rankings-and-client-bound-runs)), so
client-bound results get positions instead of ties. Equal scores, and
start-up times within the 0.25 s readiness check interval, share a position.
An implementation with a missing or left-out result, or one that does not
serve an endpoint yet, is listed as incomplete in that category and overall,
without a position.

## Method

Each framework is measured by its own job on a GitHub-hosted `ubuntu-latest`
runner (4 vCPUs, 16 GiB of RAM). The job records `lscpu`, the kernel, the
memory, the Docker version, image digests and tool versions with the results.

1. **Build.** The job builds the framework's image and the Axum baseline's
   image from their folders under `frameworks/`, with pinned base images and
   lockfiles.
2. **Database.** PostgreSQL 18.6 (image pinned by digest) starts with a
   `world` table of 10,000 rows and the 12-row `fortune` table
   ([bench/db/init.sql](bench/db/init.sql)), with `synchronous_commit = off`
   (as in TechEmpower's configuration: `/updates` measures the writes, not
   the runner's disk flushes) and `pg_stat_statements` loaded.
3. **Conformance.** Each implementation is started and checked: status, media
   type and body of every endpoint, HTTP/1.1 keep-alive, and that
   `/db-single` follows changes made to the row between requests (so it reads
   the database every time). For `/queries`, `/updates` and `/fortunes`,
   `pg_stat_statements` counts the statements each request runs: each row
   must be read by its own `SELECT`, the updated rows must be in the
   database, and `/fortunes` must read the table on every request without
   `ORDER BY` (the rules are in [CONTRIBUTING.md](CONTRIBUTING.md)). Statement
   tracking is then turned off for the measurement. An implementation that
   fails is reported as failed with the reason and is not measured.
4. **Rounds.** The framework and Axum then alternate for 5 rounds (framework,
   Axum, framework, Axum, …). Each round restores the `world` table to its
   initial values and rewrites it (`VACUUM FULL`, so earlier `/updates` runs
   leave no dead rows behind), starts a fresh container, waits for it to
   answer, measures it idle, warms up each endpoint for 5 s and runs the
   four tiers. Results are the median over rounds, with the lowest and
   highest round shown as the spread.
5. **Ratios.** For every round, each metric of the framework is divided by
   Axum's value from the adjacent round on the same runner; the reported ratio
   is the median of those per-round ratios. Runner-to-runner differences (CPU
   model, noisy neighbours) largely cancel out in the ratio, so compare ratios
   rather than absolute numbers across jobs and runs.

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
- **Load generator.** [bombardier](https://github.com/codesenberg/bombardier)
  2.0.2 with its fasthttp client, downloaded from its release and checked by
  SHA-256, with a 5 s request timeout. It runs as a host process pinned to the
  client vCPUs.
- **Database pool.** 16 connections per server (`DB_POOL_SIZE`), split
  across processes for multi-process servers.
- **Workers.** Sized for the 2 vCPUs the server has (`BENCH_WORKERS=2`), the
  way each framework's production guidance says to size them.
- **Logging.** Off. Where a framework cannot turn off its access log, it
  stays on and the folder README says so. Container output is discarded
  (`--log-driver none`) during measurement.
- **RAM** is the container's cgroup `memory.current` minus inactive file
  cache (what `docker stats` shows), sampled every 100 ms. CPU is the
  container's cgroup CPU time, in cores (2.00 means both vCPUs busy).

Flags in the results:

- **client-bound**: the client vCPUs (load generator and PostgreSQL) were at
  least 90% busy during the test. The server might have answered more
  requests than the load generator could send, so its requests/s understate
  it; the rankings use its server efficiency instead (below).
- **RAM still growing**: in Tier 4, RAM rose by more than 10% and 8 MiB
  between the middle and the last tenth of the test. For garbage-collected
  runtimes this can be heap growth rather than a leak.
- **stopped**: the server process exited (crash or out-of-memory kill) during
  a round. The phase is reported.

### Rankings and client-bound runs

With 2 client vCPUs, the load generator (and, on the database endpoints,
PostgreSQL) cannot saturate the fastest servers: their runs are client-bound
and their requests/s mostly measure the client side. Calling close
client-bound results ties hid real differences in what each request costs, so
the rankings compare those runs by server efficiency:

- for every round pair (the framework's round and the adjacent Axum round),
  the run's **capacity ratio** is the requests/s ratio when neither run was
  client-bound, and the ratio of requests per server CPU-second when either
  was (`<run>.capacity` in `results[].ratios`, with `efficiency_rounds`
  counting the round pairs that used efficiency);
- a category's score is the geometric mean of its runs' capacity ratios
  (medians over the rounds); a "*" in the rankings table marks a score where
  a run used efficiency in at least half of the round pairs;
- a run that was client-bound in most rounds for both the implementation and
  its paired Axum run, and that efficiency could not score (no server CPU
  measurement, as in results from before November 2026), would compare two
  load generators: the category lists the implementation as **not
  comparable**, without a position, and it has no overall position.

When the server is the limit, both measures agree: it uses both of its vCPUs,
so requests/s is efficiency times two. When it is not, efficiency is the
better estimate of what it could serve, with one caveat: efficiency changes
somewhat with the load (see [CPU split](#cpu-split)), so it compares servers
best when both carry a similar load.

### CPU split

PostgreSQL shares the 2 client vCPUs with the load generator. On the
database endpoints both compete for them, so most `/db-single` runs were
client-bound. Giving PostgreSQL a vCPU of its own (server 2, load generator 1,
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
endpoints are limited by PostgreSQL, which the results show as client-bound
with PostgreSQL's CPU use next to them, and the rankings compare those runs
by server efficiency. `BENCH_DATABASE_CPUS=1` (or `database.cpus` in
`bench/config.json`) reproduces the other split.

The same runs show how much efficiency depends on the load: with less load
(own-vCPU split), Axum's efficiency was 9-14% lower on `/text`, `/json` and
`/html` and 26-28% higher on `/queries` and `/updates`. Efficiency ratios
compare servers well when both run at similar loads, which the alternating
rounds on one runner give; small efficiency differences between
implementations whose loads differ a lot are not significant.

## Fairness

- Each implementation follows its own framework's production
  recommendations: release or production build, pinned versions and
  lockfiles, the framework's standard database layer (its ORM where it has
  one) and template engine, and its documented way to run in production.
- Each folder has a README that says how the implementation is configured
  and why.
- Rullst is not tuned more than the others. It is measured twice: **as
  generated** by `cargo rullst new` and `cargo rullst deploy` (its default
  production middleware included), and **minimal** (its router, ORM and
  `html!` served without that middleware, comparable to the Axum app).
- Improvements from people who use a framework in production are welcome;
  see [CONTRIBUTING.md](CONTRIBUTING.md).

## Limitations

- **Shared, virtual runners.** GitHub-hosted runners are virtual machines on
  shared hosts. Absolute numbers differ between runs and between jobs of the
  same run; the per-round ratio to Axum reduces this but does not remove it.
  Small differences (a few percent) are within the noise.
- **The load generator limits the top.** With 2 vCPUs, the load generator
  (and PostgreSQL on the database endpoints) cannot saturate the fastest
  servers. Those results are flagged client-bound, and the rankings compare
  them by server efficiency, which is measured on a server that was not
  saturated.
- **Short tiers.** Tests last 10 s to 2 minutes, with a 5 s warm-up per
  endpoint. They do not show long-term stability, and runtimes with a JIT
  compiler may not reach their best speed.
- **One small machine.** Client, server and database share one virtual
  machine and talk over loopback: no network latency, no TLS, HTTP/1.1 with
  keep-alive only.
- **Small endpoints.** `/text`, `/json`, `/db-single` and `/html` measure
  framework overhead (routing, serialization, ORM, templates, middleware).
  `/queries`, `/updates` and `/fortunes` add database work through the ORM
  and a template over database rows, but they are still small, fixed
  workloads on a 10,000-row table; a real application's code and data
  usually dominate. Tiers 2 to 4 use `/json` only.
- **One configuration per framework.** Experts may know better settings; the
  folders document the choices so they can be challenged.

## Automatic updates

A nightly check (01:00 UTC-3) reads the newest `rullst` version on crates.io,
prereleases included. When that version has not been measured yet, the
workflow measures every implementation with it and commits the results to
`main`: this README's table, [benchmarks_results.md](benchmarks_results.md) and
the JSON files under [results/](results/). The dashboard is then rebuilt. Each
measured Rullst version keeps its own results file, so the history shows how
Rullst's numbers change between releases. If Rullst cannot be built or fails
conformance with the new version, nothing is published, the failure is
recorded in `results/attempts.json` and the workflow run fails, so a
maintainer can fix the benchmark app and rerun it by hand.

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
output (every round) under `results/raw/<version>/`.

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
      "endpoints": ["text", ...],              the endpoints the implementation serves (bench.json)
      "metrics": { "<metric>": { "median", "min", "max", "spread", "n" } },
      "ratios":  { "<metric>": { "median", "min", "max", "spread", "n" },
                   "<run>.capacity": { ..., "efficiency_rounds" } },   capacity ratios (see Rankings
                                               and client-bound runs); runs: tier1.<endpoint>, tier2, tier4
      "flags": { "rounds", "crashed_rounds", "ram_growing_rounds", "client_bound_rounds": { ... } },
      "paired_baseline": { "<metric>": median },   Axum's medians from the same job (same runner) for
                                               tier1.<endpoint>.rps, tier2.rps and tier4.rps
      "rps_per_mib", "build", "environment"
    }
  ],
  "not_measured": [ same fields, no metrics; "status" is failed-conformance,
                    build-failed or missing and "problem" says why ],
  "metrics": { "<field>": "<definition>" },
  "auto_update": "...",
  "rullst_version": "13.0.0-alpha.5",
  "note": "...",                               a note about this Rullst version
                                               (bench/notes.json), or ""
  "note_pt_br": "...",                         the same note in Brazilian Portuguese, or ""
  "measured_from", "measured_to", "generated_at",   ISO 8601 UTC
  "run": { "id", "url", "sha", "event", "rounds" },
  "baseline": "axum",
  "config": { tiers, server limits, pool size, load generator, database },
  "environment": { "cpu_model", "cpu_count", "memory_total_mib", "kernel", "os",
                   "runner_image", "docker", "load_generator", "postgres", "cpu_split" },
  "rankings": {                                per-category and overall positions (bench/rankings.py)
    "reference": "axum",                       listed with score 1.0 and no position
    "tie_tolerance": 0.0,                      0 since client-bound runs are scored by efficiency
                                               (it was 0.1 when close client-bound scores tied)
    "startup_resolution_s": 0.25,              readiness check interval: start-up times below it count
                                               as equal, and times this close share a position
    "method": { "overall", "ratios", "ties", "incomplete", "reference" },   the rules in words
    "categories": [                            speed, database, pressure, memory, endurance, startup, in
                                               that order
      {
        "key": "speed", "title": "Speed", "tier": "Tier 1", "description": "...",
        "metrics": ["tier1.text.rps", ...],    the ratios the score is computed from
        "lower_is_better": false,              true for memory and startup (the score is inverted)
        "entries": [                           ranked and reference rows by score, then the others
          {
            "slug", "framework",               "framework" as in results[]
            "position": 1,                     1, 1, 3 for a tie; null for the reference, incomplete
                                               and not measured rows
            "status": "ranked",                ranked, reference, incomplete or not measured
            "tie": true, "tied_with": ["<slug>", ...],   rows sharing the position (the reference too)
            "score": 0.99,                     higher is better, Axum = 1.0; null without a position;
                                               throughput categories: from the capacity ratios
            "ratio": 0.99,                     the measured ratio to Axum (requests/s ratio, peak RAM
                                               ratio for memory, start-up time ratio for startup)
            "client_bound": true,              every run of the category client-bound in at least
                                               half of the rounds (throughput categories only)
            "client_bound_runs": ["tier1.json", ...],
            "efficiency_runs": ["tier1.json", ...],   runs scored by efficiency in at least half of
                                               the round pairs
            "detail": { ... },                 speed and database: the endpoints' requests/s ratios and
                                               "capacity"; pressure: rps, p99_ms,
                                               p99_ratio; memory: peak_ram_mib; endurance: rps,
                                               error_rate, timeouts, ram_growing_rounds,
                                               crashed_rounds, rounds; startup: startup_s
            "reason": ""                       why an incomplete or not measured row has no position
          }
        ]
      }
    ],
    "overall": {
      "weights": { "speed": 0.1667, ... },     geometric mean of the category scores, equal weights
      "entries": [ { "slug", "framework", "position", "status", "tie", "tied_with",
                     "score", "categories": { "<key>": score or null }, "missing": [keys], "reason" } ]
    }
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
(PostgreSQL's CPU use) (endpoints `text`, `json`, `db-single`, `html`,
`queries`, `updates`, `fortunes`); `tier2.rps`, `tier2.latency_ms.p50`,
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
| Rust | Rullst, as generated | [frameworks/rullst](frameworks/rullst) |
| Rust | Rullst, minimal | [frameworks/rullst-minimal](frameworks/rullst-minimal) |
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
and choose the frameworks (folder names, or `all`), the number of rounds and,
optionally, a published `rullst` version.

On a Linux machine with Docker, cgroup v2, Python 3.10+ and at least 4 CPUs
(builds and load tests are heavy; 8 GiB of RAM or more is advisable):

```sh
export BOMBARDIER="$(bench/install-bombardier.sh "$HOME/.local/bin")"
python3 bench/harness.py conformance --framework rullst
python3 bench/harness.py run --framework rullst --rounds 1 --out out/rullst.json
python3 bench/aggregate.py --input out --summary report.md
```

Numbers from other hardware are not comparable with the published ones,
except as ratios to Axum measured on the same machine.

## History

**v1 and v2.** v1 (the results up to Rullst 13.0.0-alpha.5) measured only
`/text`, `/json`, `/db-single` (always the row with id = 1) and `/html`. Its
`/db-single` tier was client-bound in most rounds, because PostgreSQL shared
the client vCPUs with the load generator, and its README table mixed
absolute numbers from different runners. v2 (November 2026) adds `/queries`,
`/updates` and `/fortunes`, measures server efficiency and PostgreSQL's CPU
use in every run, scores client-bound runs by efficiency (giving PostgreSQL
its own vCPU was measured and did not remove the client-bound runs), and
leads the table with ratios, showing each absolute number with Axum's from
the same runner, as described in [Method](#method) and [CPU split](#cpu-split).

The suite was rebuilt in November 2026. The results published before that
(measured by hand on a laptop on 22 June 2026) are kept in
[history/2026-06-22-laptop.md](history/2026-06-22-laptop.md) with an
explanation of why they are not comparable.

## License

[MIT](LICENSE)
