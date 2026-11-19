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
| Templates | Askama 0.16 (`templates/`), compiled at build time; HTML-escaped by default |
| Database endpoints | `/queries`: one `SELECT id, randomnumber FROM world WHERE id = $1` per row through the pool. `/updates`: per row, that `SELECT`, then `UPDATE world SET randomnumber = $1 WHERE id = $2` (one statement per row, autocommit: no transaction, no batching). `/fortunes`: `SELECT id, message FROM fortune`, sorted in Rust, rendered by Askama (`templates/fortunes.html`, HTML-escaped). Random ids from `rand::random_range` (rand 0.10) |
| Request input (phase 2) | `GET /world/{id}`: `Path<i32>` (a non-integer id is answered 400 by the extractor), then `SELECT … WHERE id = $1`, 404 without a row. `GET /worlds`: `Query` into optional `i64` fields (a non-integer is 400), ranges checked by hand (422), then one `SELECT … WHERE id BETWEEN $1 AND $2 ORDER BY id LIMIT $3 OFFSET $4`. `PUT /world/{id}`: `Path<i32>` and `Json` (malformed JSON 400; a missing or non-integer `randomNumber` 422), the 1-10,000 range by hand (422), then one `UPDATE world SET randomnumber = $1 WHERE id = $2 RETURNING id, randomnumber` (Axum has no ORM), 404 without a row. Axum has no validation library of its own; its examples check by hand or use `validator` |
| CSRF | [axum_csrf](https://crates.io/crates/axum_csrf) 0.12, the most-used maintained CSRF crate for Axum (Axum has none): `GET /form` and `GET /login` set the token in an encrypted cookie (`CsrfConfig::default()`: a random key and salt per process) and put its HMAC-SHA256 in the hidden `authenticity_token` field; `POST /form` and `POST /login` verify it first (403), then parse the fields (422 when invalid). The token stays valid for the cookie's 6-hour lifespan |
| Sessions | [tower-sessions](https://crates.io/crates/tower-sessions) 0.15 with the PostgreSQL store of [tower-sessions-sqlx-store](https://crates.io/crates/tower-sessions-sqlx-store) 0.16 (the most-used session crate; [axum-login](https://crates.io/crates/axum-login) does not support SQLx 0.9 yet). `POST /login` reads `users.password_argon2id` and verifies it with the `argon2` crate (0.6, in `spawn_blocking`), cycles the session id and stores the user id: one row in `tower_sessions.session`, created by [`db.sql`](db.sql) (the SQL `PostgresStore::migrate()` runs; the server creates nothing at start-up), cookie `id`, `Secure`, `HttpOnly`, `SameSite=Strict`. `GET /me` loads the session (one `SELECT` of `tower_sessions.session`, no write), then the user's row (`SELECT … FROM users WHERE id = $1`); 401 without a session |
| Middleware scope | the session layer wraps only `/form`, `/login` and `/me`, and only those routes extract the CSRF token; every other route keeps the plain stack. `PUT /world/{id}` has no CSRF check (a public JSON API route) |
| Logging | none |
| Image | `gcr.io/distroless/cc-debian12:nonroot` |

Why: this is the plain setup the Axum documentation and examples show, with
no extra middleware. The release profile is the same for every Rust
implementation (the one `cargo rullst new` generates), so compiler settings
are not a variable.

## Production settings

| Setting | Value | Source |
| --- | --- | --- |
| Logging | none: no tracing subscriber, no request logging layer | Axum has no logging of its own; its examples add `tower-http`'s `TraceLayer` only to show tracing |
| Pool | SQLx `PgPoolOptions::new().max_connections(DB_POOL_SIZE)`, every other option SQLx's default | <https://docs.rs/sqlx/0.9/sqlx/pool/struct.PoolOptions.html> |
| Connection test | SQLx's default `test_before_acquire(true)`: an idle connection taken from the pool is pinged first (`check_idle_conn`, `sqlx-core` 0.9.0 `src/pool/inner.rs`); and every connection is pinged again when it returns to the pool, whatever that setting (`return_to_pool`, `src/pool/connection.rs`). A PostgreSQL ping is a round trip (Sync, then ReadyForQuery). With `&pool` as the executor, as the examples use it, each statement takes and returns a connection, so it can cost up to two extra round trips | `sqlx-core` 0.9.0 source (`src/pool/options.rs`: "Defaults to `true`") |
| Prepared statements | SQLx prepares each query on first use per connection and caches it (100 statements per connection by default) | <https://docs.rs/sqlx/0.9/sqlx/postgres/struct.PgConnectOptions.html#method.statement_cache_capacity> |
| Server and workers | `axum::serve`, Tokio's multi-threaded runtime with one worker per CPU the process may use (2) | <https://docs.rs/axum/0.8/axum/fn.serve.html> |

The connection test is SQLx's default, so this baseline keeps it, as do the
other SQLx implementations (Actix Web, Loco, both Rullst folders).
[`../axum-no-ping`](../axum-no-ping) is the same app with
`test_before_acquire(false)`, an unranked diagnostic that bounds the cost of
the acquire-side ping; the release-side ping cannot be turned off in SQLx 0.9.
[`../axum-control`](../axum-control) is an identical copy, the A/A control.
