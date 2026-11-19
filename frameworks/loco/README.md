# Loco

| | |
| --- | --- |
| Version | loco-rs 1.3.1, SeaORM 2.0 (exact versions in `Cargo.lock`) |
| Build | `cargo build --release --locked` with Rust 1.99.1 and the release profile every Rust implementation uses (`lto = "thin"`, `codegen-units = 1`) |
| Server | `loco_bench-cli start` with `LOCO_ENV=production`; Loco's default middleware stack; Tokio starts one worker per CPU the process may use (2) |
| Database | SeaORM entity for `world`, `Entity::find_by_id(1).one(&ctx.db)`; `max_connections` = `DB_POOL_SIZE` (16), the generated `min_connections`/timeouts; `auto_migrate: false` because the harness creates the table |
| Templates | Tera through Loco's `ViewEngine<TeraView>` initializer (`assets/views/bench/hello.html`) |
| Database endpoints | `/queries`: `world::Entity::find_by_id(id).one(&ctx.db)` per row. `/updates`: per row, `find_by_id`, then `into_active_model()`, `Set` the new number and `ActiveModel::update` (one `UPDATE ... RETURNING` per row, no transaction, no batching). `/fortunes`: `fortune::Entity::find().all(&ctx.db)` (a generated-style entity in `models/_entities/fortune.rs`), sorted in Rust, rendered by Tera (`assets/views/bench/fortunes.html`, autoescaped as an `.html` template). `Query` reads `queries`; random ids from `rand::random_range` (rand 0.10) |
| Request input (phase 2) | Loco's validating extractors (`validator` 0.20, as `loco new` depends on it): `GET /world/{id}`: `Path<i32>` (a non-integer id is 400), `world::Entity::find_by_id(id).one(&ctx.db)`, 404 without a row. `GET /worlds`: `QueryValidate<WorldsParams>` (a non-integer value 400; `#[validate(range)]` on each field and a `#[validate(schema)]` check for `min <= max`: 400), then one query through SeaORM's builder (`filter(Column::Id.between(min, max))`, `order_by_asc`, `limit`, `offset`, `all`). `PUT /world/{id}`: `Path<i32>` and `JsonValidate<WorldUpdate>` (malformed JSON 400, a missing or non-integer `randomNumber` 422 from Axum's `Json`, out of range 400), validated before the row is loaded; then `find_by_id` (404), `into_active_model()`, `Set` and `ActiveModel::update` (one `UPDATE ... RETURNING`) |
| CSRF | Loco has no CSRF protection; it is built on Axum, so it uses the crate the Axum baseline uses, [axum_csrf](https://crates.io/crates/axum_csrf) 0.12, as a layer (`CsrfLayer`, `Routes::layer`) on the `/form` and `/login` routes only: `GET /form` and `GET /login` set the token in an encrypted cookie (`CsrfConfig::default()`: a random key and salt per process; the server is one process) and put its HMAC-SHA256 in the hidden `authenticity_token` field. `POST /form` takes `FormValidate<FormInput>` (`name` 1-64 characters, `randomNumber` 1-10,000; 400, or 422 for a non-integer), then verifies the token (403), then renders `assets/views/bench/form_result.html` with Tera (autoescaped), `text/html; charset=utf-8`. The token stays valid for the cookie's 6-hour lifespan |
| Sessions | Loco's `auth_session` feature (enabled in `Cargo.toml`) with its default store, a signed cookie (`loco_session`, `HttpOnly`, `SameSite=Lax`, 30 days): `auth.session` in `config/production.yaml` as Loco's generator writes it, `store: cookie`, the signing secret from `SESSION_SECRET` (bench.json `env`: Loco refuses its development default in production; every request reaches the one process). `POST /login` verifies the CSRF token, loads the user by `username` with SeaORM and checks `users.password_argon2id` with `loco_rs::hash::verify_password` (Argon2id, in `spawn_blocking`), then `session.renew().set_user_id(id)` and a 303 to `/me`; a wrong password is 401. `GET /me` takes `CurrentUser<users::Model>`: the cookie's signature is checked and `SessionUser::find_by_session_id` loads the user's row with `find_by_id` on every request (`models/users.rs`); 401 without a session. Loco's docs suggest a non-guessable `pid` as the session's user id; the harness's `users` table has only the integer id, which the signature protects |
| Middleware scope | the CSRF layer wraps only `/form` and `/login`; the session is read only by the handlers that take `Session` or `CurrentUser`. Loco's default middleware stack is unchanged and global, as before. `PUT /world/{id}` has no CSRF check (a public JSON API route) |
| Logging | `LOG_LEVEL=warn` (the generated config reads it; the default `info` logs every request) |
| Image | `gcr.io/distroless/cc-debian12:nonroot` (Loco's generated Dockerfile uses `debian:bookworm-slim`, the same Debian 12 libraries) |

Why: the app keeps the layout `loco new` generates for a PostgreSQL project
with server-side rendering: the `Hooks` implementation in `src/app.rs`, the
`cli::main` binary, `config/production.yaml` reading its values from the
environment, a SeaORM entity in `models/_entities`, and the Tera view-engine
initializer. It leaves out what the endpoints do not use (auth routes, mailers,
background workers, i18n, the separate `migration` crate) and keeps the
loco-rs feature set the generator selects, plus `auth_session` for the
signed-in session of phase 2. The `users` entity (`models/_entities/users.rs`)
maps the harness's `users` table; `db.sql` is not needed because the cookie
store keeps no table.
