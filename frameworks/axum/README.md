# Axum (baseline)

Every job measures Axum on the same runner as the framework under test, in
alternating rounds, and reports each metric as a ratio to it. It is the
reference point, not a contender.

| | |
| --- | --- |
| Version | axum 0.8.9, Tokio 1.54, Hyper 1 (exact versions in `Cargo.lock`) |
| Build | `cargo build --release --locked` with Rust 1.99.1, `lto = "thin"`, `codegen-units = 1` |
| Server | `axum::serve` on a Tokio multi-threaded runtime; Tokio starts one worker thread per CPU the process may use (2) |
| Database | SQLx 0.9 `PgPool` with `DB_POOL_SIZE` connections (16); Axum has no ORM and its examples use SQLx |
| Templates | Askama 0.16 (`templates/hello.html`), compiled at build time |
| Logging | none |
| Image | `gcr.io/distroless/cc-debian12:nonroot` |

Why: this is the plain setup the Axum documentation and examples show, with
no extra middleware. The release profile is the same for every Rust
implementation (the one `cargo rullst new` generates), so compiler settings
are not a variable.
