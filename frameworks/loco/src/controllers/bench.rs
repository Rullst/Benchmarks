use loco_rs::{controller::extractor::validate::QueryValidate, prelude::*};
use serde::{Deserialize, Serialize};
use validator::ValidationError;

use crate::models::_entities::{fortune, world};

#[derive(Serialize)]
struct Message {
    message: &'static str,
}

#[derive(Serialize)]
struct WorldBody {
    id: i32,
    #[serde(rename = "randomNumber")]
    random_number: i32,
}

impl From<world::Model> for WorldBody {
    fn from(row: world::Model) -> Self {
        Self {
            id: row.id,
            random_number: row.randomnumber,
        }
    }
}

#[derive(Deserialize)]
struct QueriesParams {
    queries: Option<String>,
}

const MAX_ID: i64 = 10_000;

/// `GET /worlds` parameters, validated by `QueryValidate`: a value that is
/// not an integer is refused by the query parser, a range or `min > max` by
/// `validator` (both 400).
#[derive(Deserialize, Validate)]
#[validate(schema(function = "min_not_above_max"))]
struct WorldsParams {
    #[validate(range(min = 1, max = 10_000))]
    min: Option<i64>,
    #[validate(range(min = 1, max = 10_000))]
    max: Option<i64>,
    #[validate(range(min = 1, max = 100))]
    limit: Option<i64>,
    #[validate(range(min = 1, max = 1000))]
    page: Option<i64>,
}

fn min_not_above_max(params: &WorldsParams) -> std::result::Result<(), ValidationError> {
    if params.min.unwrap_or(1) <= params.max.unwrap_or(MAX_ID) {
        Ok(())
    } else {
        Err(ValidationError::new("min_above_max"))
    }
}

/// `PUT /world/{id}` body, validated by `JsonValidate`: malformed JSON is 400,
/// a missing or non-integer `randomNumber` 422 (Axum's `Json`), a value out of
/// range 400 (`validator`), all before the row is loaded.
#[derive(Deserialize, Validate)]
struct WorldUpdate {
    #[serde(rename = "randomNumber")]
    #[validate(range(min = 1, max = 10_000))]
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

async fn find_world(ctx: &AppContext, id: i32) -> Result<world::Model> {
    world::Entity::find_by_id(id)
        .one(&ctx.db)
        .await?
        .ok_or_else(|| Error::NotFound)
}

#[debug_handler]
async fn text() -> Result<Response> {
    format::text("Hello World")
}

#[debug_handler]
async fn json() -> Result<Response> {
    format::json(Message {
        message: "Hello World",
    })
}

#[debug_handler]
async fn db_single(State(ctx): State<AppContext>) -> Result<Response> {
    format::json(WorldBody::from(find_world(&ctx, 1).await?))
}

#[debug_handler]
async fn queries(
    State(ctx): State<AppContext>,
    Query(params): Query<QueriesParams>,
) -> Result<Response> {
    let count = query_count(&params);
    let mut worlds = Vec::with_capacity(count);
    for _ in 0..count {
        worlds.push(WorldBody::from(find_world(&ctx, random_id()).await?));
    }
    format::json(worlds)
}

/// Each row is read with `find_by_id`, given a new random number and saved with
/// `ActiveModel::update` (one UPDATE per row, no transaction, no batching).
#[debug_handler]
async fn updates(
    State(ctx): State<AppContext>,
    Query(params): Query<QueriesParams>,
) -> Result<Response> {
    let count = query_count(&params);
    let mut worlds = Vec::with_capacity(count);
    for _ in 0..count {
        let mut row = find_world(&ctx, random_id()).await?.into_active_model();
        row.randomnumber = Set(random_id());
        worlds.push(WorldBody::from(row.update(&ctx.db).await?));
    }
    format::json(worlds)
}

#[debug_handler]
async fn fortunes(
    ViewEngine(v): ViewEngine<TeraView>,
    State(ctx): State<AppContext>,
) -> Result<Response> {
    let mut fortunes = fortune::Entity::find().all(&ctx.db).await?;
    fortunes.push(fortune::Model {
        id: 0,
        message: "Additional fortune added at request time.".to_string(),
    });
    fortunes.sort_by(|a, b| a.message.cmp(&b.message));
    format::render().view(&v, "bench/fortunes.html", data!({ "fortunes": fortunes }))
}

#[debug_handler]
async fn html(ViewEngine(v): ViewEngine<TeraView>) -> Result<Response> {
    format::render().view(&v, "bench/hello.html", data!({ "name": "World" }))
}

/// `GET /world/{id}`: `find_by_id`; 404 without a row (a non-integer id is
/// refused by `Path`, 400).
#[debug_handler]
async fn world_by_id(State(ctx): State<AppContext>, Path(id): Path<i32>) -> Result<Response> {
    format::json(WorldBody::from(find_world(&ctx, id).await?))
}

/// `GET /worlds?min=&max=&limit=&page=`: one query through SeaORM's query
/// builder (`BETWEEN`, `ORDER BY`, `LIMIT`, `OFFSET`).
#[debug_handler]
async fn worlds(
    State(ctx): State<AppContext>,
    QueryValidate(params): QueryValidate<WorldsParams>,
) -> Result<Response> {
    let min = params.min.unwrap_or(1);
    let max = params.max.unwrap_or(MAX_ID);
    let limit = params.limit.unwrap_or(20);
    let page = params.page.unwrap_or(1);
    let rows = world::Entity::find()
        .filter(world::Column::Id.between(min, max))
        .order_by_asc(world::Column::Id)
        .limit(limit as u64)
        .offset(((page - 1) * limit) as u64)
        .all(&ctx.db)
        .await?;
    format::json(rows.into_iter().map(WorldBody::from).collect::<Vec<_>>())
}

/// `PUT /world/{id}`: the body is validated first; then the row is loaded
/// with `find_by_id` (404 without one), changed and saved with
/// `ActiveModel::update` (one `UPDATE ... RETURNING`).
#[debug_handler]
async fn update_world(
    State(ctx): State<AppContext>,
    Path(id): Path<i32>,
    JsonValidate(body): JsonValidate<WorldUpdate>,
) -> Result<Response> {
    let mut row = find_world(&ctx, id).await?.into_active_model();
    row.randomnumber = Set(body.random_number);
    format::json(WorldBody::from(row.update(&ctx.db).await?))
}

pub fn routes() -> Routes {
    Routes::new()
        .add("/text", get(text))
        .add("/json", get(json))
        .add("/db-single", get(db_single))
        .add("/html", get(html))
        .add("/queries", get(queries))
        .add("/updates", get(updates))
        .add("/fortunes", get(fortunes))
        .add("/world/{id}", get(world_by_id).put(update_world))
        .add("/worlds", get(worlds))
}
