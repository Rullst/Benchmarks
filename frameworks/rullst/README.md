# Rullst (as generated)

Rullst the way `cargo rullst new` (blank starter, PostgreSQL, Active Record),
`cargo rullst auth` and `cargo rullst deploy` generate it, with the benchmark
endpoints in place of the starter page. Compare it with
[`../rullst-minimal`](../rullst-minimal) to see what the default stack costs.

| | |
| --- | --- |
| Version | `rullst = "=13.0.0-alpha.6"` (exact pin and `Cargo.lock`); the `RULLST_VERSION` build argument measures another published release. Built from crates.io (13.0.0-alpha.6 was published on 2026-11-20 from tag `v13.0.0-alpha.6`, commit `58438b6`) |
| Features | `orm`, `strict-postgres`, `studio`, as `cargo rullst new` generates them (Studio only starts in debug builds), and `auth-session-registry-postgres`, which `cargo rullst auth` adds |
| Build | `cargo build --release --locked` with Rust 1.99.1 and the generated release profile (`lto = "thin"`, `codegen-units = 1`, `strip = "symbols"`) |
| Server | `Server::new(router()).run(port)` with `RULLST_ENV=production` and `HOST=0.0.0.0`, as in the generated Dockerfile; Tokio starts one worker per CPU the process may use (2) |
| Middleware | the router as 13.0.0-alpha.6 generates it: the routes and `/health` and `/ready`, with no CSRF or header layer of its own, because `Server` applies its security baseline to every route in every environment (WAF, CSRF, secure cookies, secure headers), plus `Vary: HX-Request` and the access log (turned off here: see Logging). Global, as generated: every endpoint, including the earlier ones, runs it |
| Database | `#[derive(Orm)]` models, `World::find(1)`; pool of `DB_POOL_SIZE` (16) connections via `Orm::init_with_options`. Each model has the save mode the CLI generates, a `#[sqlx(skip)] snapshot: RowSnapshot` field (13.0.0-alpha.6 requires a save mode): `save()` writes only the changed columns, and nothing when no column changed |
| Templates | `html!` |
| Database endpoints | `/queries`: `World::find(id)` per row. `/updates`: per row, `World::find`, set `randomnumber`, `save()` (one `UPDATE world SET randomnumber = … WHERE id = … RETURNING *` in its own transaction, as Rullst does without an enclosing `Orm::transaction`; no batching; with alpha.5 it was a full-row `UPDATE`). The new number is drawn again when it equals the stored one, because a `RowSnapshot` save writes nothing for an unchanged value and every row must be written. `/fortunes`: a `#[derive(Orm)] #[orm(table = "fortune")]` model, `Fortune::all()`, sorted in Rust, rendered with `html!` (`@for`, escaped). `Query` (re-exported by `rullst::server`) reads `queries`; random ids from `rand::random_range` (rand 0.10) |
| Request input (phase 2) | `GET /world/{id}`: `Path<i32>` (a non-integer id is 400), `World::find(id)`, 404 without a row. `GET /worlds`: `Query<WorldsParams>` (a non-integer is 400), then `#[derive(Validate)]` constraints (`range` on each field, a `schema` function for `min <= max`) checked with `FieldErrors::validate` and answered like `ValidatedJson` (422 with the field errors): Rullst has no validating query extractor; then one query through the ORM's builder (`World::query().where_between("id", min, max).order_by("id").limit(..).offset(..).get()`). `PUT /world/{id}`: `ValidatedJson<WorldUpdate>` (malformed JSON or a missing or non-integer `randomNumber`: 400; out of range: 422) before the row is loaded, then `World::find` (404), the new value and `save()` (`UPDATE … RETURNING`) |
| CSRF | `Server`'s security baseline (built in, global): the double-submit `rullst_csrf` cookie, set by the first `GET` of a page; `GET /form` and `GET /login` embed the request's `CsrfToken` (since 13.0.0-alpha.6 masked per response, 86 characters) in the hidden `_token` field. Every `POST`, `PUT`, `PATCH` and `DELETE` must send it as `_token` or `X-CSRF-Token` (the masked value, or the cookie value itself), compared with the cookie in constant time; otherwise 403 before the handler runs. `POST /form` then takes `ValidatedForm<FormInput>` (`name` 1-64 characters, `randomNumber` 1-10,000: 422; unreadable fields 400) and renders the page with `html!` (escaped), `text/html; charset=utf-8` |
| `PUT /world/{id}` and CSRF | The finding of decision 7 in the phase-2 spec: the production `Server` refuses every state-changing request without the CSRF pair and exempts only authenticated machine endpoints (`Server::with_machine_endpoints`, for requests that carry a credential) and signed webhooks, so an unauthenticated public JSON write needs the pair. `bench.json` declares `"write_csrf": {"cookie": "rullst_csrf", "header": "X-CSRF-Token"}`: the harness takes the `rullst_csrf` cookie from `GET /form` and sends it with the same value in `X-CSRF-Token`, as a same-site script (htmx, `fetch`) does. Without them the `PUT` is refused with 403 and writes nothing (checked by conformance) |
| Sessions | The session registry `cargo rullst auth` sets up since 13.0.0-alpha.6 (`src/auth_middleware.rs`, the generated file with the differences below). `POST /login` (behind the generated `credential_rate_limit` and bounded Argon2id work: 4 at a time, 2 s wait) finds the user by `username` with the ORM, checks `users.password_argon2id` with `rullst::auth::verify_password` (a dummy hash when there is no such user), then `SessionRegistry::sign_in` stores a row in `rullst_auth_sessions` (a SHA-256 digest of the session secret, created by [`db.sql`](db.sql), the SQL of the generated migration; the server only `connect`s) and returns the `rullst_session` cookie (a `v3.` token sealed with `APP_KEY`, 30 days); the response is a 303 to `/me`. A wrong password is 401. `GET /me` runs behind the generated `auth_middleware`: `authenticate_request` (one primary-key `SELECT` of the session row, at most one `UPDATE` of its last-seen hour per hour), then `User::find` of the user's row on every request; a request without a valid session is redirected (303) to `/login` |
| Logging | Off: the container gets `RULLST_ACCESS_LOG=off` (`env` in `bench.json`), the setting Rullst 13.0.0-alpha.6 added for `Server`'s access log (`on`, `off`, `errors` or `1/N`). Rullst 13.0.0-alpha.5 and earlier ignore the variable and write one access-log line per request to stdout, so the published 13.0.0-alpha.5 results were measured with the access log on. The container's output is discarded (`--log-driver none`), as for every implementation. `Server` still installs its default tracing subscriber (no `RUST_LOG`: `info,sqlx=warn`), which prints start-up messages and warnings, no per-request lines; the ORM's INFO `rullst.orm.query` spans stay enabled (recorded, not printed), as in production |
| Image | `gcr.io/distroless/cc-debian12:nonroot` (the generated Dockerfile uses the same base) |

