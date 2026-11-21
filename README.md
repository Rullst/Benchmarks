# Rullst Benchmarks

An HTTP benchmark suite that compares [Rullst](https://github.com/Rullst/Rullst)
with other web frameworks under the same conditions. Every number is measured
by a GitHub Actions workflow on GitHub-hosted runners, so anyone can rerun it,
and every number on this page is generated from the measurement output.

- Dashboard: <https://rullst.win/Benchmarks/>
- Full results tables: [benchmarks_results.md](benchmarks_results.md)
- Machine-readable results: <https://rullst.win/Benchmarks/data/latest.json> (see [Machine-readable results](#machine-readable-results))

## How to read these results

- **1.00× is Axum.** Every score divides a framework's result by the result
  of Axum, a small Rust framework used as the reference, measured on the same
  machine in alternating rounds. 0.50× is half of Axum's result and 2.00×
  twice. Higher is better in every score: for memory and start-up time the
  ratio is turned around, so a higher score means less RAM or a faster start.
- **Ties and ±.** The machines are shared cloud machines, so results vary
  from run to run. "±6%" next to a score is the margin within which two scores
  cannot be told apart. Scores that close share a range of positions, such as
  "3–7": those implementations are in positions 3 to 7 in no particular order.
- **The categories answer different questions.** Hello world: what a framework
  costs per request when the page is trivial. Database: how it reads, writes
  and renders rows. Application: what it does with a real request (input,
  validation, a write, a form with CSRF protection, a signed-in user). Memory:
  how much RAM it needs under load. Startup: how fast it starts. Stability
  (pass or fail): whether it keeps working under heavier load.
- **The database usually comes first.** In a real application the database
  is usually the limit before the framework is, so a large gap in Hello world
  shrinks or disappears once requests read and write data; Database and
  Application are closer to what an application does.
- **The overall score is a summary.** It combines the five category scores,
  with Hello world, Database and Application counted twice and Memory and
  Startup once, for quick reading. The categories are the real result: other
  weights change the order, as the table under the rankings shows.

## What this means for Rullst

<!-- reading:start -->
Rullst as `cargo rullst new` generates it (13.0.0-alpha.6, with its production middleware) is in positions 4–5 of 14 in the overall score, at 0.75× Axum (Axum = 1.00); in the same group as Loco (0.77×); the closest scores outside its group are Gin (0.83×, higher) and Fastify (0.61×, lower). By category: Hello world positions 3–6 of 14 (0.50×); Database positions 3–7 of 14 (0.79×); Application positions 4–5 of 14 (0.81×); Memory (high-water mark) positions 1–5 of 14 (1.00×); Startup positions 1–11 of 14 (1.00×). Memory: its RAM high-water mark under the Tier 3 load was 12 MiB (Axum: 17 MiB on the same runners), both counted as the 64 MiB floor of the Memory score; after the 125 logins of the application endpoints its peak was 470 MiB (Axum: 927 MiB), which no score includes. Its Application figure, and through it the overall score, is affected by this run's PUT /world/{id} problem (‡): most of its measured PUT requests did not write, so its PUT ratio and its Application score are higher than they would be with a write. This benchmark is maintained by Rullst's maintainer, who also wrote every implementation in it and designed the method ([Authorship](#authorship)).
<!-- reading:end -->

Deeper performance tests of Rullst alone (CPU and allocation profiles, the
database statements each request runs, the generated middleware stack one
layer at a time, SSE and WebSocket load, and a real-application workload) are
planned for Rullst 13.1 and tracked in
[Rullst's roadmap](https://github.com/Rullst/Rullst/blob/main/ROADMAP.md#next-131).
They are not part of this cross-framework benchmark.

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
  database share a single small virtual machine (4 vCPUs, which are two
  physical cores with two SMT threads each; the server gets both threads of
  one core) and talk over loopback. Tiers are short (10 s to 2 minutes).
- **Memory after logins, in the Memory score.** The Memory score is Tier 3's
  RAM high-water mark, measured before the 125 logins of the application
  endpoints. A memory-hard password hash can leave hundreds of MiB in the
  allocator after them (Axum: about 930 MiB in the first official v3 run);
  that RAM is shown in its own column ("Peak RAM after the 125 logins") and is
  not part of any score.
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
> Measured on 2026-11-20 with **Rullst 13.0.0-alpha.6** (from crates.io) on GitHub-hosted runners (4 vCPUs; each server limited to 2 vCPUs, the two SMT threads of one physical core on every runner, and 2 GiB). Each implementation ran 5 rounds on each of 3 runners (jobs), alternating which side goes first with the Axum baseline measured on the same runner (ABBA); values are medians over every round pair. Runner CPUs per job: EPYC 7763 ×24, Xeon 6975P-C ×9, EPYC 9V74 ×8, Xeon PLATINUM 8573C ×4, EPYC 9V45 ×3, Xeon Platinum 8370C CPU @ 2.80GHz ×2, Xeon 6973P-C ×1; each row names its own. Ratios to Axum (1.00 = Axum) cancel much of the difference between runners, so the tables lead with them, but not all of it: in these results one implementation's score in a category differed between jobs on two CPU models by up to 11% for the Rust and Go implementations (Loco's Hello world score: 0.47 on EPYC 7763, 0.52 on EPYC 9V74) and by up to 70% for the others (Laravel's Hello world score: 0.003 on Xeon 6975P-C, 0.006 on EPYC 7763). The tie margins include these differences. These results update automatically when a new Rullst version is published on crates.io. Last update: 2026-11-21.

Source: [workflow run 44765309608](https://github.com/Rullst/Benchmarks/actions/runs/44765309608). Full tables, ranges and flags: [benchmarks_results.md](benchmarks_results.md); dashboard: <https://rullst.win/Benchmarks/>.

**Database-layer defaults.** The Database and Application rankings partly measure the defaults of each stack's database layer, and they differ: SQLx (Axum, Actix Web, Loco, Rullst) tests each pooled connection with a round trip before handing it out (`test_before_acquire`, on by default; the unranked `axum-no-ping` diagnostic, measured for Axum only, shows its size: in these results Axum scored 1.23 in Database and 1.15 in Application with it switched off); node-postgres (Fastify, NestJS) sends unprepared statements; Laravel on PHP-FPM opens a new PostgreSQL connection for every request; Npgsql (ASP.NET Core) resets a pooled connection's state before each query EF Core runs; GORM (Gin) wraps each write in a transaction by default (`SkipDefaultTransaction` off); Rails uses 6 of its 16 connections. [Fairness](README.md#fairness) and each folder README list the settings that were changed from the defaults, and why.

| Implementation | Version | Language | /json vs Axum | /html vs Axum | /db-single vs Axum | /queries vs Axum | /updates vs Axum | /fortunes vs Axum | /json req/s (Axum) | Idle RAM (MiB) | Peak RAM (MiB) | Runner CPUs |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Axum – baseline | 0.8.9 | Rust | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 126,538 | 1.1 | 17.3 | EPYC 7763 ×24, Xeon 6975P-C ×9, EPYC 9V74 ×8, Xeon PLATINUM 8573C ×4, EPYC 9V45 ×3, Xeon Platinum 8370C CPU @ 2.80GHz ×2, Xeon 6973P-C ×1 |
| Actix Web | 4.19.0 | Rust | 1.17 | 1.15 | 0.99 | 0.97 | 1.00 | 0.80 | 197,090 (165,074) | 2.3 | 11.6 | EPYC 9V45, EPYC 7763, Xeon Platinum 8370C CPU @ 2.80GHz |
| Loco | 1.3.1 | Rust | 0.51 | 0.49 | 0.99 | 0.97 | 0.95 | 0.59 | 69,336 (126,069) | 3.1 | 16.6 | EPYC 9V74, EPYC 7763, Xeon 6975P-C |
| Rullst (as generated) | 13.0.0-alpha.6 | Rust | 0.52 | 0.47 | 0.98 | 0.97 | 0.81 | 0.62 | 59,870 (117,159) | 1.5 | 12.1 | EPYC 7763, EPYC 7763, EPYC 9V74 |
| Topcoat | 0.12.1 | Rust | 0.79 | 0.73 | 1.39 | 1.48 | 1.47 | 0.79 | 145,754 (188,753) | 1.4 | 11.8 | Xeon 6975P-C, EPYC 7763, Xeon PLATINUM 8573C |
| ASP.NET Core | 10.0.15 | C# | 0.53 | 0.34 | 0.32 | 0.75 | 1.19 | 0.23 | 100,996 (188,502) | 30.0 | 126.8 | Xeon Platinum 8370C CPU @ 2.80GHz, Xeon PLATINUM 8573C, EPYC 9V45 |
| Django | 6.1.3 | Python | 0.03 | 0.03 | 0.14 | 0.30 | 0.38 | 0.06 | 3,682 (114,336) | 104.3 | 118.0 | EPYC 7763, EPYC 7763, Xeon PLATINUM 8573C |
| Laravel | 13.42.0 | PHP | 0.01 | 0.00 | 0.02 | 0.18 | 0.29 | 0.01 | 733 (119,406) | 37.5 | 84.1 | EPYC 7763, Xeon 6975P-C, EPYC 7763 |
| NestJS | 12.5.0 | TypeScript | 0.30 | 0.28 | 0.70 | 0.61 | 0.72 | 0.40 | 34,596 (114,917) | 190.9 | 252.3 | EPYC 7763, EPYC 7763, Xeon 6975P-C |
| Phoenix | 1.8.16 | Elixir | 0.16 | 0.14 | 0.72 | 1.22 | 1.33 | 0.40 | 18,470 (113,892) | 136.4 | 158.2 | EPYC 9V45, EPYC 7763, EPYC 7763 |
| Ruby on Rails | 8.1.4.1 | Ruby | 0.01 | 0.01 | 0.11 | 0.71 | 0.73 | 0.07 | 2,480 (162,816) | 103.6 | 402.1 | EPYC 7763, EPYC 9V74, Xeon 6975P-C |
| Spring Boot | 4.1.2 | Java | 0.27 | 0.20 | 0.49 | 1.29 | 1.51 | 0.14 | 63,006 (226,883) | 233.6 | 471.1 | EPYC 7763, Xeon 6975P-C, Xeon 6973P-C |
| FastAPI | 0.163.0 | Python | 0.07 | 0.06 | 0.11 | 0.23 | 0.28 | 0.07 | 12,727 (166,508) | 170.1 | 190.9 | Xeon 6975P-C, EPYC 9V74, EPYC 7763 |
| Fastify | 5.12.8 | JavaScript | 0.44 | 0.32 | 0.72 | 0.67 | 0.77 | 0.62 | 55,421 (126,538) | 101.8 | 169.6 | EPYC 7763, EPYC 9V74, EPYC 9V74 |
| Gin | 1.12.0 | Go | 0.45 | 0.44 | 1.26 | 1.34 | 1.38 | 0.51 | 77,222 (165,719) | 3.8 | 26.1 | EPYC 7763, EPYC 9V74, Xeon PLATINUM 8573C |
| Axum (test_before_acquire off) – diagnostic, unranked | 0.8.9 | Rust | 1.00 | 1.00 | 1.15 | 1.18 | 1.18 | 1.24 | 115,387 (115,310) | 1.2 | 16.8 | EPYC 7763, EPYC 7763, EPYC 7763 |
| Axum (A/A control) – A/A control, unranked | 0.8.9 | Rust | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 118,278 (118,931) | 1.1 | 17.1 | EPYC 7763, Xeon 6975P-C, EPYC 7763 |

Ratios are requests/s divided by Axum's on the same runners (higher is better); the scores in the rankings use capacity ratios instead (see below). "/json req/s (Axum)" is the absolute number, with Axum's on the same runners in brackets: compare absolute numbers only within a row. Peak RAM is the Memory category's high-water mark, measured before the logins of the application endpoints (the next table has the RAM after them). "n/i": not implemented yet. /queries and /updates use queries=20. Runner CPUs: the CPU model of each job (runner) the row was measured on.

| Implementation | GET /world/{id} vs Axum | GET /worlds vs Axum | PUT /world/{id} vs Axum ‡ | POST /form vs Axum | GET /me vs Axum | CSRF | Session store | Peak RAM after the 125 logins (MiB) | Hot rows p99 (ms) | Hot rows errors |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- | ---: | ---: | ---: |
| Axum – baseline | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | token (library) | postgresql (library) | 928 | 13.68 | 0 |
| Actix Web | 0.97 | 0.98 | 0.99 | 1.42 | 1.81 | token (library) | cookie-encrypted (documented) | 696 (928) | 11.32 | 0 |
| Loco | 0.97 | 0.99 | 0.59 | 0.64 | 1.82 | token (library) | cookie-signed (built-in) | 1,045 (929) | 25.05 | 0 |
| Rullst (as generated) | 0.96 | 0.75 | 1.16 ‡ | 0.63 | 0.99 | token (built-in) | postgresql (generator) | 470 (927) | 31.97 | 0 |
| Topcoat | 1.37 | 1.27 | 0.85 | 1.20 | 1.39 | fetch-metadata (built-in) | postgresql (built-in) | 1,040 (928) | 10.41 | 0 |
| ASP.NET Core | 0.34 | 0.42 | 0.38 ‡ | 0.22 | 0.52 | token (built-in) | cookie-encrypted (built-in) | 157 (1,042) | 35.09 | 0 |
| Django | 0.13 | 0.12 | 0.11 | 0.04 | 0.16 | token (built-in) | postgresql (built-in) | 122 (929) | 155.53 | 0 |
| Laravel | 0.02 | 0.02 | 0.02 ‡ | 0.01 | 0.03 | token (built-in) | cookie-encrypted (built-in) | 90 (928) | 587.58 | 0 |
| NestJS | 0.68 | 0.59 | 0.39 | 0.18 | 0.47 | fetch-metadata (built-in) | postgresql (documented) | 299 (927) | 79.47 | 0 |
| Phoenix | 0.74 | 0.74 | 0.77 ‡ | 0.18 | 0.94 | token (built-in) | postgresql (generator) | 160 (928) | 25.08 | 0 |
| Ruby on Rails | 0.11 | 0.12 | 0.13 ‡ | 0.02 | 0.15 | token (built-in) | postgresql (generator) | 408 (965) | 181.66 | 0 |
| Spring Boot | 0.67 | 0.62 | 0.66 ‡ | 0.08 | 1.15 | token (built-in) | memory (built-in) | 489 (929) | 57.35 | 0 |
| FastAPI | 0.11 | 0.10 | 0.10 ‡ | 0.05 | 0.17 | token (documented) | cookie-signed (documented) | 438 (927) | 183.18 | 0 |
| Fastify | 0.73 | 0.69 | 0.75 | 0.29 | 1.33 | token (library) | cookie-encrypted (library) | 177 (928) | 20.67 | 0 |
| Gin | 1.24 | 1.09 | 0.61 | 0.57 | 1.64 | fetch-metadata (stdlib) | cookie-signed (library) | 20 (928) | 45.47 | 0 |
| Axum (test_before_acquire off) – diagnostic, unranked | 1.14 | 1.10 | 1.13 | 1.01 | 1.15 | token (library) | postgresql (library) | 984 (928) | 13.94 | 0 |
| Axum (A/A control) – A/A control, unranked | 1.00 | 1.00 | 1.00 | 0.99 | 1.00 | token (library) | postgresql (library) | 928 (931) | 14.82 | 0 |

Application endpoints (phase 2). CSRF is the design of the form protection (`token`: a secret the form echoes; `fetch-metadata`: `Sec-Fetch-Site`/`Origin` checks) and the session store is each framework's default for a signed-in user, with where the mechanism comes from (built-in, generator, stdlib, documented, library): /form and /me compare those defaults, not one common mechanism. A cookie store reads no database row for /me; a PostgreSQL store (Axum's tower-sessions store included) reads one, which shows in the PostgreSQL CPU per request. Peak RAM after the logins: the server's highest RAM while answering the application endpoints and the hot-rows run, after each round signed its users in (a memory-hard password hash can leave hundreds of MiB in the allocator), with Axum's on the same runners in brackets; the Memory score is measured before the logins and does not include it. Hot rows: PUT /world/{id} on ids 1-10 only, so requests wait for each other's row locks; reported, not ranked.

‡ PUT /world/{id} in this run: the load repeated 10,000 fixed (id, value) pairs that the warm-up had already stored, so an ORM that writes only changed columns answered most measured requests without an UPDATE. The rows marked ‡ are those whose PostgreSQL CPU per PUT was at most 1.10 times their CPU per GET /world/{id} (Rullst (as generated) 0.99, ASP.NET Core 1.01, Laravel 1.03, Phoenix 1.02, Ruby on Rails 1.00, Spring Boot 0.94, FastAPI 0.75, Rullst (minimal) – diagnostic, unranked 1.00; 1.23-2.98 for the other rows, whose PUTs wrote): most of their measured PUTs did not write, so their PUT ratio and their Application score (and through it their overall score) are higher than they would be with a write. Fixed in the next run: every request now carries a new value, and the harness counts the rows each PUT run writes.

### Rankings

- **Hello world (Tier 1):** /text, /json and /html with 125 connections for 10 s each; the score is the geometric mean of the three capacity ratios to Axum.
- **Database (Tier 1):** /db-single, /queries and /updates (20 random rows per request) and /fortunes, with the same 125 connections; the geometric mean of the four capacity ratios.
- **Application (Tier 1):** GET /world/{id}, GET /worlds, PUT /world/{id}, POST /form (CSRF verified) and GET /me (a signed-in session); the geometric mean of the five capacity ratios. /form and /me compare each framework's own default CSRF design and session store (cookie or PostgreSQL), not one mechanism.
- **Memory (Tier 3):** the RAM high-water mark while answering /json with 200 connections for 15 s, measured after the phase-1 Tier 1 runs, Tiers 2 and 4 and an idle period, so it includes memory the server kept from that load; the score is Axum's high-water mark / the implementation's, both counted as at least 64 MiB. It is measured before the logins of the application endpoints: the RAM after them ("Peak RAM after the logins" in the application table) is not part of any score.
- **Startup:** time from starting the container to its first answer; the score is Axum's time / the implementation's, both counted as at least 1 s.
- **Stability (Tiers 2 and 4, not a score):** /json with 300 connections for 30 s and 500 connections for 2 minutes: fail when the server stopped or a round had more than 1% errors (timeouts included); warn when RAM was still growing at the end of Tier 4 (for a garbage-collected runtime that can be heap growth rather than a leak).

Every score is a ratio to Axum (1.00), higher is better. In the throughput categories each run counts with its requests/s ratio when neither server was client-bound, and otherwise with its CPU-cost ratio ("*"): the ratio of requests per CPU-second of the server and PostgreSQL together, so a framework is charged for the PostgreSQL work its queries cause. When both sides were client-bound their requests/s were about equal, and the score compares CPU cost per request, not throughput. A run limited by the load generator while a server used less than 75% of its vCPUs is not comparable. A run with more than 1% errors has no score ("errors"). "≈": within the tie margin of Axum's 1.00 (the largest of the A/A margin, the score's own spread and the pooled floor), so not distinguishable from Axum. A range such as "5–7": scores that cannot be told apart, sharing the positions 5 to 7 in no particular order. Axum, diagnostics and the A/A control have no position. "incomplete": a result is missing or left out.

Tie margins: each implementation has one score per job (runner) in each category; its between-job spread is the half-range of their logarithms. Two scores tie when their gap is at most the largest of (a) the A/A margin (the largest deviation from 1.00 of the A/A control, an identical copy of Axum, per job and pooled), (b) the root of the sum of squares of their two spreads and (c) the pooled floor (the median spread of the ranked implementations measured on at least two jobs). An implementation whose jobs all ran on one CPU model counts with at least the floor as its spread, one measured on a single job with the floor. A run in which most round pairs had one side PostgreSQL-bound and the other not compares CPU cost at two different loads: each such run adds the change in CPU cost with the load that the [CPU split](README.md#cpu-split) experiment measured for its endpoint (7% for a single-query read, 2% for /fortunes, a third for /queries and the writes), divided by the category's number of runs, to that implementation's spread. Scores are sorted and each is compared with its neighbour above: a new group starts only where that gap is larger than their margin, so a group is a chain of neighbours within their margins (its two ends can be further apart than one margin) and its members share the range of positions it occupies, for example "5–7". "±" after a score: the margin of its comparison with the score above it (the first position has none). A/A margin and pooled floor per category: Hello world: A/A ±1.3%, floor ±9.0% (14 implementations); Database: A/A ±0.4%, floor ±6.0% (14 implementations); Application: A/A ±1.2%, floor ±5.9% (14 implementations); Memory (high-water mark): A/A ±0.0%, floor ±0.4% (14 implementations); Startup: A/A ±0.0%, floor ±0.0% (14 implementations).

| Implementation | Overall | Hello world | Database | Application ‡ | Memory (high-water mark) | Startup | Stability | Runner CPUs |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Axum (test_before_acquire off) – diagnostic, unranked | diagnostic: 1.09 | diagnostic: 1.00×* ≈ | diagnostic: 1.23×* | diagnostic: 1.15×* | diagnostic: 1.00× ≈ (17 MiB) | diagnostic: 1.00× ≈ (0.02 s) | pass | EPYC 7763, EPYC 7763, EPYC 7763 |
| Actix Web | 1: 1.07 | 1: 1.18×* | 3–7: 0.95×* ≈ ±6.0% | 1: 1.19×* | 1–5: 1.00× ≈ (12 MiB) | 1–11: 1.00× ≈ (0.02 s) | pass | EPYC 9V45, EPYC 7763, Xeon Platinum 8370C CPU @ 2.80GHz |
| Axum – baseline | reference: 1.00 | reference: 1.00× | reference: 1.00× | reference: 1.00× | reference: 1.00× (17 MiB) | reference: 1.00× (0.02 s) | pass | EPYC 7763 ×24, Xeon 6975P-C ×9, EPYC 9V74 ×8, Xeon PLATINUM 8573C ×4, EPYC 9V45 ×3, Xeon Platinum 8370C CPU @ 2.80GHz ×2, Xeon 6973P-C ×1 |
| Axum (A/A control) – A/A control, unranked | A/A: 1.00 | A/A: 1.00×* ≈ | A/A: 1.00×* ≈ | A/A: 1.00×* ≈ | A/A: 1.00× ≈ (17 MiB) | A/A: 1.00× ≈ (0.02 s) | pass | EPYC 7763, Xeon 6975P-C, EPYC 7763 |
| Topcoat | 2: 0.99 ±5.5% | 2: 0.76×* ±9.0% | 1: 1.19×* | 2: 1.06×* ±5.9% | 1–5: 1.00× ≈ (12 MiB) ±0.4% | 1–11: 1.00× ≈ (0.02 s) ±0.0% | pass | Xeon 6975P-C, EPYC 7763, Xeon PLATINUM 8573C |
| Gin | 3: 0.83 ±5.5% | 3–6: 0.46×* ±9.0% | 2: 1.11×* ±6.0% | 3: 0.92×* ±5.9% | 1–5: 1.00× ≈ (26 MiB) ±0.4% | 1–11: 1.00× ≈ (0.02 s) ±0.0% | pass | EPYC 7763, EPYC 9V74, Xeon PLATINUM 8573C |
| Loco | 4–5: 0.77 ±5.5% | 3–6: 0.49×* ±9.0% | 3–7: 0.84×* ±15.6% | 4–5: 0.84×* ±5.9% | 1–5: 1.00× ≈ (17 MiB) ±0.4% | 1–11: 1.00× ≈ (0.02 s) ±0.0% | pass | EPYC 9V74, EPYC 7763, Xeon 6975P-C |
| Rullst (as generated) | 4–5: 0.75 ±5.5% | 3–6: 0.50×* ±9.0% | 3–7: 0.79×* ±6.0% | 4–5: 0.81×* ‡ ±5.9% | 1–5: 1.00× ≈ (12 MiB) ±0.4% | 1–11: 1.00× ≈ (0.02 s) ±0.0% | pass | EPYC 7763, EPYC 7763, EPYC 9V74 |
| Fastify | 6: 0.61 ±5.5% | 7: 0.39×* ±12.9% | 3–7: 0.80×* ±6.0% | 6: 0.71×* ±5.9% | 10: 0.38× (170 MiB) ±6.4% | 1–11: 1.00× ≈ (0.83 s) ±0.0% | pass | EPYC 7763, EPYC 9V74, EPYC 9V74 |
| ASP.NET Core | 7–8: 0.50 ±9.9% | 3–6: 0.46× ±10.9% | 8–10: 0.51×* ±25.5% | 9–10: 0.37×* ‡ ±21.4% | 8: 0.50× (127 MiB) ±0.7% | 1–11: 1.00× ≈ (0.64 s) ±0.0% | pass | Xeon Platinum 8370C CPU @ 2.80GHz, Xeon PLATINUM 8573C, EPYC 9V45 |
| Phoenix | 7–8: 0.46 ±15.9% | 10: 0.15×* ±31.6% | 3–7: 0.86×* ±15.6% | 7: 0.62×* ‡ ±13.8% | 9: 0.40× (158 MiB) ±2.5% | 12: 0.74× (1.35 s) ±22.5% | pass | EPYC 9V45, EPYC 7763, EPYC 7763 |
| NestJS | 9: 0.40 ±12.4% | 8–9: 0.30×* ±22.4% | 8–10: 0.60×* ±21.7% | 9–10: 0.38×* ±16.8% | 12: 0.25× (252 MiB) ±1.4% | 13: 0.53× (1.89 s) ±24.2% | pass | EPYC 7763, EPYC 7763, Xeon 6975P-C |
| Spring Boot | 10: 0.33 ±8.5% | 8–9: 0.24×* ±29.8% | 8–10: 0.66×* ±11.8% | 8: 0.46×* ‡ ±17.9% | 14: 0.14× (471 MiB) ±7.0% | 14: 0.18× (5.66 s) ±26.5% | pass | EPYC 7763, Xeon 6975P-C, Xeon 6973P-C |
| FastAPI | 11–12: 0.18 ±15.3% | 11: 0.070×* ±24.7% | 11–13: 0.20×* ±50.8% | 11–13: 0.12×* ‡ ±45.6% | 11: 0.34× (191 MiB) ±5.9% | 1–11: 0.93× ≈ (1.07 s) ±23.6% | pass | Xeon 6975P-C, EPYC 9V74, EPYC 7763 |
| Django | 11–12: 0.16 ±22.6% | 12: 0.029×* ±21.3% | 11–13: 0.23×* ±41.9% | 11–13: 0.12×* ±37.1% | 7: 0.54× (118 MiB) ±0.6% | 1–11: 0.93× (1.08 s) ±24.8% | pass | EPYC 7763, EPYC 7763, Xeon PLATINUM 8573C |
| Ruby on Rails | 13: 0.12 ±22.2% | 13: 0.014×* ±28.6% | 11–13: 0.31×* ±30.4% | 11–13: 0.11×* ‡ ±45.3% | 13: 0.16× (402 MiB) ±3.1% | 1–11: 0.91× ≈ (1.10 s) ±18.9% | pass | EPYC 7763, EPYC 9V74, Xeon 6975P-C |
| Laravel | 14: 0.047 ±21.9% | 14: 0.005×* ±37.5% | 14: 0.057×* † ±40.9% | 14: 0.018×* ‡ ±41.3% | 6: 0.76× (84 MiB) ±0.4% | 1–11: 1.00× ≈ (0.45 s) ±0.0% | pass | EPYC 7763, Xeon 6975P-C, EPYC 7763 |

† Database: Laravel: opens a new PostgreSQL connection for every request (PHP-FPM; Laravel's documentation does not recommend persistent PDO connections).

‡ Application: the score includes a PUT /world/{id} run that did not write in most measured requests (the note under the application table).

Overall: the geometric mean of the 5 category scores, with Hello world, Database and Application counted twice and Memory and Startup counted once (2:2:2:1:1), with the same tie margins and position ranges as the categories. The three throughput categories count twice because the Memory and Startup floors make most native implementations tie there. It is a summary for quick reading; the categories are the result, and other weightings change the order (the table below, equal weights included). Stability is not a score; an implementation that fails it has no overall position.

Positions under other weightings (Equal weights: Hello world ×1, Database ×1, Application ×1, Memory ×1, Startup ×1; Throughput only: Hello world ×1, Database ×1, Application ×1; Database and Application: Database ×1, Application ×1; Without Hello world: Database ×1, Application ×1, Memory ×1, Startup ×1; Throughput ×2: Hello world ×2, Database ×2, Application ×2, Memory ×1, Startup ×1):

| Implementation | Equal weights | Throughput only | Database and Application | Without Hello world | Throughput ×2 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Axum (test_before_acquire off) – diagnostic, unranked | diagnostic: 1.07 | diagnostic: 1.12 | diagnostic: 1.19 | diagnostic: 1.09 | diagnostic: 1.09 |
| Actix Web | 1: 1.06 | 1: 1.10 | 1–3: 1.07 | 1–3: 1.03 | 1: 1.07 |
| Axum – baseline | reference: 1.00 | reference: 1.00 | reference: 1.00 | reference: 1.00 | reference: 1.00 |
| Axum (A/A control) – A/A control, unranked | A/A: 1.00 | A/A: 1.00 | A/A: 1.00 | A/A: 1.00 | A/A: 1.00 |
| Topcoat | 2: 0.99 | 2: 0.99 | 1–3: 1.12 | 1–3: 1.06 | 2: 0.99 |
| Gin | 3: 0.86 | 3: 0.78 | 1–3: 1.01 | 1–3: 1.00 | 3: 0.83 |
| Loco | 4–5: 0.81 | 4–5: 0.70 | 4: 0.84 | 4–5: 0.92 | 4–5: 0.77 |
| Rullst (as generated) | 4–5: 0.79 | 4–5: 0.68 | 5–7: 0.80 | 4–5: 0.89 | 4–5: 0.75 |
| Fastify | 6: 0.61 | 6: 0.61 | 5–7: 0.75 | 6–7: 0.68 | 6: 0.61 |
| ASP.NET Core | 7–8: 0.54 | 7–10: 0.44 | 9–10: 0.44 | 8: 0.56 | 7–8: 0.50 |
| Phoenix | 7–8: 0.48 | 7–10: 0.43 | 5–7: 0.73 | 6–7: 0.63 | 7–8: 0.46 |
| NestJS | 9: 0.39 | 7–10: 0.41 | 9–10: 0.48 | 9: 0.42 | 9: 0.40 |
| Spring Boot | 10: 0.28 | 7–10: 0.42 | 8: 0.55 | 11–12: 0.29 | 10: 0.33 |
| FastAPI | 11–12: 0.22 | 11–13: 0.12 | 11–13: 0.16 | 11–12: 0.29 | 11–12: 0.18 |
| Django | 11–12: 0.21 | 11–13: 0.094 | 11–13: 0.17 | 10: 0.35 | 11–12: 0.16 |
| Ruby on Rails | 13: 0.15 | 11–13: 0.079 | 11–13: 0.19 | 13: 0.27 | 13: 0.12 |
| Laravel | 14: 0.084 | 14: 0.018 | 14: 0.032 | 14: 0.17 | 14: 0.047 |

### Diagnostics

Unranked rows kept out of the tables above, with what they measure:

- **Rullst (minimal) – diagnostic, unranked**: Serves its router through rullst::web::axum::serve, Axum's own server re-exported by Rullst, and bypasses rullst::Server, so none of the production middleware that cargo rullst new generates runs; its Hello world numbers are therefore largely Axum's. No other framework has such a stripped-down variant here, so it is listed apart from the headline tables.

| Implementation | Version | Language | /json vs Axum | /html vs Axum | /db-single vs Axum | /queries vs Axum | /updates vs Axum | /fortunes vs Axum | /json req/s (Axum) | Idle RAM (MiB) | Peak RAM (MiB) | Runner CPUs |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Rullst (minimal) – diagnostic, unranked | 13.0.0-alpha.6 | Rust | 1.03 | 0.96 | 0.97 | 0.97 | 0.78 | 0.82 | 169,518 (166,909) | 1.3 | 15.2 | EPYC 7763, Xeon 6975P-C, EPYC 9V74 |

| Implementation | GET /world/{id} vs Axum | GET /worlds vs Axum | PUT /world/{id} vs Axum ‡ | POST /form vs Axum | GET /me vs Axum | CSRF | Session store | Peak RAM after the 125 logins (MiB) | Hot rows p99 (ms) | Hot rows errors |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- | ---: | ---: | ---: |
| Rullst (minimal) – diagnostic, unranked | 0.97 | 0.74 | 1.18 ‡ | 1.18 | 0.99 | token (built-in) | postgresql (generator) | 472 (928) | 21.34 | 0 |

| Implementation | Hello world | Database | Application | Memory (high-water mark) | Startup | Runner CPUs |
| --- | --- | --- | --- | --- | --- | --- |
| Rullst (minimal) – diagnostic, unranked | diagnostic: 1.00×* ≈ | diagnostic: 0.87×* | diagnostic: 0.98×* ‡ ≈ | diagnostic: 1.00× ≈ (15 MiB) | diagnostic: 1.00× ≈ (0.01 s) | EPYC 7763, Xeon 6975P-C, EPYC 9V74 |
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
| `PUT /world/{id}` | body `{"randomNumber": n}` (a JSON integer 1-10,000), validated (400 or 422 otherwise, a JSON string such as `"5"` included, with nothing written); the row is changed the ORM's usual way and returned as stored. A public JSON API call, sent without cookies (Rullst as generated, which refuses cookieless writes, gets its CSRF cookie and header). Measured with the 10,000 ids shuffled and a new random value (1,000-9,999) in every request, drawn by the load generator, so that a request does not store the value its row already holds (an ORM that writes only changed columns would then skip the `UPDATE`); the harness counts the rows each measured run updates |
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
ratio when neither server was client-bound, and with its CPU-cost ratio
(requests per CPU-second of the server and PostgreSQL together) when either
was. When both sides were client-bound their requests/s were about equal, so
such a score compares CPU cost per request, not throughput. A run with more
than 1% errors has no score in its category. Ties come from an A/A control
(an identical copy of Axum, measured like everything else) and from how much
each implementation's scores differ between its jobs
([How the scores are computed](#how-the-scores-are-computed)).

An overall ranking is published (`scoring.publish_overall` in
[bench/config.json](bench/config.json) is `true`): the weighted geometric
mean of the five category scores, with Hello world, Database and Application
counted twice and Memory and Startup once (`scoring.overall_weights`,
2:2:2:1:1). The throughput categories count double because the Memory and
Startup floors make most native implementations tie there. It is a summary
for quick reading, with the same tie margins and position ranges as the
categories; the categories are the result. A table of the positions under
other weightings (equal weights, throughput only, Database and Application
only, without Hello world) is printed right below it.

## Method

Each framework is measured by its own jobs, each on a GitHub-hosted
`ubuntu-latest` runner (4 vCPUs, 16 GiB of RAM): 3 jobs per implementation
by default (the `jobs_per_framework` input; `publication.min_jobs` in
[bench/config.json](bench/config.json) is the minimum for publishing), so
every implementation is measured on three machines, often with different
CPU models. Ratios to Axum cancel part of the difference between runners
(below: most of it for Rust and Go, much less for the other runtimes); the
tie margins below are derived from what remains. Each job
records `lscpu`, the CPU model, the kernel, the memory, the Docker version,
image digests and tool versions with the results, and every results row
names the CPU model of each of its jobs.

How much of the difference between runners the ratios cancel depends on the
runtime. In the first official v3 run (Rullst 13.0.0-alpha.6) a Rust or Go
implementation's per-job scores in a category differed by about 10% or less
between CPU models, while for the other runtimes up to about 70% of the
difference remained (FastAPI's Database score: 0.13 on a Xeon 6975P-C, 0.22
on an EPYC 7763); the results state each run's own figures above the tables.
Two implementations can also have drawn different CPU models: in that run
Topcoat's lead over Gin in Database came from its Xeon 6975P-C job (1.27,
against 1.17 on its other two), a model Gin never drew. Hosted runners
cannot be chosen, so the tie margins carry what remains. `scoring.cpu_model_weighting` can give each CPU model one vote
instead of letting a model that ran two of an implementation's three jobs
set its score (`"per-model"`, the geometric mean of the per-model medians);
it is `"pooled"`, the median of every round pair, and the per-model score is
recorded in the results (`detail.score_per_cpu_model`) for comparison.

1. **Build.** The job builds the framework's image and the Axum baseline's
   image from their folders under `frameworks/`, with base images pinned by
   digest (the digests the first official v3 run built with) and lockfiles.
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
   server that closes connections). For `PUT /world/{id}`,
   `pg_stat_statements` also counts the rows its `UPDATE` statements wrote
   during that step: fewer than 0.8 per successful request fails
   conformance.
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
   measured in Tiers 3 and 4; the server's highest RAM during these runs is
   reported as "Peak RAM after the 125 logins", outside every score. Around
   the measured `PUT /world/{id}` run the harness reads PostgreSQL's count of
   updated `world` rows (`pg_stat_user_tables.n_tup_upd`, kept whatever the
   statement tracking; backends report it about once a second, so it can be
   off by about a second of writes at each end): the round records the rows
   updated per successful request, and the publication gate refuses results
   where an implementation's median is below 0.8. Warm-up errors are reported
   with the results.
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
   neighbours) partly cancel out in the ratio (most for Rust and Go, see
   above), so compare ratios rather than absolute numbers across jobs and
   runs.
6. **A/A control.** `frameworks/axum-control` is a byte-identical copy of
   the Axum baseline (`harness.py validate` checks it), measured in its own
   jobs exactly like every other implementation. Its ratios should all be
   1.00, so how far they land from 1.00 is the noise of a ratio on one
   runner; it is one of the three terms of the tie margins (below) and is
   listed, unranked, with the results.

Fixed settings, the same for every implementation:

- **CPU split.** The server container gets 2 vCPUs (`--cpuset-cpus`; both
  threads of one physical core when the runner exposes SMT siblings, as all
  51 runners of the first official v3 run did: the server's 2 vCPUs were one
  physical core, and the load generator and PostgreSQL shared the other). The
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
  implementation gets the same mix. In the `PUT /world/{id}` bodies the Lua
  script replaces a placeholder with a new random value (1,000-9,999, the
  width of the placeholder) in every request it sends, from a generator
  seeded anew for each run and each wrk thread: a prebuilt value would be
  sent again by the second thread, by the next pass through the list and by
  the measurement after its warm-up. On the phase-2 endpoints, in every
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
  **CPU-cost ratio**, the ratio of requests per CPU-second of **the server
  and PostgreSQL together**. When both sides were limited by the client
  vCPUs their requests/s were about equal, so the score then compares CPU
  cost per request, not throughput (a `/db-single` at 0.98× Axum in
  requests/s can score 0.85×). A framework is charged for the PostgreSQL work its queries
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
frameworks changes from one CPU model to another.

**Runs measured at different loads.** When one side of a round pair was
PostgreSQL-bound and the other was limited by its own server, the CPU-cost
ratio compares the two at different loads, and CPU cost per request changes
with the load ([CPU split](#cpu-split): +7% on `/db-single`, -2% on
`/fortunes`, +33-34% on `/queries` and `/updates`). Each run in which most
round pairs were like that adds its endpoint's measured change (the
single-query application reads count like `/db-single`, the write like
`/updates`), divided by the category's number of runs, to that
implementation's spread, as a root of the sum of squares; the detailed
tables mark it "+ mixed limits". Marking those runs not comparable instead
would have left most implementations without a Database score (every Rust
and Go row had a server-bound `/fortunes` against a PostgreSQL-bound Axum).

**Positions.** The scores are sorted and each is compared with its
neighbour above: a new group starts only where that gap is larger than the
margin of the pair. Neighbours within their margin therefore always share a
group, and every member of a group gets the range of positions the group
occupies, for example "5–7" (positions 5 to 7, in no particular order). A
group is a chain of such neighbours, so its two ends can be further apart
than one margin; that is the price of never splitting two scores that cannot
be told apart. Until 20 November 2026 each score was compared with the best
score of its group, which could show "5 (tie)" and "7" for two scores 2%
apart against a 6% margin. A score within the largest of (a), its own spread
and (c) of 1.00 is marked "≈": not distinguishable from Axum. Neighbouring
start-up times within the 0.25 s readiness check interval also share a
group. The overall score and the other weightings use the same rule with
the per-job weighted geometric means. The A/A margin and the floor of each
category are printed above the rankings; "±" after a score is the margin of
its comparison with the score above it, and the detailed tables in
[benchmarks_results.md](benchmarks_results.md) list each job's score and CPU
model, the spread used and that comparison.

**Unranked rows.** Axum is the reference (1.00). Rullst's minimal
configuration, the A/A control and the Axum variant without SQLx's
connection test are diagnostics: they get scores, labelled, without a
position, so they never push a ranked implementation down. Rullst's minimal
configuration serves its router through `rullst::web::axum::serve` (Axum's
own server, re-exported by Rullst) and bypasses `rullst::Server`, so its
Hello world numbers are largely Axum's; no other framework has such a
stripped-down variant here, so it is listed only in the results' Diagnostics
section (`"listing": "diagnostics"` in its `bench.json`), not in the headline
tables.

**Overall.** The weighted geometric mean of the five category scores
(`scoring.overall_weights`: Hello world, Database and Application ×2,
Memory and Startup ×1), published because `scoring.publish_overall` is
`true`, followed by the positions under other weightings (equal weights,
throughput only, Database and Application only, without Hello world,
throughput counted twice). An implementation that fails the Stability check
has no overall position. The weighting is a choice; the sensitivity table
shows how much the order depends on it.

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
  Npgsql, under ASP.NET Core, resets a pooled connection's state before each
  query EF Core runs; GORM, under Gin, wraps each write in a transaction by
  default; Rails uses 6 of its 16 connections (2 Puma workers × 3 threads,
  Rails' production default). PostgreSQL's CPU per request is printed for
  every database run so these costs are visible, and the results repeat
  these defaults above the tables.
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
  served through `rullst::web::axum::serve` and bypassing `rullst::Server`)
  is an unranked diagnostic listed apart from the headline tables: it takes
  no position in any ranking. The results say whether the measured Rullst
  came from crates.io or from a git revision.
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
  remove it, least for the runtimes that are not native code (see
  [Method](#method)). Implementations are not given the same mix of CPU
  models: a model that ran two of an implementation's three jobs sets most
  of its score. The tie margins take what is left from the A/A control and from
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
  category (a broken control);
- a category has no between-job spread (no ranked implementation has scores
  from two jobs), so its tie margins could not include the difference
  between runners, or its pooled floor is above 15%
  (`publication.max_floor`: the runners differed too much to rank; the A/A
  margin alone, 0.2-1.3% in the first official run against floors of 6-9%,
  could never refuse that);
- an implementation's measured `PUT /world/{id}` runs updated fewer than
  0.8 rows of `world` per successful request (median), or have no count;
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
      "listing", "listing_note",               "diagnostics": shown only in the Diagnostics section
      "dependency_source": { "kind", "label", "raw" },   Rullst rows: crates.io or a git revision
      "jobs": [ { "job", "status", "rounds", "cpu_model", "runner", "round_orders" } ],
      "runners": ["<cpu model>", ...],         the CPU model of each measured job
      "endpoints": ["text", ...],              the endpoints the implementation serves (bench.json)
      "metrics": { "<metric>": { "median", "min", "max", "spread", "n" } },
      "ratios":  { "<metric>": { "median", "min", "max", "spread", "n" },   pooled over every job
                   "tier1.<endpoint>.capacity": { ..., "pairs", "cpu_rounds", "not_comparable_rounds",
                                 "postgresql_rounds", "load_generator_rounds", "mixed_limit_rounds" } },
                                               capacity ratios (How the scores are computed)
      "ratios_by_cpu_model": { "tier1.<endpoint>.capacity": { "models": { "<cpu model>": median },
                                 "value" } },  the median per CPU model and their geometric mean
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
  "server_cores": { "jobs", "smt_threads_of_one_core" },   jobs whose server vCPUs were one core's two threads
  "reading_rullst": "...",                     the plain-language reading for Rullst as generated
                                               (bench/reading.py; README "What this means for Rullst")
  "labels": { "put_world": { "flagged": [slug, ...], "unchecked", "note" } },   PUT /world/{id} runs that
                                               did not write in most requests, and the footnote
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
    "settings": { "publish_overall", "overall_weights", "cpu_model_weighting", "max_error_rate",
                  "memory_floor_mib", "startup_floor_s" },
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
            "position": 1,                     the group's first position (1, 1, 3); null for every row
                                               that is not "ranked"
            "position_range": [1, 2],          the positions the group occupies, and
            "position_label": "1–2",           as printed
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
                        "effective", "effective_percent", "basis", "mixed_limit" },   the score of each
                                               scored job with its CPU model, the half-range of their
                                               logarithms ("own"), and the spread the margins use
                                               ("effective": own, or the floor, with mixed_limit added;
                                               "basis" says which)
            "mixed_limit_runs", "mixed_limit_widening",   runs measured at different loads on the two
                                               sides and what they add to the spread
            "tie_check": { "against", "margin", "percent", "gap_percent", "tied", "group_spread_of" },
                                               the comparison with the score above (absent for the
                                               first position); group_spread_of is always null since
                                               20 November 2026
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
    "publish_overall": true,                   when true, "overall" and "sensitivity" are included:
    "overall": { "weights": {...}, "weight_ratio": {...}, "tie_rule": {...},
                 "entries": [ { "slug", "framework", "position", "position_range", "position_label",
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
`after.memory_peak_mib`; `tier1.world-update.rows_updated` and
`tier1.world-update.rows_updated_per_request` (the rows of `world` PostgreSQL
updated during the measured PUT run); `application.ram_peak_mib` (the
server's highest RAM during the application endpoints and the hot-rows run,
after the logins). RAM is in MiB, latency in milliseconds, CPU in
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

**Review of the first official v3 run (20 November 2026).** An independent
review of the Rullst 13.0.0-alpha.6 publication found that `PUT /world/{id}`
measured no write for the implementations whose ORM writes only changed
columns (Rullst, Phoenix, Rails, Spring Boot, ASP.NET Core, Laravel and, by
the same evidence, FastAPI): the load repeated 10,000 fixed (id, value) pairs
that the warm-up had already stored. Every PUT now carries a new value, the
conformance step and every measured round count the rows written, and the
publication gate refuses a run that did not write. The results of that run
are labelled (‡) until the next run replaces them. The same review led to
position ranges from neighbour comparisons, the widening for runs measured
at different loads, the "Peak RAM after the 125 logins" column, the floor
limit of the publication gate, base images pinned by digest, the Diagnostics
section and the CPU-model figures above the tables. The overall ranking is
published since then, with the weights 2:2:2:1:1. Positions from before
this change are not comparable with later ones.

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
