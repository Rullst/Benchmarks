# Loco

| | |
| --- | --- |
| Version | loco-rs 1.3.1, SeaORM 2.0 (exact versions in `Cargo.lock`) |
| Build | `cargo build --release --locked` with Rust 1.99.1 and the release profile every Rust implementation uses (`lto = "thin"`, `codegen-units = 1`) |
| Server | `loco_bench-cli start` with `LOCO_ENV=production`; Loco's default middleware stack; Tokio starts one worker per CPU the process may use (2) |
| Database | SeaORM entity for `world`, `Entity::find_by_id(1).one(&ctx.db)`; `max_connections` = `DB_POOL_SIZE` (16), the generated `min_connections`/timeouts; `auto_migrate: false` because the harness creates the table |
| Templates | Tera through Loco's `ViewEngine<TeraView>` initializer (`assets/views/bench/hello.html`) |
| Database endpoints | `/queries`: `world::Entity::find_by_id(id).one(&ctx.db)` per row. `/updates`: per row, `find_by_id`, then `into_active_model()`, `Set` the new number and `ActiveModel::update` (one `UPDATE ... RETURNING` per row, no transaction, no batching). `/fortunes`: `fortune::Entity::find().all(&ctx.db)` (a generated-style entity in `models/_entities/fortune.rs`), sorted in Rust, rendered by Tera (`assets/views/bench/fortunes.html`, autoescaped as an `.html` template). `Query` reads `queries`; random ids from `rand::random_range` (rand 0.10) |
| Logging | `LOG_LEVEL=warn` (the generated config reads it; the default `info` logs every request) |
| Image | `gcr.io/distroless/cc-debian12:nonroot` (Loco's generated Dockerfile uses `debian:bookworm-slim`, the same Debian 12 libraries) |

Why: the app keeps the layout `loco new` generates for a PostgreSQL project
with server-side rendering: the `Hooks` implementation in `src/app.rs`, the
`cli::main` binary, `config/production.yaml` reading its values from the
environment, a SeaORM entity in `models/_entities`, and the Tera view-engine
initializer. It leaves out what the endpoints do not use (users, auth routes,
mailers, background workers, i18n, the separate `migration` crate) and keeps
the loco-rs feature set the generator selects.
