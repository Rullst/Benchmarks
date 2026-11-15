//! Actix Web: the suite's four endpoints with SQLx and Askama.

use actix_web::{App, HttpResponse, HttpServer, Responder, get, http::header::ContentType, web};
use askama::Template;
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

#[get("/text")]
async fn text() -> &'static str {
    "Hello World"
}

#[get("/json")]
async fn json() -> web::Json<Message> {
    web::Json(Message { message: "Hello World" })
}

#[get("/db-single")]
async fn db_single(pool: web::Data<PgPool>) -> HttpResponse {
    let row: Result<(i32, i32), _> =
        sqlx::query_as("SELECT id, randomnumber FROM world WHERE id = $1")
            .bind(1_i32)
            .fetch_one(pool.get_ref())
            .await;
    match row {
        Ok((id, random_number)) => HttpResponse::Ok().json(World { id, random_number }),
        Err(_) => HttpResponse::InternalServerError().finish(),
    }
}

#[get("/html")]
async fn html() -> impl Responder {
    match (Hello { name: "World" }).render() {
        Ok(body) => HttpResponse::Ok().content_type(ContentType::html()).body(body),
        Err(_) => HttpResponse::InternalServerError().finish(),
    }
}

fn env_or<T: std::str::FromStr>(name: &str, default: T) -> T {
    std::env::var(name)
        .ok()
        .and_then(|value| value.parse().ok())
        .unwrap_or(default)
}

#[actix_web::main]
async fn main() -> std::io::Result<()> {
    let database_url = std::env::var("DATABASE_URL").map_err(std::io::Error::other)?;
    let pool = PgPoolOptions::new()
        .max_connections(env_or("DB_POOL_SIZE", 16))
        .connect(&database_url)
        .await
        .map_err(std::io::Error::other)?;
    let pool = web::Data::new(pool);

    // Workers default to the number of CPUs the process may use (2 here).
    HttpServer::new(move || {
        App::new()
            .app_data(pool.clone())
            .service(text)
            .service(json)
            .service(db_single)
            .service(html)
    })
    .bind(("0.0.0.0", env_or("PORT", 8080_u16)))?
    .run()
    .await
}
