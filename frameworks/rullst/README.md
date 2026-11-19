# Rullst (as generated)

Rullst the way `cargo rullst new` (blank starter, PostgreSQL, Active Record)
and `cargo rullst deploy` generate it, with the benchmark endpoints in
place of the starter page. Compare it with [`../rullst-minimal`](../rullst-minimal)
to see what the default stack costs.

| | |
| --- | --- |
| Version | `rullst = "=13.0.0-alpha.5"` (exact pin and `Cargo.lock`); the `RULLST_VERSION` build argument measures another published release |
| Features | `orm`, `strict-postgres`, `studio`, as generated (Studio only starts in debug builds) |
| Build | `cargo build --release --locked` with Rust 1.99.1 and the generated release profile (`lto = "thin"`, `codegen-units = 1`, `strip = "symbols"`) |
| Server | `Server::new(router()).run(port)` with `RULLST_ENV=production` and `HOST=0.0.0.0`, as in the generated Dockerfile; Tokio starts one worker per CPU the process may use (2) |
| Middleware | the generated router layers (CSRF, `/health` and `/ready`, security headers) and the production baseline `Server` adds (WAF, CSRF, secure cookies, security headers, `Vary: HX-Request`, access log, turned off here: see Logging) |
| Database | `#[derive(Orm)]` model, `World::find(1)`; pool of `DB_POOL_SIZE` (16) connections via `Orm::init_with_options` |
| Templates | `html!` |
| Database endpoints | `/queries`: `World::find(id)` per row. `/updates`: per row, `World::find`, set `randomnumber`, `save()` (Active Record; each `save()` runs its `UPDATE` in its own transaction, as Rullst does without an enclosing `Orm::transaction`; no batching). `/fortunes`: a `#[derive(Orm)] #[orm(table = "fortune")]` model, `Fortune::all()`, sorted in Rust, rendered with `html!` (`@for`, escaped). `Query` (re-exported by `rullst::server`) reads `queries`; random ids from `rand::random_range` (rand 0.10) |
| Logging | Off: the container gets `RULLST_ACCESS_LOG=off` (`env` in `bench.json`), the setting Rullst 13.0.0-alpha.6 added for `Server`'s access log (`on`, `off`, `errors` or `1/N`). Rullst 13.0.0-alpha.5 and earlier ignore the variable and write one access-log line per request to stdout, so the published 13.0.0-alpha.5 results were measured with the access log on. The container's output is discarded (`--log-driver none`), as for every implementation |
| Image | `gcr.io/distroless/cc-debian12:nonroot` (the generated Dockerfile uses the same base) |

The only change from the generated `main` is the pool size, set to the value
every implementation uses. The only setting added to the generated deployment
is `RULLST_ACCESS_LOG=off`, because every implementation runs with logging off.
