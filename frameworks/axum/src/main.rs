//! Axum baseline: the suite's four endpoints with SQLx and Askama.

use askama::Template;
use axum::{
    Json, Router,
    extract::State,
    http::StatusCode,
    response::{Html, IntoResponse, Response},
    routing::get,
};
use serde::Serialize;
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

#[derive(Template)]
#[template(path = "hello.html")]
struct Hello<'a> {
    name: &'a str,
}

async fn text() -> &'static str {
    "Hello World"
}

async fn json() -> Json<Message> {
    Json(Message { message: "Hello World" })
}

async fn db_single(State(pool): State<PgPool>) -> Result<Json<World>, StatusCode> {
    let (id, random_number): (i32, i32) =
        sqlx::query_as("SELECT id, randomnumber FROM world WHERE id = $1")
            .bind(1_i32)
            .fetch_one(&pool)
            .await
            .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    Ok(Json(World { id, random_number }))
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
        .with_state(pool);

    let listener = tokio::net::TcpListener::bind(("0.0.0.0", env_or("PORT", 8080_u16))).await?;
    axum::serve(listener, app).await?;
    Ok(())
}
