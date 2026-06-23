use actix_bench::{configure_app, AppState};
use actix_web::{web, App, HttpServer};
use sqlx::{postgres::PgPoolOptions, Row};

#[actix_web::main]
async fn main() -> std::io::Result<()> {
    let database_url = std::env::var("DATABASE_URL")
        .unwrap_or_else(|_| "postgres://postgres:postgres@localhost:5432/benchdb".to_string());

    let pool = PgPoolOptions::new()
        .max_connections(100)
        .connect(&database_url)
        .await
        .expect("Failed to create pool");

    // Auto-migrate for benchmark purposes
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

    let state = web::Data::new(AppState { db: pool });

    let port = std::env::var("PORT").unwrap_or_else(|_| "3000".to_string()).parse::<u16>().unwrap();
    println!("Actix-web listening on 0.0.0.0:{}", port);
    HttpServer::new(move || {
        App::new()
            .app_data(state.clone())
            .configure(configure_app)
    })
    .bind(("0.0.0.0", port))?
    .run()
    .await
}
