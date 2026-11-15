//! Topcoat with its documented defaults: `topcoat::start` with a
//! `module_router!`, `#[route]`/`#[page]` handlers, `view!` for HTML and
//! Toasty (the database layer `topcoat new` sets up) for /db-single.

use serde::Serialize;
use toasty::Db;
use topcoat::{
    Result,
    context::{Cx, context},
    router::{content::Json, module_router, page, route},
    view::{View, view},
};

#[derive(Debug, toasty::Model)]
#[table = "world"]
struct World {
    #[key]
    id: i32,
    randomnumber: i32,
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
