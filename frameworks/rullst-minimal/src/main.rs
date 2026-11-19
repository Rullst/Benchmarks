//! Rullst in a minimal configuration comparable to the Axum baseline: the
//! Rullst router (`routes!`), ORM (`#[derive(Orm)]`) and `html!`, served
//! directly with `axum::serve`, without `rullst::Server` and its middleware
//! stack (access log, security baseline, CSRF, security headers).

use rullst::db::Orm;
use rullst::server::{Json, Query, StatusCode};
use rullst::{Markup, Router, html, routes};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Orm, Serialize)]
#[orm(table = "world")]
pub struct World {
    pub id: i32,
    #[serde(rename = "randomNumber")]
    pub randomnumber: i32,
}

#[derive(Debug, Clone, Orm, Serialize)]
#[orm(table = "fortune")]
pub struct Fortune {
    pub id: i32,
    pub message: String,
}

#[derive(Serialize)]
struct Message {
    message: &'static str,
}

#[derive(Deserialize)]
struct QueriesParams {
    queries: Option<String>,
}

/// The `queries` parameter: an integer clamped to 1..=500, otherwise 1.
fn query_count(params: &QueriesParams) -> usize {
    let count = params
        .queries
        .as_deref()
        .and_then(|value| value.parse::<i64>().ok())
        .unwrap_or(1);
    count.clamp(1, 500) as usize
}

fn random_id() -> i32 {
    rand::random_range(1..=10_000)
}

async fn find_world(id: i32) -> Result<World, StatusCode> {
    match World::find(id).await {
        Ok(Some(world)) => Ok(world),
        Ok(None) => Err(StatusCode::NOT_FOUND),
        Err(_) => Err(StatusCode::INTERNAL_SERVER_ERROR),
    }
}

async fn text() -> &'static str {
    "Hello World"
}

async fn json() -> Json<Message> {
    Json(Message { message: "Hello World" })
}

async fn db_single() -> Result<Json<World>, StatusCode> {
    Ok(Json(find_world(1).await?))
}

async fn queries(Query(params): Query<QueriesParams>) -> Result<Json<Vec<World>>, StatusCode> {
    let count = query_count(&params);
    let mut worlds = Vec::with_capacity(count);
    for _ in 0..count {
        worlds.push(find_world(random_id()).await?);
    }
    Ok(Json(worlds))
}

/// Each row is read with `World::find`, given a new random number and saved
/// with `save()` (one UPDATE per row in its own transaction, no batching).
async fn updates(Query(params): Query<QueriesParams>) -> Result<Json<Vec<World>>, StatusCode> {
    let count = query_count(&params);
    let mut worlds = Vec::with_capacity(count);
    for _ in 0..count {
        let mut world = find_world(random_id()).await?;
        world.randomnumber = random_id();
        world
            .save()
            .await
            .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
        worlds.push(world);
    }
    Ok(Json(worlds))
}

async fn fortunes() -> Result<Markup, StatusCode> {
    let mut fortunes = Fortune::all()
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    fortunes.push(Fortune {
        id: 0,
        message: "Additional fortune added at request time.".to_string(),
    });
    fortunes.sort_by(|a, b| a.message.cmp(&b.message));
    Ok(html! {
        <!DOCTYPE html>
        <html><head><title>Fortunes</title></head><body><table>
        <tr><th>id</th><th>message</th></tr>
        @for fortune in &fortunes {
            <tr><td>{fortune.id}</td><td>{fortune.message}</td></tr>
        }
        </table></body></html>
    })
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
        get("/queries" => queries),
        get("/updates" => updates),
        get("/fortunes" => fortunes),
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
