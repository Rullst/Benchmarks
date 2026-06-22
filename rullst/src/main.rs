use rullst::{Server, Router};
use serde::{Deserialize, Serialize};
use sqlx::{postgres::{PgPoolOptions, PgRow}, Row};
use std::sync::Arc;
use axum::{routing::get, extract::State, Json, http::StatusCode, response::Html};

#[derive(Serialize)]
struct Message {
    message: String,
}

#[derive(Serialize, Deserialize)]
struct User {
    id: i32,
    name: String,
}

struct AppState {
    db: sqlx::PgPool,
}

async fn text_handler() -> &'static str {
    "Hello World"
}

async fn json_handler() -> Json<Message> {
    Json(Message {
        message: "Hello World".to_string(),
    })
}

async fn html_handler() -> Html<&'static str> {
    Html("<h1>Hello, World!</h1>")
}

async fn db_single_handler(
    State(state): State<Arc<AppState>>,
) -> Result<Json<User>, StatusCode> {
    let row_result: Result<PgRow, sqlx::Error> = sqlx::query("SELECT id, name FROM users LIMIT 1")
        .fetch_one(&state.db)
        .await;

    match row_result {
        Ok(row) => {
            let user = User {
                id: row.get("id"),
                name: row.get("name"),
            };
            Ok(Json(user))
        }
        Err(_) => Err(StatusCode::INTERNAL_SERVER_ERROR),
    }
}

#[tokio::main]
async fn main() {
    let database_url = std::env::var("DATABASE_URL")
        .unwrap_or_else(|_| "postgres://postgres:postgres@localhost:5432/benchdb".to_string());

    let pool = PgPoolOptions::new()
        .max_connections(100)
        .connect(&database_url)
        .await
        .expect("Failed to create pool");

    sqlx::query("CREATE TABLE IF NOT EXISTS users (id SERIAL PRIMARY KEY, name VARCHAR(255) NOT NULL)")
        .execute(&pool)
        .await
        .unwrap();

    let count: i64 = sqlx::query_scalar("SELECT COUNT(*) FROM users")
        .fetch_one(&pool)
        .await
        .unwrap_or(0);

    if count == 0 {
        sqlx::query("INSERT INTO users (name) VALUES ($1)")
            .bind("Benchmark User")
            .execute(&pool)
            .await
            .unwrap();
    }

    let state = Arc::new(AppState { db: pool });

    let axum_router = axum::Router::new()
        .route("/text", get(text_handler))
        .route("/json", get(json_handler))
        .route("/html", get(html_handler))
        .route("/db-single", get(db_single_handler))
        .with_state(state);

    let router = Router::new().merge_axum(axum_router);

    println!("Rullst listening on 0.0.0.0:3000");
    
    Server::new(router).run(3000).await;
}
