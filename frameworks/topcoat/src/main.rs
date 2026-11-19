//! Topcoat with its documented defaults: `topcoat::start` with a
//! `module_router!`, `#[route]`/`#[page]` handlers, `view!` for HTML and
//! Toasty (the database layer `topcoat new` sets up) for the database
//! endpoints.

use serde::Serialize;
use toasty::Db;
use topcoat::{
    Result,
    context::{Cx, context},
    router::{content::Json, module_router, page, query_params, route},
    view::{View, view},
};

#[derive(Debug, toasty::Model)]
#[table = "world"]
struct World {
    #[key]
    id: i32,
    randomnumber: i32,
}

#[derive(Debug, toasty::Model)]
#[table = "fortune"]
struct Fortune {
    #[key]
    id: i32,
    message: String,
}

#[query_params]
struct QueriesQuery {
    queries: Option<String>,
}

/// The `queries` parameter: an integer clamped to 1..=500, otherwise 1.
fn query_count(cx: &Cx) -> usize {
    let count = query_params::<QueriesQuery>(cx)
        .ok()
        .and_then(|query| query.queries.as_deref())
        .and_then(|value| value.parse::<i64>().ok())
        .unwrap_or(1);
    count.clamp(1, 500) as usize
}

fn random_id() -> i32 {
    rand::random_range(1..=10_000)
}

#[derive(Serialize)]
struct Message {
    message: &'static str,
}

#[derive(Serialize)]
struct WorldBody {
    id: i32,
    #[serde(rename = "randomNumber")]
    random_number: i32,
}

#[route(GET "./text")]
async fn text(cx: &Cx) -> Result<&'static str> {
    Ok("Hello World")
}

#[route(GET "./json")]
async fn json(cx: &Cx) -> Result<Json<Message>> {
    Ok(Json(Message { message: "Hello World" }))
}

#[route(GET "./db-single")]
async fn db_single(cx: &Cx) -> Result<Json<WorldBody>> {
    // Cloning `Db` is cheap: it is a handle to the shared pool.
    let mut db = context::<Db>(cx).clone();
    let world = World::get_by_id(&mut db, 1).await?;
    Ok(Json(WorldBody {
        id: world.id,
        random_number: world.randomnumber,
    }))
}

#[route(GET "./queries")]
async fn queries(cx: &Cx) -> Result<Json<Vec<WorldBody>>> {
    let mut db = context::<Db>(cx).clone();
    let count = query_count(cx);
    let mut worlds = Vec::with_capacity(count);
    for _ in 0..count {
        let world = World::get_by_id(&mut db, random_id()).await?;
        worlds.push(WorldBody {
            id: world.id,
            random_number: world.randomnumber,
        });
    }
    Ok(Json(worlds))
}

/// Each row is read with `get_by_id`, given a new random number and saved with
/// `update()` (one UPDATE per row, no transaction, no batching).
#[route(GET "./updates")]
async fn updates(cx: &Cx) -> Result<Json<Vec<WorldBody>>> {
    let mut db = context::<Db>(cx).clone();
    let count = query_count(cx);
    let mut worlds = Vec::with_capacity(count);
    for _ in 0..count {
        let mut world = World::get_by_id(&mut db, random_id()).await?;
        world.update().randomnumber(random_id()).exec(&mut db).await?;
        worlds.push(WorldBody {
            id: world.id,
            random_number: world.randomnumber,
        });
    }
    Ok(Json(worlds))
}

#[page("./fortunes")]
async fn fortunes(cx: &Cx) -> Result<impl View> {
    let mut db = context::<Db>(cx).clone();
    let mut fortunes = Fortune::all().exec(&mut db).await?;
    fortunes.push(Fortune {
        id: 0,
        message: "Additional fortune added at request time.".to_string(),
    });
    fortunes.sort_by(|a, b| a.message.cmp(&b.message));
    Ok(view! {
        <!DOCTYPE html>
        <html><head><title>"Fortunes"</title></head><body><table>
        <tr><th>"id"</th><th>"message"</th></tr>
        for fortune in fortunes {
            <tr><td>(fortune.id)</td><td>(fortune.message)</td></tr>
        }
        </table></body></html>
    })
}

#[page("./html")]
async fn html(cx: &Cx) -> Result<impl View> {
    let name = "World";
    Ok(view! {
        <!DOCTYPE html>
        <html><head><title>"Benchmark"</title></head><body><h1>"Hello " (name)</h1></body></html>
    })
}

fn env_or<T: std::str::FromStr>(name: &str, default: T) -> T {
    std::env::var(name)
        .ok()
        .and_then(|value| value.parse().ok())
        .unwrap_or(default)
}

#[tokio::main]
async fn main() {
    let database_url = std::env::var("DATABASE_URL").expect("DATABASE_URL is required");
    let db = Db::builder()
        .models(toasty::models!(crate::*))
        .max_pool_size(env_or("DB_POOL_SIZE", 16))
        .connect(&database_url)
        .await
        .expect("cannot connect to the database");

    // HOST and PORT come from the environment (`topcoat::start`).
    topcoat::start(module_router!().with(db).build()).await.unwrap();
}
