//! Actix Web: the suite's endpoints with SQLx and Askama.

use actix_web::{App, HttpResponse, HttpServer, Responder, get, http::header::ContentType, web};
use askama::Template;
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
    let row: Result<(i32, i32), _> = sqlx::query_as(SELECT_WORLD)
        .bind(1_i32)
        .fetch_one(pool.get_ref())
        .await;
    match row {
        Ok((id, random_number)) => HttpResponse::Ok().json(World { id, random_number }),
        Err(_) => HttpResponse::InternalServerError().finish(),
    }
}

async fn read_worlds(pool: &PgPool, count: usize) -> Result<Vec<World>, sqlx::Error> {
    let mut worlds = Vec::with_capacity(count);
    for _ in 0..count {
        let (id, random_number): (i32, i32) = sqlx::query_as(SELECT_WORLD)
            .bind(random_id())
            .fetch_one(pool)
            .await?;
        worlds.push(World { id, random_number });
    }
    Ok(worlds)
}

/// Each row is read, given a new random number and written back with its own
/// UPDATE statement (no transaction, no batching).
async fn update_worlds(pool: &PgPool, count: usize) -> Result<Vec<World>, sqlx::Error> {
    let mut worlds = Vec::with_capacity(count);
    for _ in 0..count {
        let (id, _old): (i32, i32) = sqlx::query_as(SELECT_WORLD)
            .bind(random_id())
            .fetch_one(pool)
            .await?;
        let random_number = random_id();
        sqlx::query("UPDATE world SET randomnumber = $1 WHERE id = $2")
            .bind(random_number)
            .bind(id)
            .execute(pool)
            .await?;
        worlds.push(World { id, random_number });
    }
    Ok(worlds)
}

#[get("/queries")]
async fn queries(pool: web::Data<PgPool>, params: web::Query<QueriesParams>) -> HttpResponse {
    match read_worlds(pool.get_ref(), query_count(&params)).await {
        Ok(worlds) => HttpResponse::Ok().json(worlds),
        Err(_) => HttpResponse::InternalServerError().finish(),
    }
}

#[get("/updates")]
async fn updates(pool: web::Data<PgPool>, params: web::Query<QueriesParams>) -> HttpResponse {
    match update_worlds(pool.get_ref(), query_count(&params)).await {
        Ok(worlds) => HttpResponse::Ok().json(worlds),
        Err(_) => HttpResponse::InternalServerError().finish(),
    }
}

#[get("/fortunes")]
async fn fortunes(pool: web::Data<PgPool>) -> HttpResponse {
    let rows: Result<Vec<(i32, String)>, _> = sqlx::query_as("SELECT id, message FROM fortune")
        .fetch_all(pool.get_ref())
        .await;
    let Ok(rows) = rows else {
        return HttpResponse::InternalServerError().finish();
    };
    let mut fortunes: Vec<Fortune> = rows
        .into_iter()
        .map(|(id, message)| Fortune { id, message })
        .collect();
    fortunes.push(Fortune {
        id: 0,
        message: "Additional fortune added at request time.".to_string(),
    });
    fortunes.sort_by(|a, b| a.message.cmp(&b.message));
    match (Fortunes { fortunes }).render() {
        Ok(body) => HttpResponse::Ok().content_type(ContentType::html()).body(body),
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
            .service(queries)
            .service(updates)
            .service(fortunes)
    })
    .bind(("0.0.0.0", env_or("PORT", 8080_u16)))?
    .run()
    .await
}
