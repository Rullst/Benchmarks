//! Rullst in a minimal configuration comparable to the Axum baseline: the
//! Rullst router (`routes!`), ORM (`#[derive(Orm)]`), `html!`,
//! `ValidatedJson`/`ValidatedForm` and the session registry, served directly
//! with `axum::serve`, without `rullst::Server` and its middleware stack
//! (access log, security baseline, secure headers). CSRF protection is
//! Rullst's `csrf_middleware` on `/form` and `/login` only (`browser.rs`).

mod auth_middleware;
mod browser;

use rullst::db::Orm;
use rullst::orm::RowSnapshot;
use rullst::server::{IntoResponse, Json, Path, Query, Response, StatusCode};
use rullst::{FieldErrors, Markup, Router, Validate, ValidatedJson, ValidationError, html, routes};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Orm, Serialize)]
#[orm(table = "world")]
pub struct World {
    pub id: i32,
    #[serde(rename = "randomNumber")]
    pub randomnumber: i32,
    // `save()` writes only the columns that changed (the save mode the CLI
    // generates; 13.0.0-alpha.6 requires one).
    #[sqlx(skip)]
    #[serde(skip)]
    pub snapshot: RowSnapshot,
}

#[derive(Debug, Clone, Orm)]
#[orm(table = "fortune")]
pub struct Fortune {
    pub id: i32,
    pub message: String,
    #[sqlx(skip)]
    pub snapshot: RowSnapshot,
}

#[derive(Serialize)]
struct Message {
    message: &'static str,
}

#[derive(Deserialize)]
struct QueriesParams {
    queries: Option<String>,
}

const MAX_ID: i64 = 10_000;

/// `GET /worlds` parameters: `Query` refuses a value that is not an integer
/// (400); the constraints are checked with `FieldErrors::validate` (422, the
/// response `ValidatedJson` gives), since Rullst has no validating query
/// extractor.
#[derive(Deserialize, Validate)]
#[validate(schema(function = "min_not_above_max"))]
struct WorldsParams {
    #[validate(range(min = 1, max = 10000))]
    min: Option<i64>,
    #[validate(range(min = 1, max = 10000))]
    max: Option<i64>,
    #[validate(range(min = 1, max = 100))]
    limit: Option<i64>,
    #[validate(range(min = 1, max = 1000))]
    page: Option<i64>,
}

fn min_not_above_max(params: &WorldsParams) -> Result<(), validator::ValidationError> {
    if params.min.unwrap_or(1) <= params.max.unwrap_or(MAX_ID) {
        Ok(())
    } else {
        Err(validator::ValidationError::new("min_above_max"))
    }
}

/// `PUT /world/{id}` body, validated by `ValidatedJson` (malformed JSON or a
/// missing or non-integer `randomNumber`: 400; out of range: 422).
#[derive(Deserialize, Validate)]
struct WorldUpdate {
    #[serde(rename = "randomNumber")]
    #[validate(range(min = 1, max = 10000))]
    random_number: i32,
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
    Json(Message {
        message: "Hello World",
    })
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
/// The number is drawn again when it equals the stored one: `save()` of a
/// `RowSnapshot` model writes nothing for an unchanged value, and every row
/// must be written.
async fn updates(Query(params): Query<QueriesParams>) -> Result<Json<Vec<World>>, StatusCode> {
    let count = query_count(&params);
    let mut worlds = Vec::with_capacity(count);
    for _ in 0..count {
        let mut world = find_world(random_id()).await?;
        let mut random_number = random_id();
        while random_number == world.randomnumber {
            random_number = random_id();
        }
        world.randomnumber = random_number;
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
        snapshot: RowSnapshot::default(),
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

/// `GET /world/{id}`: `World::find`; 404 without a row (a non-integer id is
/// refused by `Path`, 400).
async fn world_by_id(Path(id): Path<i32>) -> Result<Json<World>, StatusCode> {
    Ok(Json(find_world(id).await?))
}

/// `GET /worlds?min=&max=&limit=&page=`: one query through the ORM's query
/// builder (`where_between`, `order_by`, `limit`, `offset`).
async fn worlds(Query(params): Query<WorldsParams>) -> Result<Json<Vec<World>>, Response> {
    FieldErrors::validate(&params).map_err(|errors| {
        ValidationError::ValidationError {
            errors,
            is_htmx: false,
        }
        .into_response()
    })?;
    let min = params.min.unwrap_or(1);
    let max = params.max.unwrap_or(MAX_ID);
    let limit = params.limit.unwrap_or(20);
    let page = params.page.unwrap_or(1);
    World::query()
        .where_between("id", min as i32, max as i32)
        .order_by("id")
        .limit(limit as usize)
        .offset(((page - 1) * limit) as usize)
        .get()
        .await
        .map(Json)
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR.into_response())
}

/// `PUT /world/{id}`: the body is validated first; then `World::find` (404
/// without a row), the new value and `save()` (one `UPDATE ... RETURNING` of
/// the changed column).
async fn update_world(
    Path(id): Path<i32>,
    ValidatedJson(body): ValidatedJson<WorldUpdate>,
) -> Result<Json<World>, StatusCode> {
    let mut world = find_world(id).await?;
    world.randomnumber = body.random_number;
    world
        .save()
        .await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    Ok(Json(world))
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
        get("/world/{id}" => world_by_id),
        put("/world/{id}" => update_world),
        get("/worlds" => worlds),
    ]
    .merge_axum(browser::routes().into_axum())
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
