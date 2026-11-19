//! Topcoat with its documented defaults: `topcoat::start` with a
//! `module_router!`, `#[route]`/`#[page]` handlers, `view!` for HTML and
//! Toasty (the database layer `topcoat new` sets up) for the database
//! endpoints.
//!
//! Phase 2 (docs/v3-spec.md): `/world/{id}`, `/worlds`, `PUT /world/{id}`
//! and the browser routes `/form`, `/login` and `/me`. Cross-origin form posts
//! are refused by the router's default `OriginPolicy` (on for every route, as
//! Topcoat ships it); the session token is carried in a cookie, so the cookie
//! layer wraps `/login` and `/me` only.

use std::fmt::Write as _;
use std::time::{SystemTime, UNIX_EPOCH};

use serde::{Deserialize, Serialize};
use toasty::Db;
use topcoat::{
    Result,
    context::{Cx, context},
    cookie::CookieLayer,
    router::{
        Body, Layer, LayerFn, LayerFuture, Next,
        content::{Form, Json},
        error::{RouterErrorExt, SeeOther, bad_request, see_other, unauthorized},
        module_router, page, path_param, query_params, route,
    },
    session::{self, TokenHash},
    view::{View, view},
};

#[derive(Debug, toasty::Model)]
#[table = "world"]
struct World {
    #[key]
    id: i32,
    randomnumber: i32,
}

#[derive(Debug, toasty::Model)]
#[table = "fortune"]
struct Fortune {
    #[key]
    id: i32,
    message: String,
}

/// The harness's `users` table (bench/db/phase2.sql); the model maps the
/// columns this app reads.
#[derive(Debug, toasty::Model)]
#[table = "users"]
struct User {
    #[key]
    id: i32,
    #[unique]
    username: String,
    display_name: String,
    password_argon2id: String,
}

/// A session record (`db.sql`): the hash of the token Topcoat issued, hex
/// encoded, the user id and the expiry in Unix seconds.
#[derive(Debug, toasty::Model)]
#[table = "user_sessions"]
struct UserSession {
    #[key]
    token_hash: String,
    user_id: i32,
    expires_at: i64,
}

#[query_params]
struct QueriesQuery {
    queries: Option<String>,
}

/// The `queries` parameter: an integer clamped to 1..=500, otherwise 1.
fn query_count(cx: &Cx) -> usize {
    let count = query_params::<QueriesQuery>(cx)
        .ok()
        .and_then(|query| query.queries.as_deref())
        .and_then(|value| value.parse::<i64>().ok())
        .unwrap_or(1);
    count.clamp(1, 500) as usize
}

const MAX_ID: i64 = 10_000;

path_param!(id: i32 else not_found);

/// `GET /worlds` parameters: a value that is not an integer is answered 400
/// by `#[query_params(error = bad_request)]`; the ranges are checked by hand
/// (400).
#[query_params(error = bad_request)]
struct WorldsQuery {
    min: Option<i64>,
    max: Option<i64>,
    limit: Option<i64>,
    page: Option<i64>,
}

/// `PUT /world/{id}` body: malformed JSON or a missing or non-integer
/// `randomNumber` is answered 400 by `Json`; the range is checked by hand.
#[derive(Deserialize)]
struct WorldUpdate {
    #[serde(rename = "randomNumber")]
    random_number: i64,
}

fn random_id() -> i32 {
    rand::random_range(1..=10_000)
}

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

#[route(GET "./text")]
async fn text(cx: &Cx) -> Result<&'static str> {
    Ok("Hello World")
}

#[route(GET "./json")]
async fn json(cx: &Cx) -> Result<Json<Message>> {
    Ok(Json(Message {
        message: "Hello World",
    }))
}

#[route(GET "./db-single")]
async fn db_single(cx: &Cx) -> Result<Json<WorldBody>> {
    // Cloning `Db` is cheap: it is a handle to the shared pool.
    let mut db = context::<Db>(cx).clone();
    let world = World::get_by_id(&mut db, 1).await?;
    Ok(Json(WorldBody {
        id: world.id,
        random_number: world.randomnumber,
    }))
}

#[route(GET "./queries")]
async fn queries(cx: &Cx) -> Result<Json<Vec<WorldBody>>> {
    let mut db = context::<Db>(cx).clone();
    let count = query_count(cx);
    let mut worlds = Vec::with_capacity(count);
    for _ in 0..count {
        let world = World::get_by_id(&mut db, random_id()).await?;
        worlds.push(WorldBody {
            id: world.id,
            random_number: world.randomnumber,
        });
    }
    Ok(Json(worlds))
}

/// Each row is read with `get_by_id`, given a new random number and saved with
/// `update()` (one UPDATE per row, no transaction, no batching).
#[route(GET "./updates")]
async fn updates(cx: &Cx) -> Result<Json<Vec<WorldBody>>> {
    let mut db = context::<Db>(cx).clone();
    let count = query_count(cx);
    let mut worlds = Vec::with_capacity(count);
    for _ in 0..count {
        let mut world = World::get_by_id(&mut db, random_id()).await?;
        world
            .update()
            .randomnumber(random_id())
            .exec(&mut db)
            .await?;
        worlds.push(WorldBody {
            id: world.id,
            random_number: world.randomnumber,
        });
    }
    Ok(Json(worlds))
}

