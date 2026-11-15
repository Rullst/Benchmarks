//! Rullst as `cargo rullst new` generates it: `Server::new(router()).run()`
//! with the generated router layers (CSRF, health probes, security headers)
//! and the production security baseline that `RULLST_ENV=production` turns on.
//! The four endpoints use the ORM (`#[derive(Orm)]`) and `html!`.

use rullst::db::Orm;
use rullst::server::{Json, StatusCode};
use rullst::{Markup, Router, Server, html, routes};
use serde::Serialize;

#[derive(Debug, Clone, Orm, Serialize)]
#[orm(table = "world")]
pub struct World {
    pub id: i32,
    #[serde(rename = "randomNumber")]
    pub randomnumber: i32,
}

#[derive(Serialize)]
struct Message {
    message: &'static str,
}

async fn text() -> &'static str {
    "Hello World"
}

async fn json() -> Json<Message> {
    Json(Message { message: "Hello World" })
}

async fn db_single() -> Result<Json<World>, StatusCode> {
    match World::find(1).await {
        Ok(Some(world)) => Ok(Json(world)),
        Ok(None) => Err(StatusCode::NOT_FOUND),
        Err(_) => Err(StatusCode::INTERNAL_SERVER_ERROR),
    }
}

async fn page() -> Markup {
    let name = "World";
    html! {
        <!DOCTYPE html>
        <html><head><title>Benchmark</title></head><body><h1>Hello {name}</h1></body></html>
    }
}

fn router() -> Router {
    routes![
        get("/text" => text),
        get("/json" => json),
        get("/db-single" => db_single),
        get("/html" => page),
    ]
    .layer(rullst::server::from_fn(rullst::security::csrf_middleware))
    .merge_axum(rullst::health::health_router())
    .layer(rullst::server::from_fn(rullst::security::headers_middleware))
}

fn env_or<T: std::str::FromStr>(name: &str, default: T) -> T {
    std::env::var(name)
        .ok()
        .and_then(|value| value.parse().ok())
        .unwrap_or(default)
}

#[rullst::runtime::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // The only change from the generated `main`: the pool gets the suite's
    // common size instead of the SQLx default. `Server` keeps a pool that is
    // already initialized.
    let database_url = std::env::var("DATABASE_URL")?;
    Orm::init_with_options(&database_url, env_or("DB_POOL_SIZE", 16), 10).await?;

    Server::new(router()).run(env_or("PORT", 8080)).await?;
    Ok(())
}
