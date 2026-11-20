# Actix Web

| | |
| --- | --- |
| Version | actix-web 4.19.0 (exact versions in `Cargo.lock`) |
| Build | `cargo build --release --locked` with Rust 1.99.1, `lto = "thin"`, `codegen-units = 1` |
| Server | `HttpServer` with its default worker count: one worker per CPU the process may use (2) |
| Database | SQLx 0.9 `PgPool` with `DB_POOL_SIZE` connections (16), shared by the workers; Actix Web has no ORM |
| Templates | Askama 0.16 (`templates/`), as in the Actix examples' templating section |
| Database endpoints | as in the Axum baseline: one `SELECT` per row for `/queries`; for `/updates`, per row, that `SELECT` and one `UPDATE` (autocommit, no transaction, no batching); `/fortunes` with `SELECT id, message FROM fortune` and Askama (`templates/fortunes.html`). `web::Query` reads `queries`; random ids from `rand::random_range` (rand 0.10) |
| Request input (phase 2) | `GET /world/{id}`: `web::Path<i32>` (a non-integer id is answered 404, `PathConfig`'s default), then `SELECT … WHERE id = $1`, 404 without a row. `GET /worlds`: `web::Query` into optional `i64` fields (a non-integer is 400), ranges checked by hand (422), then one `SELECT … WHERE id BETWEEN $1 AND $2 ORDER BY id LIMIT $3 OFFSET $4`. `PUT /world/{id}`: `web::Path<i32>` and `web::Json` (malformed JSON or a missing or non-integer `randomNumber`: 400), the 1-10,000 range by hand (422) before any write, then one `UPDATE world SET randomnumber = $1 WHERE id = $2 RETURNING id, randomnumber` (no ORM), 404 without a row. Actix Web has no validation library of its own; the extractors check types and the handlers check ranges |
| CSRF | [actix-csrf](https://crates.io/crates/actix-csrf) 0.8, the CSRF middleware for Actix Web (Actix has none built in; last release 2024-11): a double-submit cookie. `GET /form` and `GET /login` get a random 32-byte token in the `__Host-Csrf-Token` cookie (its defaults: `Secure`, `HttpOnly`, `SameSite=Strict`; the token is not rotated on posts) and echo it in the hidden `csrf_token` field; `POST /form` and `POST /login` take `Csrf<web::Form<_>>`, which compares the field with the cookie (422 on a mismatch or a missing cookie, 400 when the field is missing), then the fields are validated (`web::Form` types: 400; the name's 1-64 characters and the 1-10,000 range by hand: 422). The success page is rendered by Askama (`templates/form_result.html`, HTML-escaped) as `text/html; charset=utf-8` |
| Sessions | [actix-session](https://crates.io/crates/actix-session) 0.11, the session crate of the Actix project, with its `CookieSessionStore`: Actix has no PostgreSQL session store, so the spec's rule picks the cookie store. The session state is encrypted in the `id` cookie (`CookieContentSecurity::Private`, the default; `Secure`, `HttpOnly`, `SameSite=Lax`, a browser-session cookie with a 1-day state TTL that is extended only when the state changes). The `Key` is generated once per process and shared by the two workers. `POST /login` reads `users.password_argon2id` and verifies it with the `argon2` crate (0.6, in `web::block`), renews the session and stores the user id, then answers 303 to `/me`; a wrong password is 401. `GET /me` decrypts the cookie, then reads the user's row (`SELECT … FROM users WHERE id = $1`); 401 without a session |
| Middleware scope | the CSRF and session middlewares wrap a `web::scope("")` that holds only `/form`, `/login` and `/me` (registered after the other routes, because a scope without a prefix matches every path); every other route keeps the plain stack. `PUT /world/{id}` has no CSRF check (a public JSON API route) |
| Logging | none (no `Logger` middleware) |
| Image | `gcr.io/distroless/cc-debian12:nonroot` |

Why: default `HttpServer` settings as the Actix Web documentation describes
them for production, with the same database and template crates as the Axum
baseline so the comparison is about the framework. The release profile is the
same for every Rust implementation.