#[page("./fortunes")]
async fn fortunes(cx: &Cx) -> Result<impl View> {
    let mut db = context::<Db>(cx).clone();
    let mut fortunes = Fortune::all().exec(&mut db).await?;
    fortunes.push(Fortune {
        id: 0,
        message: "Additional fortune added at request time.".to_string(),
    });
    fortunes.sort_by(|a, b| a.message.cmp(&b.message));
    Ok(view! {
        <!DOCTYPE html>
        <html><head><title>"Fortunes"</title></head><body><table>
        <tr><th>"id"</th><th>"message"</th></tr>
        for fortune in fortunes {
            <tr><td>(fortune.id)</td><td>(fortune.message)</td></tr>
        }
        </table></body></html>
    })
}

/// `GET /world/{id}`: one row by primary key; 404 when there is none or when
/// the id is not an integer (`path_param!(id: i32 else not_found)`).
#[route(GET "./world/{id}")]
async fn world_by_id(cx: &Cx) -> Result<Json<WorldBody>> {
    let id = *id(cx)?;
    let mut db = context::<Db>(cx).clone();
    let world = World::filter_by_id(id)
        .first()
        .exec(&mut db)
        .await?
        .ok_or_not_found()?;
    Ok(Json(WorldBody {
        id: world.id,
        random_number: world.randomnumber,
    }))
}

/// `GET /worlds?min=&max=&limit=&page=`: one query through Toasty's query
/// builder (filter, `ORDER BY`, `LIMIT`, `OFFSET`).
#[route(GET "./worlds")]
async fn world_page(cx: &Cx) -> Result<Json<Vec<WorldBody>>> {
    let query = query_params::<WorldsQuery>(cx)?;
    let min = query.min.unwrap_or(1);
    let max = query.max.unwrap_or(MAX_ID);
    let limit = query.limit.unwrap_or(20);
    let page = query.page.unwrap_or(1);
    let valid = (1..=MAX_ID).contains(&min)
        && (1..=MAX_ID).contains(&max)
        && min <= max
        && (1..=100).contains(&limit)
        && (1..=1000).contains(&page);
    if !valid {
        return Err(bad_request("min, max, limit or page out of range").into());
    }
    let mut db = context::<Db>(cx).clone();
    let id = World::fields().id();
    let rows = World::filter(id.clone().ge(min as i32).and(id.clone().le(max as i32)))
        .order_by(id.asc())
        .limit(limit as usize)
        .offset(((page - 1) * limit) as usize)
        .exec(&mut db)
        .await?;
    Ok(Json(
        rows.into_iter()
            .map(|world| WorldBody {
                id: world.id,
                random_number: world.randomnumber,
            })
            .collect(),
    ))
}

/// `PUT /world/{id}`: the body is validated first; then the row is loaded
/// (404 without one) and saved with `update()` (one `UPDATE`).
#[route(PUT "./world/{id}")]
async fn update_world(cx: &Cx, Json(body): Json<WorldUpdate>) -> Result<Json<WorldBody>> {
    if !(1..=MAX_ID).contains(&body.random_number) {
        return Err(bad_request("randomNumber must be 1..=10000").into());
    }
    let id = *id(cx)?;
    let mut db = context::<Db>(cx).clone();
    let mut world = World::filter_by_id(id)
        .first()
        .exec(&mut db)
        .await?
        .ok_or_not_found()?;
    world
        .update()
        .randomnumber(body.random_number as i32)
        .exec(&mut db)
        .await?;
    Ok(Json(WorldBody {
        id: world.id,
        random_number: world.randomnumber,
    }))
}

/// The posted form: `name` and an integer `randomNumber` (`Form` answers 400
/// when one is missing or not an integer); the ranges are checked by hand.
#[derive(Deserialize)]
struct FormInput {
    name: String,
    #[serde(rename = "randomNumber")]
    random_number: i64,
}

#[derive(Deserialize)]
struct LoginInput {
    username: String,
    password: String,
}

#[derive(Serialize)]
struct Me {
    id: i32,
    username: String,
    #[serde(rename = "displayName")]
    display_name: String,
}

/// `GET /form`. There is no hidden token: the router's `OriginPolicy` checks
/// `Sec-Fetch-Site` (then `Origin` against `Host`) on every unsafe request.
#[page("./form")]
async fn form_page(cx: &Cx) -> Result<impl View> {
    Ok(view! {
        <!DOCTYPE html>
        <html><head><title>"Form"</title></head><body>
        <form method="post" action="/form">
        <input type="text" name="name"><input type="number" name="randomNumber">
        <button type="submit">"Send"</button>
        </form>
        </body></html>
    })
}

