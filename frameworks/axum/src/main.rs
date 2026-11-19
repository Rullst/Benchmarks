//! Axum baseline: the suite's endpoints with SQLx and Askama.

use askama::Template;
use axum::{
    Json, Router,
    extract::{Query, State},
    http::StatusCode,
    response::{Html, IntoResponse, Response},
    routing::get,
};
use serde::{Deserialize, Serialize};
use sqlx::postgres::{PgPool, PgPoolOptions};

#[derive(Serialize)]
struct Message {
    message: &'static str,
}

#[derive(Serialize)]
struct World {
    id: i32,
    #[serde(rename = "randomNumber")]
    random_number: i32,
}

struct Fortune {
    id: i32,
    message: String,
}

#[derive(Template)]
#[template(path = "hello.html")]
struct Hello<'a> {
    name: &'a str,
}

#[derive(Template)]
#[template(path = "fortunes.html")]
struct Fortunes {
    fortunes: Vec<Fortune>,
}

#[derive(Deserialize)]
struct QueriesParams {
    queries: Option<String>,
}

const SELECT_WORLD: &str = "SELECT id, randomnumber FROM world WHERE id = $1";

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

fn internal_error<E>(_: E) -> StatusCode {
    StatusCode::INTERNAL_SERVER_ERROR
}

async fn text() -> &'static str {
    "Hello World"
}

async fn json() -> Json<Message> {
    Json(Message { message: "Hello World" })
}

async fn db_single(State(pool): State<PgPool>) -> Result<Json<World>, StatusCode> {
    let (id, random_number): (i32, i32) = sqlx::query_as(SELECT_WORLD)
        .bind(1_i32)
        .fetch_one(&pool)
        .await
        .map_err(internal_error)?;
    Ok(Json(World { id, random_number }))
}

async fn queries(
    State(pool): State<PgPool>,
    Query(params): Query<QueriesParams>,
) -> Result<Json<Vec<World>>, StatusCode> {
    let count = query_count(&params);
    let mut worlds = Vec::with_capacity(count);
    for _ in 0..count {
        let (id, random_number): (i32, i32) = sqlx::query_as(SELECT_WORLD)
            .bind(random_id())
            .fetch_one(&pool)
            .await
            .map_err(internal_error)?;
        worlds.push(World { id, random_number });
    }
    Ok(Json(worlds))
}

/// Each row is read, given a new random number and written back with its own
/// UPDATE statement (no transaction, no batching).
async fn updates(
    State(pool): State<PgPool>,
    Query(params): Query<QueriesParams>,
) -> Result<Json<Vec<World>>, StatusCode> {
    let count = query_count(&params);
    let mut worlds = Vec::with_capacity(count);
    for _ in 0..count {
        let (id, _old): (i32, i32) = sqlx::query_as(SELECT_WORLD)
            .bind(random_id())
            .fetch_one(&pool)
            .await
            .map_err(internal_error)?;
        let random_number = random_id();
        sqlx::query("UPDATE world SET randomnumber = $1 WHERE id = $2")
            .bind(random_number)
            .bind(id)
            .execute(&pool)
            .await
            .map_err(internal_error)?;
        worlds.push(World { id, random_number });
    }
    Ok(Json(worlds))
}

async fn fortunes(State(pool): State<PgPool>) -> Result<Response, StatusCode> {
    let rows: Vec<(i32, String)> = sqlx::query_as("SELECT id, message FROM fortune")
        .fetch_all(&pool)
        .await
        .map_err(internal_error)?;
    let mut fortunes: Vec<Fortune> = rows
        .into_iter()
        .map(|(id, message)| Fortune { id, message })
        .collect();
    fortunes.push(Fortune {
        id: 0,
        message: "Additional fortune added at request time.".to_string(),
    });
    fortunes.sort_by(|a, b| a.message.cmp(&b.message));
    let body = (Fortunes { fortunes }).render().map_err(internal_error)?;
    Ok(Html(body).into_response())
}

async fn html() -> Response {
    match (Hello { name: "World" }).render() {
        Ok(body) => Html(body).into_response(),
        Err(_) => StatusCode::INTERNAL_SERVER_ERROR.into_response(),
    }
}

fn env_or<T: std::str::FromStr>(name: &str, default: T) -> T {
    std::env::var(name)
        .ok()
        .and_then(|value| value.parse().ok())
        .unwrap_or(default)
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let database_url = std::env::var("DATABASE_URL")?;
    let pool = PgPoolOptions::new()
        .max_connections(env_or("DB_POOL_SIZE", 16))
        .connect(&database_url)
        .await?;

    let app = Router::new()
        .route("/text", get(text))
        .route("/json", get(json))
        .route("/db-single", get(db_single))
        .route("/html", get(html))
        .route("/queries", get(queries))
        .route("/updates", get(updates))
        .route("/fortunes", get(fortunes))
        .with_state(pool);

    let listener = tokio::net::TcpListener::bind(("0.0.0.0", env_or("PORT", 8080_u16))).await?;
    axum::serve(listener, app).await?;
    Ok(())
}
