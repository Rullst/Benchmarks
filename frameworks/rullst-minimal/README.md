# Rullst (minimal)

Rullst's router (`routes!`), ORM (`#[derive(Orm)]`), `html!`, validation
extractors and session registry, served with `axum::serve` as the Axum
baseline is, without `rullst::Server`. This shows the cost of Rullst's own
layers (routing wrapper, ORM, `html!`, validation, sessions) apart from its
production middleware stack, which [`../rullst`](../rullst) measures.

**Unranked diagnostic.** This is not how `cargo rullst new` sets up an
application, so it takes no position in any ranking (`"role":
"diagnostic"` in `bench.json`): the results show its scores next to the
Axum reference, labelled, and rank only Rullst as generated. The results
also record whether the Rullst crates came from crates.io or from a git
revision.

| | |
| --- | --- |
| Version | `rullst = "=13.0.0-alpha.6"` (exact pin and `Cargo.lock`); the `RULLST_VERSION` build argument measures another published release. Built from crates.io (13.0.0-alpha.6 was published on 2026-11-20 from tag `v13.0.0-alpha.6`, commit `58438b6`) |
| Features | `orm`, `strict-postgres`, `auth-session-registry-postgres` |
| Build | `cargo build --release --locked` with Rust 1.99.1 and the same release profile as every Rust implementation |
| Server | `axum::serve(listener, router().into_axum())` on a Tokio multi-threaded runtime (2 workers) |
| Middleware | none on the earlier endpoints, like the Axum baseline; Rullst's `csrf_middleware` on `/form` and `/login` only, the generated `auth_middleware` on `/me` only |
| Database | `#[derive(Orm)]` models with the `RowSnapshot` save mode the CLI generates, `World::find(1)`; pool of `DB_POOL_SIZE` (16) connections via `Orm::init_with_options` |
| Templates | `html!` |
| Database endpoints | the same handlers as [`../rullst`](../rullst): `World::find` per row for `/queries`; `World::find` and `save()` per row for `/updates` (each `save()` an `UPDATE … RETURNING` of the changed column in its own transaction, no batching; a number equal to the stored one is drawn again, so every row is written); `Fortune::all()` and `html!` for `/fortunes` |
| Request input (phase 2) | the same handlers as [`../rullst`](../rullst): `Path<i32>` (400), `Query` (400) with `FieldErrors::validate` (422), `ValidatedJson` (400/422) before the write, the ORM's query builder for `/worlds`, `World::find` and `save()` for the `PUT` |
| CSRF | Rullst's built-in `csrf_middleware` as a layer on the `/form` and `/login` routes only: the double-submit `rullst_csrf` cookie, the token masked per response in the hidden `_token` field, compared in constant time; 403 on a mismatch. `PUT /world/{id}` has no CSRF check here (no `Server`), so `bench.json` declares no `write_csrf` |
| Sessions | the same session registry as [`../rullst`](../rullst) (`rullst_auth_sessions`, created by [`db.sql`](db.sql); `rullst_session` cookie sealed with `APP_KEY`, set in `bench.json` `env`); `POST /login` with bounded Argon2id work but without `credential_rate_limit`, which, like the rest of the production stack, this configuration leaves out; `GET /me` behind `auth_middleware` (a `SELECT` of the session row and one of the user's row per request) |
| Logging | none |
| Image | `gcr.io/distroless/cc-debian12:nonroot` |

This is not how `cargo rullst new` sets up an application; it is a
configuration comparable to the Axum app. As in [`../rullst`](../rullst),
the harness's `users` table has no `session_epoch` column, so every account
is at session epoch 0.
