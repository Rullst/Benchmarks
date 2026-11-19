//! Browser routes: `/form`, `/login` and `/me` (docs/v3-spec.md, sections 4-6).
//!
//! Loco has no CSRF protection of its own; it is built on Axum, so the forms
//! use `axum_csrf` (the most-used maintained CSRF crate for Axum) as a layer on
//! the `/form` and `/login` routes only: the token lives in an encrypted cookie
//! and the form carries its HMAC (`authenticity_token`). The session is
//! Loco's `auth_session` feature with its default store, a signed cookie
//! (`auth.session` in `config/production.yaml`), and `CurrentUser` loads the
//! user's row on every request.

use axum::http::StatusCode;
use axum_csrf::{CsrfConfig, CsrfLayer, CsrfToken};
use loco_rs::{controller::extractor::validate::FormValidate, hash, prelude::*};
use serde::{Deserialize, Serialize};

use crate::models::_entities::users;

/// The posted form, validated by `FormValidate` (a non-integer
/// `randomNumber` is refused by the form parser, 422; a name outside 1..64
/// characters or a number outside 1..10000 by `validator`, 400). The handler
/// then verifies the CSRF token (403).
#[derive(Deserialize, Validate)]
struct FormInput {
    authenticity_token: Option<String>,
    #[validate(length(min = 1, max = 64))]
    name: String,
    #[serde(rename = "randomNumber")]
    #[validate(range(min = 1, max = 10_000))]
    random_number: i64,
}

#[derive(Deserialize)]
struct LoginInput {
    authenticity_token: Option<String>,
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

fn verified(token: &CsrfToken, submitted: Option<&str>) -> bool {
    submitted.is_some_and(|value| token.verify(value).is_ok())
}

fn forbidden() -> Response {
    StatusCode::FORBIDDEN.into_response()
}

/// `GET /form`: the page with the CSRF field; the response sets the CSRF cookie.
#[debug_handler]
async fn show_form(token: CsrfToken, ViewEngine(v): ViewEngine<TeraView>) -> Result<Response> {
    let authenticity_token = token
        .authenticity_token()
        .map_err(|_| Error::InternalServerError)?;
    let page = format::render().view(
        &v,
        "bench/form.html",
        data!({ "authenticity_token": authenticity_token }),
    )?;
    Ok((token, page).into_response())
}

/// `POST /form`: validation by `FormValidate`, the CSRF check, then the page
/// (Tera escapes the name).
#[debug_handler]
async fn submit_form(
    token: CsrfToken,
    ViewEngine(v): ViewEngine<TeraView>,
    FormValidate(input): FormValidate<FormInput>,
) -> Result<Response> {
    if !verified(&token, input.authenticity_token.as_deref()) {
        return Ok(forbidden());
    }
    format::render().view(
        &v,
        "bench/form_result.html",
        data!({ "name": input.name, "random_number": input.random_number }),
    )
}

#[debug_handler]
async fn show_login(token: CsrfToken, ViewEngine(v): ViewEngine<TeraView>) -> Result<Response> {
    let authenticity_token = token
        .authenticity_token()
        .map_err(|_| Error::InternalServerError)?;
    let page = format::render().view(
        &v,
        "bench/login.html",
        data!({ "authenticity_token": authenticity_token }),
    )?;
    Ok((token, page).into_response())
}

/// `POST /login`: CSRF check, then `loco_rs::hash::verify_password` (Argon2id)
/// against `users.password_argon2id`; on success the session is renewed and
/// holds the user id (a signed cookie), then a redirect to `/me`.
#[debug_handler]
async fn login(
    State(ctx): State<AppContext>,
    token: CsrfToken,
    session: Session,
    Form(input): Form<LoginInput>,
) -> Result<Response> {
    if !verified(&token, input.authenticity_token.as_deref()) {
        return Ok(forbidden());
    }
    let Some(user) = users::Model::find_by_username(&ctx, &input.username).await? else {
        return unauthorized("invalid credentials");
    };
    let hash = user.password_argon2id.clone();
    let valid = tokio::task::spawn_blocking(move || hash::verify_password(&input.password, &hash))
        .await
        .map_err(|_| Error::InternalServerError)?;
    if !valid {
        return unauthorized("invalid credentials");
    }
    let session = session.renew().set_user_id(user.id.to_string());
    Ok((session, format::redirect("/me")?).into_response())
}

/// `GET /me`: `CurrentUser` verifies the signed cookie and loads the user's
/// row (401 without a session).
#[debug_handler(state = AppContext)]
async fn me(CurrentUser(user): CurrentUser<users::Model>) -> Result<Response> {
    format::json(Me {
        id: user.id,
        username: user.username,
        display_name: user.display_name,
    })
}

/// `/form` and `/login`, with the CSRF layer (`CsrfConfig::default()`: a random
/// cookie key and salt per process; the server is one process).
pub fn csrf_routes() -> Routes {
    Routes::new()
        .add("/form", get(show_form).post(submit_form))
        .add("/login", get(show_login).post(login))
        .layer(CsrfLayer::new(CsrfConfig::default()))
}

/// `/me`, which needs only the session.
pub fn routes() -> Routes {
    Routes::new().add("/me", get(me))
}
