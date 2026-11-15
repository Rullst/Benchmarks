use loco_rs::prelude::*;
use serde::Serialize;

use crate::models::_entities::world;

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

#[debug_handler]
async fn text() -> Result<Response> {
    format::text("Hello World")
}

#[debug_handler]
async fn json() -> Result<Response> {
    format::json(Message { message: "Hello World" })
}

#[debug_handler]
async fn db_single(State(ctx): State<AppContext>) -> Result<Response> {
    let row = world::Entity::find_by_id(1)
        .one(&ctx.db)
        .await?
        .ok_or_else(|| Error::NotFound)?;
    format::json(WorldBody {
        id: row.id,
        random_number: row.randomnumber,
    })
}

#[debug_handler]
async fn html(ViewEngine(v): ViewEngine<TeraView>) -> Result<Response> {
    format::render().view(&v, "bench/hello.html", data!({ "name": "World" }))
}

pub fn routes() -> Routes {
    Routes::new()
        .add("/text", get(text))
        .add("/json", get(json))
        .add("/db-single", get(db_single))
        .add("/html", get(html))
}
