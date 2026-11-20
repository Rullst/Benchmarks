//! Axum baseline: the suite's endpoints with SQLx and Askama.
//!
//! Phase 2 (docs/v3-spec.md): `/world/{id}`, `/worlds`, `PUT /world/{id}`
//! and the browser routes `/form`, `/login` and `/me`. Only the browser routes
//! have the session layer (tower-sessions with its PostgreSQL store) and CSRF
//! protection (axum_csrf); the other routes keep the plain stack.

mod browser;

use askama::Template;
use axum::{
    Json, Router,
    extract::{FromRef, Path, Query, State},
    http::StatusCode,
    response::{Html, IntoResponse, Response},
    routing::get,
};
use axum_csrf::CsrfConfig;
use serde::{Deserialize, Serialize};
use sqlx::postgres::{PgPool, PgPoolOptions};

/// The application state: the database pool and the CSRF configuration
/// (`CsrfConfig::default()`: a random cookie key and salt per process).
#[derive(Clone)]
pub struct AppState {
    pool: PgPool,
    csrf: CsrfConfig,
}

impl FromRef<AppState> for PgPool {
    fn from_ref(state: &AppState) -> Self {
        state.pool.clone()
    }
}

impl FromRef<AppState> for CsrfConfig {
    fn from_ref(state: &AppState) -> Self {
        state.csrf.clone()
    }
}

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
const MAX_ID: i64 = 10_000;

/// `GET /worlds` parameters. A value that is not an integer is rejected by
/// the `Query` extractor (400); ranges are checked by hand (422).
#[derive(Deserialize)]
struct WorldsParams {
    min: Option<i64>,
    max: Option<i64>,
    limit: Option<i64>,
    page: Option<i64>,
}

/// `PUT /world/{id}` body. A missing or non-integer `randomNumber` is
/// rejected by the `Json` extractor (422; malformed JSON 400); the range is
/// checked by hand (422).
#[derive(Deserialize)]
struct WorldUpdate {
    #[serde(rename = "randomNumber")]
    random_number: i64,
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

pub(crate) fn internal_error<E>(_: E) -> StatusCode {
    StatusCode::INTERNAL_SERVER_ERROR
}

async fn text() -> &'static str {
    "Hello World"
}

async fn json() -> Json<Message> {
    Json(Message {
        message: "Hello World",
    })
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

/// `GET /world/{id}`: one row by primary key; 404 when there is none.
async fn world(State(pool): State<PgPool>, Path(id): Path<i32>) -> Result<Json<World>, StatusCode> {
    let row: Option<(i32, i32)> = sqlx::query_as(SELECT_WORLD)
        .bind(id)
        .fetch_optional(&pool)
        .await
        .map_err(internal_error)?;
    let (id, random_number) = row.ok_or(StatusCode::NOT_FOUND)?;
    Ok(Json(World { id, random_number }))
}

/// `GET /worlds?min=&max=&limit=&page=`: one filtered, ordered, paginated query.
async fn worlds(
    State(pool): State<PgPool>,
    Query(params): Query<WorldsParams>,
) -> Result<Json<Vec<World>>, StatusCode> {
    let min = params.min.unwrap_or(1);
    let max = params.max.unwrap_or(MAX_ID);
    let limit = params.limit.unwrap_or(20);
    let page = params.page.unwrap_or(1);
    let valid = (1..=MAX_ID).contains(&min)
        && (1..=MAX_ID).contains(&max)
        && min <= max
        && (1..=100).contains(&limit)
        && (1..=1000).contains(&page);
    if !valid {
        return Err(StatusCode::UNPROCESSABLE_ENTITY);
    }
    let rows: Vec<(i32, i32)> = sqlx::query_as(
        "SELECT id, randomnumber FROM world WHERE id BETWEEN $1 AND $2 ORDER BY id LIMIT $3 OFFSET $4",
    )
    .bind(min as i32)
    .bind(max as i32)
    .bind(limit)
    .bind((page - 1) * limit)
    .fetch_all(&pool)
    .await
    .map_err(internal_error)?;
    Ok(Json(
        rows.into_iter()
            .map(|(id, random_number)| World { id, random_number })
            .collect(),
    ))
}

/// `PUT /world/{id}`: one `UPDATE ... RETURNING` (Axum has no ORM); 404 when
/// the row does not exist.
async fn update_world(
    State(pool): State<PgPool>,
    Path(id): Path<i32>,
    Json(body): Json<WorldUpdate>,
) -> Result<Json<World>, StatusCode> {
    if !(1..=MAX_ID).contains(&body.random_number) {
        return Err(StatusCode::UNPROCESSABLE_ENTITY);
    }
    let row: Option<(i32, i32)> = sqlx::query_as(
        "UPDATE world SET randomnumber = $1 WHERE id = $2 RETURNING id, randomnumber",
    )
    .bind(body.random_number as i32)
    .bind(id)
    .fetch_optional(&pool)
    .await
    .map_err(internal_error)?;
    let (id, random_number) = row.ok_or(StatusCode::NOT_FOUND)?;
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
    // The only difference from frameworks/axum: no ping before an idle
    // connection is handed out (SQLx's default is true).
    let pool = PgPoolOptions::new()
        .max_connections(env_or("DB_POOL_SIZE", 16))
        .test_before_acquire(false)
        .connect(&database_url)
        .await?;
    let state = AppState {
        pool: pool.clone(),
        csrf: CsrfConfig::default(),
    };

    let app = Router::new()
        .route("/text", get(text))
        .route("/json", get(json))
        .route("/db-single", get(db_single))
        .route("/html", get(html))
        .route("/queries", get(queries))
        .route("/updates", get(updates))
        .route("/fortunes", get(fortunes))
        .route("/world/{id}", get(world).put(update_world))
        .route("/worlds", get(worlds))
        .merge(browser::routes(pool))
        .with_state(state);

    let listener = tokio::net::TcpListener::bind(("0.0.0.0", env_or("PORT", 8080_u16))).await?;
    axum::serve(listener, app).await?;
    Ok(())
}
