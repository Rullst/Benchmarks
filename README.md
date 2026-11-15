# Rullst Benchmarks

An HTTP benchmark suite that compares [Rullst](https://github.com/Rullst/Rullst)
with other web frameworks under the same conditions. Every number is measured
by a GitHub Actions workflow on GitHub-hosted runners, so anyone can rerun it,
and every number on this page is generated from the measurement output.

- Dashboard: <https://rullst.win/Benchmarks/>
- Full results tables: [benchmarks_results.md](benchmarks_results.md)
- Machine-readable results: <https://rullst.win/Benchmarks/data/latest.json> (see [Machine-readable results](#machine-readable-results))

## Results

<!-- results:start -->
No results have been published from the rebuilt suite yet. The first run
will replace this paragraph. Results from before the rebuild are kept, for
the record only, in [history/2026-06-22-laptop.md](history/2026-06-22-laptop.md).
<!-- results:end -->

## What is measured

Every implementation serves the same four endpoints on port 8080:

| Endpoint | Response |
| --- | --- |
| `GET /text` | `Hello World`, `text/plain` |
| `GET /json` | `{"message":"Hello World"}`, `application/json` |
| `GET /db-single` | the row with `id = 1` of the `world` table, read from PostgreSQL on every request, as `{"id":1,"randomNumber":N}`, `application/json` |
| `GET /html` | `<!DOCTYPE html><html><head><title>Benchmark</title></head><body><h1>Hello World</h1></body></html>`, `text/html`, rendered by the framework's template engine with `World` passed as a variable |

The four tiers:

| Tier | Load | Reported |
| --- | --- | --- |
| 1 | 125 connections for 10 s on each endpoint | requests/s, p50 and p99 latency, errors, server CPU |
| 2 | 300 connections for 30 s on `/json` | requests/s, p50 and p99 latency, errors and timeouts |
| 3 | idle for 10 s, then 200 connections for 15 s on `/json` | idle and peak RAM, idle and loaded CPU |
| 4 | 500 connections for 2 minutes on `/json` | requests/s, p99, errors and timeouts, RAM growth, whether the server stopped |

Each metric is also reported as a ratio to the Axum baseline measured on the
same runner (see below). The results also list requests/s per MiB of peak RAM
as one column; it is not used to rank anything.

## Method

Each framework is measured by its own job on a GitHub-hosted `ubuntu-latest`
runner (4 vCPUs, 16 GiB of RAM). The job records `lscpu`, the kernel, the
memory, the Docker version, image digests and tool versions with the results.

1. **Build.** The job builds the framework's image and the Axum baseline's
   image from their folders under `frameworks/`, with pinned base images and
   lockfiles.
2. **Database.** PostgreSQL 18.6 (image pinned by digest) starts with a
   `world` table of 10,000 rows ([bench/db/init.sql](bench/db/init.sql)).
3. **Conformance.** Each implementation is started and checked: status, media
   type and body of every endpoint, HTTP/1.1 keep-alive, and that
   `/db-single` follows changes made to the row between requests (so it reads
   the database every time). An implementation that fails is reported as
   failed with the reason and is not measured.
4. **Rounds.** The framework and Axum then alternate for 5 rounds (framework,
   Axum, framework, Axum, …). Each round starts a fresh container, waits for
   it to answer, measures it idle, warms up each endpoint for 5 s and runs the
   four tiers. Results are the median over rounds, with the lowest and highest
   round shown as the spread.
5. **Ratios.** For every round, each metric of the framework is divided by
   Axum's value from the adjacent round on the same runner; the reported ratio
   is the median of those per-round ratios. Runner-to-runner differences (CPU
   model, noisy neighbours) largely cancel out in the ratio, so compare ratios
   rather than absolute numbers across jobs and runs.

Fixed settings, the same for every implementation:

- **CPU split.** The server container gets 2 vCPUs (`--cpuset-cpus`; both
  threads of one physical core when the runner exposes SMT siblings). The
  load generator, PostgreSQL and the harness use the other 2 vCPUs. The job
  stops if the runner has fewer than 4 vCPUs.
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
  requests than the load generator could send, so close results at the top
  are ties, not rankings.
- **RAM still growing**: in Tier 4, RAM rose by more than 10% and 8 MiB
  between the middle and the last tenth of the test. For garbage-collected
  runtimes this can be heap growth rather than a leak.
- **stopped**: the server process exited (crash or out-of-memory kill) during
  a round. The phase is reported.

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
  cannot saturate the fastest servers on the simplest endpoints. Those
  results are flagged client-bound and should be read as ties.
- **Short tiers.** Tests last 10 s to 2 minutes, with a 5 s warm-up per
  endpoint. They do not show long-term stability, and runtimes with a JIT
  compiler may not reach their best speed.
- **One small machine.** Client, server and database share one virtual
  machine and talk over loopback: no network latency, no TLS, HTTP/1.1 with
  keep-alive only.
- **Trivial endpoints.** The endpoints measure framework overhead (routing,
  serialization, ORM, templates, middleware), not the speed of a real
  application, where application code and the database usually dominate.
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
between Rullst/Rullst and this repository. A measurement uses at most 3
runners at a time (`max-parallel: 3`), only Linux runners, and one measurement
runs at a time (a new trigger waits; it never cancels a running measurement).
Before a scheduled or manual run starts, it checks the public Actions API of
Rullst/Rullst and does not start while a release, release admission or a long
verification workflow is running there, or while more than 10 jobs are
queued; the next nightly check tries again. A manual run can override this
with the `force` input.

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
      "metrics": { "<metric>": { "median", "min", "max", "spread", "n" } },
      "ratios":  { "<metric>": { "median", "min", "max", "spread", "n" } },
      "flags": { "rounds", "crashed_rounds", "ram_growing_rounds", "client_bound_rounds": { ... } },
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
  "measured_from", "measured_to", "generated_at",   ISO 8601 UTC
  "run": { "id", "url", "sha", "event", "rounds" },
  "baseline": "axum",
  "config": { tiers, server limits, pool size, load generator, database },
  "environment": { "cpu_model", "cpu_count", "memory_total_mib", "kernel", "os",
                   "runner_image", "docker", "load_generator", "postgres", "cpu_split" },
  "results_schema": 1
}
```

`versions.json` (`rullst.benchmarks.versions.v1`) lists every measured Rullst
version with its date, run, file name and the headline medians and ratios of
the Rullst variants and Axum.

Metric names: `tier1.<endpoint>.rps`, `tier1.<endpoint>.latency_ms.mean`, `tier1.<endpoint>.latency_ms.p50`,
`tier1.<endpoint>.latency_ms.p99`, `tier1.<endpoint>.error_rate`,
`tier1.<endpoint>.server_cpu_cores` (endpoints `text`, `json`, `db-single`,
`html`); `tier2.rps`, `tier2.latency_ms.p50`, `tier2.latency_ms.p99`,
`tier2.error_rate`, `tier2.timeouts`; `tier3.idle_ram_mib`,
`tier3.idle_cpu_cores`, `tier3.load_ram_peak_mib`, `tier3.load_cpu_cores`,
`tier3.rps`; `tier4.rps`, `tier4.latency_ms.p99`, `tier4.error_rate`,
`tier4.transport_errors`, `tier4.timeouts`, `tier4.ram_mid_mib`,
`tier4.ram_end_mib`, `tier4.ram_growth_mib`; `startup_s`, `idle.tasks`,
`after.ram_mib`, `after.memory_peak_mib`. RAM is in MiB, latency in
milliseconds, CPU in cores, error rates as fractions. `ratios` has no entries
for error counts and rates; for Axum, whose ratios are 1 by definition, it is
empty. New fields may be added; a breaking change gets a new `schema` name.

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

The suite was rebuilt in November 2026. The results published before that
(measured by hand on a laptop on 22 June 2026) are kept in
[history/2026-06-22-laptop.md](history/2026-06-22-laptop.md) with an
explanation of why they are not comparable.

## License

[MIT](LICENSE)
