//! Rullst in a minimal configuration comparable to the Axum baseline: the
//! Rullst router (`routes!`), ORM (`#[derive(Orm)]`) and `html!`, served
//! directly with `axum::serve`, without `rullst::Server` and its middleware
//! stack (access log, security baseline, CSRF, security headers).

use rullst::db::Orm;
use rullst::server::{Json, StatusCode};
use rullst::{Markup, Router, html, routes};
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
}

fn env_or<T: std::str::FromStr>(name: &str, default: T) -> T {
    std::env::var(name)
        .ok()
        .and_then(|value| value.parse().ok())
        .unwrap_or(default)
}

#[rullst::runtime::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let database_url = std::env::var("DATABASE_URL")?;
    Orm::init_with_options(&database_url, env_or("DB_POOL_SIZE", 16), 10).await?;

    let listener = tokio::net::TcpListener::bind(("0.0.0.0", env_or("PORT", 8080_u16))).await?;
    rullst::web::axum::serve(listener, router().into_axum()).await?;
    Ok(())
}
