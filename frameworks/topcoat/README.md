# Topcoat

Topcoat (by the Tokio team) is an early 0.x framework: its README calls it
"early-stage and experimental" and expects breaking changes, and it has
little deployment guidance yet. This implementation pins the exact version
and uses its documented defaults; the results label it as an early 0.x
framework.

| | |
| --- | --- |
| Version | topcoat 0.12.1, Toasty 0.11.0 (exact pins and `Cargo.lock`) |
| Build | `cargo build --release --locked` with Rust 1.99.1 and the release profile every Rust implementation uses (`lto = "thin"`, `codegen-units = 1`) |
| Features | `topcoat` without default features plus `asset`, `router`, `serve`, `view`, `discover`, as `topcoat new` selects them, and `session` and `cookie` (both in Topcoat's default feature set) for the signed-in session of phase 2; `argon2` 0.6 for the login (Topcoat has no password hasher) |
| Server | `topcoat::start(module_router!().with(db).build())`, which binds `HOST`/`PORT`; Tokio starts one worker per CPU the process may use (2) |
| Routing | `#[route(GET "./text")]`, `#[route(GET "./json")]` (`Json<T>`), `#[route(GET "./db-single")]` and `#[page("./html")]` in the root module |
| Database | Toasty, the database layer `topcoat new --recommended` sets up, with its PostgreSQL driver: `#[derive(toasty::Model)] #[table = "world"]`, `World::get_by_id(&mut db, 1)`; `max_pool_size` = `DB_POOL_SIZE` (16) |
| Templates | `view!` |
| Database endpoints | `/queries`: `World::get_by_id(&mut db, id)` per row. `/updates`: per row, `get_by_id`, then `world.update().randomnumber(n).exec(&mut db)` (one `UPDATE` per row, no transaction, no batching). `/fortunes`: a `#[derive(toasty::Model)] #[table = "fortune"]` model, `Fortune::all().exec(&mut db)`, sorted in Rust, rendered with `view!` in a `#[page]` (escaped). `#[query_params]` reads `queries`; random ids from `rand::random_range` (rand 0.10) |
| Request input (phase 2) | `GET /world/{id}` and `PUT /world/{id}`: `path_param!(id: i32 else not_found)`, so a non-integer id is 404; `World::filter_by_id(id).first()`, 404 without a row. `GET /worlds`: `#[query_params(error = bad_request)]` into optional `i64` fields (a non-integer is 400), ranges checked by hand (400), then one query through Toasty's builder (`World::filter(id >= min AND id <= max).order_by(id.asc()).limit(..).offset(..)`). `PUT /world/{id}`: `content::Json<WorldUpdate>` (malformed JSON or a missing or non-integer `randomNumber`: 400), the range by hand (400) before any read or write, then `filter_by_id(..).first()` (404) and `world.update().randomnumber(n).exec(&mut db)` (one `UPDATE`). Topcoat has no validation library; its extractors check types |
| CSRF | the router's built-in `OriginPolicy`, on by default for every route (design `fetch-metadata`, no token): an unsafe request (`POST`, `PUT`, …) with `Sec-Fetch-Site` other than `same-origin`/`none` is refused with 403 before the handler runs; without that header, `Origin` must match `Host`; a request with neither header (a non-browser client, such as the harness's `PUT`) passes. `GET /form` therefore has no hidden field. `POST /form` (`#[page(POST "./form")]`) parses `content::Form<FormInput>` (400 for a missing or non-integer field), checks the name's 1-64 characters and the 1-10,000 range by hand (400), and renders the page with `view!` (escaped), `text/html; charset=utf-8` |
| Sessions | Topcoat's built-in `session` feature: `session::start(cx)` issues a fresh 32-byte token in the `__Host-session` cookie (`Secure`, `HttpOnly`, `SameSite=Lax`, 30 days) and returns its SHA-256 hash and expiry, which the application stores; Topcoat leaves the record to the app ("You choose the database and schema"). Here it is a `UserSession` Toasty model on the `user_sessions` table (hash, hex encoded, as the primary key; user id; expiry in Unix seconds), created by [`db.sql`](db.sql), not at start-up. `POST /login` loads the user by `username` with Toasty, verifies `users.password_argon2id` with the `argon2` crate (in `spawn_blocking`), starts the session, inserts its record and answers 303 to `/me`; a wrong password is 401. `GET /me` reads `session::token_hash(cx)`, then the record (`filter_by_token_hash`, rejected when expired) and the user's row (`User::filter_by_id`): two `SELECT`s; 401 without a valid session |
| Middleware scope | Topcoat's `CookieLayer` (needed by the session's cookie token store) wraps only `/login` and `/me`, through `LayerFn`s registered on those paths (a layer with a path wraps only the handlers under it); `OriginPolicy` is the router's default for every route, as before. `PUT /world/{id}` is sent without `Origin` or `Sec-Fetch-Site`, as a non-browser JSON client, and passes it |
| Logging | none |
| Image | `gcr.io/distroless/cc-debian12:nonroot` |

Why: this follows the README, `llms.txt`, the `toasty-todo` example and the
`main.rs` that `topcoat new` generates (database handle stored in the router
context, `topcoat::start`). Topcoat's own benchmark app adds jemalloc as the
global allocator; that is not part of the generated application, so it is not
used here.
