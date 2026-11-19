# Actix Web

| | |
| --- | --- |
| Version | actix-web 4.19.0 (exact versions in `Cargo.lock`) |
| Build | `cargo build --release --locked` with Rust 1.99.1, `lto = "thin"`, `codegen-units = 1` |
| Server | `HttpServer` with its default worker count: one worker per CPU the process may use (2) |
| Database | SQLx 0.9 `PgPool` with `DB_POOL_SIZE` connections (16), shared by the workers; Actix Web has no ORM |
| Templates | Askama 0.16 (`templates/hello.html`), as in the Actix examples' templating section |
| Database endpoints | as in the Axum baseline: one `SELECT` per row for `/queries`; for `/updates`, per row, that `SELECT` and one `UPDATE` (autocommit, no transaction, no batching); `/fortunes` with `SELECT id, message FROM fortune` and Askama (`templates/fortunes.html`). `web::Query` reads `queries`; random ids from `rand::random_range` (rand 0.10) |
| Logging | none (no `Logger` middleware) |
| Image | `gcr.io/distroless/cc-debian12:nonroot` |

Why: default `HttpServer` settings as the Actix Web documentation describes
them for production, with the same database and template crates as the Axum
baseline so the comparison is about the framework. The release profile is the
same for every Rust implementation.
