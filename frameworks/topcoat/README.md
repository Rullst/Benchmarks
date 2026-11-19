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
| Features | `topcoat` without default features plus `asset`, `router`, `serve`, `view`, `discover`, as `topcoat new` selects them |
| Server | `topcoat::start(module_router!().with(db).build())`, which binds `HOST`/`PORT`; Tokio starts one worker per CPU the process may use (2) |
| Routing | `#[route(GET "./text")]`, `#[route(GET "./json")]` (`Json<T>`), `#[route(GET "./db-single")]` and `#[page("./html")]` in the root module |
| Database | Toasty, the database layer `topcoat new --recommended` sets up, with its PostgreSQL driver: `#[derive(toasty::Model)] #[table = "world"]`, `World::get_by_id(&mut db, 1)`; `max_pool_size` = `DB_POOL_SIZE` (16) |
| Templates | `view!` |
| Database endpoints | `/queries`: `World::get_by_id(&mut db, id)` per row. `/updates`: per row, `get_by_id`, then `world.update().randomnumber(n).exec(&mut db)` (one `UPDATE` per row, no transaction, no batching). `/fortunes`: a `#[derive(toasty::Model)] #[table = "fortune"]` model, `Fortune::all().exec(&mut db)`, sorted in Rust, rendered with `view!` in a `#[page]` (escaped). `#[query_params]` reads `queries`; random ids from `rand::random_range` (rand 0.10) |
| Logging | none |
| Image | `gcr.io/distroless/cc-debian12:nonroot` |

Why: this follows the README, `llms.txt`, the `toasty-todo` example and the
`main.rs` that `topcoat new` generates (database handle stored in the router
context, `topcoat::start`). Topcoat's own benchmark app adds jemalloc as the
global allocator; that is not part of the generated application, so it is not
used here.