Changes from the generated application, all for the benchmark:

- `main` gives the pool the size every implementation uses instead of the
  SQLx default, and does not run migrations at start-up: the harness creates
  `world`, `fortune` and `users`, and [`db.sql`](db.sql) the session table.
- `RULLST_ACCESS_LOG=off`, because every implementation runs with logging
  off, and a fixed `APP_KEY` (benchmark-only, in `bench.json` `env`), which
  production requires to seal the session cookies; the server is one
  process, so every request sees the same key.
- **Login throttling (benchmark deviation).** The generated
  `credential_rate_limit` allows 10 credential submissions per client per
  minute; the harness signs in 125 users from 127.0.0.1 at the start of every
  round, so `CREDENTIAL_ATTEMPTS_PER_MINUTE` (the generated constant that sets
  it, in `src/browser.rs`) is 1,000 here. Nothing else changes: the limiter,
  the bounded Argon2id work and the CSRF check stay on the login. Rullst's
  Login Jail (`rullst-security`'s `LoginGuard`) is not part of the generated
  application or of `Server`'s stack, so it needs no setting.
- **Session epoch.** The generated `User` has a `session_epoch` column that
  "sign out everywhere" and password changes increment; the harness's
  `users` table (shared by every implementation) has none, so every account
  is at epoch 0. The epoch check still runs on every request; one session can
  still be revoked through its registry row.
- The login form uses `username` (the harness's accounts) instead of
  `email`, answers a wrong password with 401 instead of re-rendering the
  page, and redirects to `/me` instead of `/dashboard`; there is no
  registration, password reset or device list.

## Production settings

Each setting audited against Rullst's documentation and source at the
measured commit (`58438b6`, checked 2026-11-19), under the same rule as every
other folder.

| Setting | Value | Source |
| --- | --- | --- |
| Environment | `RULLST_ENV=production`, `HOST=0.0.0.0`, as the Dockerfile `cargo rullst deploy` generates | [docker.rs](https://github.com/Rullst/Rullst/blob/58438b64caa847ef7ffdcc08653ce26cb5a8a8a0/cargo-rullst/src/generators/project/docker.rs#L177) |
| Access log | off: `RULLST_ACCESS_LOG=off` (`Server` does not install it) | [Turning the access log down or off](https://github.com/Rullst/Rullst/blob/58438b64caa847ef7ffdcc08653ce26cb5a8a8a0/docs/src/telemetry-guide.md#L136) |
| Tracing subscriber | `Server`'s default, `RUST_LOG` unset: filter `info,sqlx=warn`; start-up messages and warnings only. ORM operations open INFO spans that the subscriber records without printing | [telemetry-guide.md](https://github.com/Rullst/Rullst/blob/58438b64caa847ef7ffdcc08653ce26cb5a8a8a0/docs/src/telemetry-guide.md#L120), [telemetry.rs](https://github.com/Rullst/Rullst/blob/58438b64caa847ef7ffdcc08653ce26cb5a8a8a0/rullst-core/src/telemetry.rs#L55), [startup.rs](https://github.com/Rullst/Rullst/blob/58438b64caa847ef7ffdcc08653ce26cb5a8a8a0/rullst-core/src/server/builder/startup.rs#L34) |
| Middleware | `Server`'s production stack as generated, global (security baseline, `Vary: HX-Request`); development tools need a debug build | [v3 spec §2.3 and decision 2](../../docs/v3-spec.md); [startup.rs](https://github.com/Rullst/Rullst/blob/58438b64caa847ef7ffdcc08653ce26cb5a8a8a0/rullst-core/src/server/builder/startup.rs#L227) |
| Pool | `Orm::init_with_options(url, DB_POOL_SIZE, 10)`: 16 connections, the 10 s acquire timeout, 300 s idle timeout and 30 min lifetime that `Orm::init` also uses | [pool.rs](https://github.com/Rullst/Rullst/blob/58438b64caa847ef7ffdcc08653ce26cb5a8a8a0/rullst-orm/src/pool.rs#L173), [config.rs](https://github.com/Rullst/Rullst/blob/58438b64caa847ef7ffdcc08653ce26cb5a8a8a0/rullst-orm/src/pool/config.rs#L103) |
| Prepared statements, connection checks | SQLx's defaults: 100 cached statements per connection, a ping when a connection is taken from the pool (`test_before_acquire`; Rullst turns it off only for SQLite) and when it is returned | [pool.rs](https://github.com/Rullst/Rullst/blob/58438b64caa847ef7ffdcc08653ce26cb5a8a8a0/rullst-orm/src/pool.rs#L121); SQLx [options.rs](https://github.com/launchbadge/sqlx/blob/v0.9.0/sqlx-core/src/pool/options.rs#L149) |
| Server and workers | `Server::run` (Hyper) on Tokio's multi-threaded runtime, one worker per CPU (2) | as generated |
