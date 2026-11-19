# Rullst (minimal)

Rullst's router (`routes!`), ORM (`#[derive(Orm)]`) and `html!`, served with
`axum::serve` as the Axum baseline is, without `rullst::Server`. This shows the
cost of Rullst's own layers (routing wrapper, ORM, `html!`) apart from its
production middleware stack, which [`../rullst`](../rullst) measures.

| | |
| --- | --- |
| Version | `rullst = "=13.0.0-alpha.5"` (exact pin and `Cargo.lock`); the `RULLST_VERSION` build argument measures another published release |
| Features | `orm`, `strict-postgres` |
| Build | `cargo build --release --locked` with Rust 1.99.1 and the same release profile as every Rust implementation |
| Server | `axum::serve(listener, router().into_axum())` on a Tokio multi-threaded runtime (2 workers) |
| Middleware | none, like the Axum baseline |
| Database | `#[derive(Orm)]` model, `World::find(1)`; pool of `DB_POOL_SIZE` (16) connections via `Orm::init_with_options` |
| Templates | `html!` |
| Database endpoints | the same handlers as [`../rullst`](../rullst): `World::find` per row for `/queries`; `World::find` and `save()` per row for `/updates` (each `save()` in its own transaction, no batching); `Fortune::all()` and `html!` for `/fortunes` |
| Logging | none |
| Image | `gcr.io/distroless/cc-debian12:nonroot` |

This is not how `cargo rullst new` sets up an application; it is a
configuration comparable to the Axum app.
