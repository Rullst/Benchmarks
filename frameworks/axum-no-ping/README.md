# Axum (test_before_acquire off)

A diagnostic, not ranked: [the Axum baseline](../axum) with one change in
`src/main.rs`, `PgPoolOptions::test_before_acquire(false)`. Every other file
is the baseline's.

Why: SQLx 0.9's pool pings an idle connection before handing it out
(`test_before_acquire`, default `true`: `sqlx-core/src/pool/options.rs`, and
`check_idle_conn` in `sqlx-core/src/pool/inner.rs`), and pings every
connection again when it returns to the pool (`return_to_pool` in
`sqlx-core/src/pool/connection.rs`, whatever the setting). A PostgreSQL
ping is a round trip (Sync, then ReadyForQuery). With `&pool` as the
executor, as Axum's examples use it, every statement takes and returns a
connection, so each statement can cost up to two extra round trips and
PostgreSQL CPU. That is SQLx's documented default and Axum keeps it, as do
Actix Web, Loco and both Rullst folders (all on SQLx); Topcoat's Toasty does
not ping by default, and Gin's pgx pings only connections idle for more than
1 s.

This variant bounds the acquire-side part of that cost: compare its
database rows, and its PostgreSQL CPU per request, with Axum's. The
release-side ping cannot be turned off in SQLx 0.9 and stays in both.

Production settings: the same as the baseline (see its README); the pool
setting above is the only difference.
