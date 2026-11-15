# Rullst (as generated)

Rullst the way `cargo rullst new` (blank starter, PostgreSQL, Active Record)
and `cargo rullst deploy` generate it, with the four benchmark endpoints in
place of the starter page. Compare it with [`../rullst-minimal`](../rullst-minimal)
to see what the default stack costs.

| | |
| --- | --- |
| Version | `rullst = "=13.0.0-alpha.5"` (exact pin and `Cargo.lock`); the `RULLST_VERSION` build argument measures another published release |
| Features | `orm`, `strict-postgres`, `studio`, as generated (Studio only starts in debug builds) |
| Build | `cargo build --release --locked` with Rust 1.99.1 and the generated release profile (`lto = "thin"`, `codegen-units = 1`, `strip = "symbols"`) |
| Server | `Server::new(router()).run(port)` with `RULLST_ENV=production` and `HOST=0.0.0.0`, as in the generated Dockerfile; Tokio starts one worker per CPU the process may use (2) |
| Middleware | the generated router layers (CSRF, `/health` and `/ready`, security headers) and the production baseline `Server` adds (WAF, CSRF, secure cookies, security headers, `Vary: HX-Request`, access log) |
| Database | `#[derive(Orm)]` model, `World::find(1)`; pool of `DB_POOL_SIZE` (16) connections via `Orm::init_with_options` |
| Templates | `html!` |
| Logging | Rullst's access log: `Server` writes one line per request to stdout and has no setting to turn it off. The container's output is discarded (`--log-driver none`), as for every implementation |
| Image | `gcr.io/distroless/cc-debian12:nonroot` (the generated Dockerfile uses the same base) |

The only change from the generated `main` is the pool size, set to the value
every implementation uses.