/// `POST /form`: `OriginPolicy` (403 for a cross-site post) before the
/// handler, `Form` parsing (400), the ranges (400), then the page.
#[page(POST "./form")]
async fn form_submit(cx: &Cx, Form(input): Form<FormInput>) -> Result<impl View> {
    let name_length = input.name.chars().count();
    if !(1..=64).contains(&name_length) || !(1..=MAX_ID).contains(&input.random_number) {
        return Err(bad_request("name must be 1-64 characters, randomNumber 1..=10000").into());
    }
    let (name, random_number) = (input.name, input.random_number);
    Ok(view! {
        <!DOCTYPE html>
        <html><head><title>"Form"</title></head><body><h1>"Hello, " (name)</h1><p>(random_number)</p></body></html>
    })
}

#[page("./login")]
async fn login_page(cx: &Cx) -> Result<impl View> {
    Ok(view! {
        <!DOCTYPE html>
        <html><head><title>"Login"</title></head><body>
        <form method="post" action="/login">
        <input type="text" name="username"><input type="password" name="password">
        <button type="submit">"Sign in"</button>
        </form>
        </body></html>
    })
}

/// The session record's key: the token hash, hex encoded.
fn record_key(hash: &TokenHash) -> String {
    let mut key = String::with_capacity(64);
    for byte in hash.iter() {
        let _ = write!(key, "{byte:02x}");
    }
    key
}

fn unix_seconds(time: SystemTime) -> i64 {
    time.duration_since(UNIX_EPOCH)
        .map_or(0, |elapsed| elapsed.as_secs() as i64)
}

/// `POST /login`: the Argon2id hash of `users` (the `argon2` crate, in
/// `spawn_blocking`), then `session::start` (a fresh token in the session
/// cookie) and its record, then a redirect to `/me`. A wrong password is 401.
#[route(POST "./login")]
async fn login(cx: &Cx, Form(input): Form<LoginInput>) -> Result<SeeOther> {
    let mut db = context::<Db>(cx).clone();
    let user = User::filter_by_username(input.username)
        .first()
        .exec(&mut db)
        .await?
        .ok_or_unauthorized()?;
    let (password, hash) = (input.password, user.password_argon2id);
    let valid = tokio::task::spawn_blocking(move || {
        use argon2::{Argon2, PasswordVerifier};
        Argon2::default()
            .verify_password(password.as_bytes(), hash.as_str())
            .is_ok()
    })
    .await?;
    if !valid {
        return Err(unauthorized().into());
    }
    let session = session::start(cx).await?;
    UserSession::create()
        .token_hash(record_key(&session.token_hash))
        .user_id(user.id)
        .expires_at(unix_seconds(session.expires_at))
        .exec(&mut db)
        .await?;
    Ok(see_other("/me"))
}

/// `GET /me`: the session record by the token's hash, then the user's row
/// (two Toasty lookups); 401 without a valid session.
#[route(GET "./me")]
async fn me(cx: &Cx) -> Result<Json<Me>> {
    let hash = session::token_hash(cx).await?.ok_or_unauthorized()?;
    let mut db = context::<Db>(cx).clone();
    let record = UserSession::filter_by_token_hash(record_key(&hash))
        .first()
        .exec(&mut db)
        .await?
        .filter(|record| record.expires_at > unix_seconds(SystemTime::now()))
        .ok_or_unauthorized()?;
    let user = User::filter_by_id(record.user_id)
        .first()
        .exec(&mut db)
        .await?
        .ok_or_unauthorized()?;
    Ok(Json(Me {
        id: user.id,
        username: user.username,
        display_name: user.display_name,
    }))
}

/// The cookie jar the session token needs, as a layer on one path.
fn cookie_jar<'a>(cx: &'a Cx, body: Body, next: Next<'a>) -> LayerFuture<'a> {
    static COOKIES: CookieLayer = CookieLayer::new();
    COOKIES.handle(cx, body, next)
}

#[page("./html")]
async fn html(cx: &Cx) -> Result<impl View> {
    let name = "World";
    Ok(view! {
        <!DOCTYPE html>
        <html><head><title>"Benchmark"</title></head><body><h1>"Hello " (name)</h1></body></html>
    })
}

fn env_or<T: std::str::FromStr>(name: &str, default: T) -> T {
    std::env::var(name)
        .ok()
        .and_then(|value| value.parse().ok())
        .unwrap_or(default)
}

#[tokio::main]
async fn main() {
    let database_url = std::env::var("DATABASE_URL").expect("DATABASE_URL is required");
    let db = Db::builder()
        .models(toasty::models!(crate::*))
        .max_pool_size(env_or("DB_POOL_SIZE", 16))
        .connect(&database_url)
        .await
        .expect("cannot connect to the database");

    // HOST and PORT come from the environment (`topcoat::start`). The cookie
    // layer (Topcoat's `CookieLayer`) wraps only the routes that use the
    // session, through path-scoped `LayerFn`s; the default `OriginPolicy`
    // and session settings (a `__Host-` cookie, 30 days) are unchanged.
    let router = module_router!()
        .layer(LayerFn::new(Some("/login"), cookie_jar))
        .layer(LayerFn::new(Some("/me"), cookie_jar))
        .with(db)
        .build();
    topcoat::start(router).await.unwrap();
}
