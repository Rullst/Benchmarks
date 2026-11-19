//! Browser routes: `/form`, `/login` and `/me` (docs/v3-spec.md, sections 4-6).
//!
//! Axum has no CSRF protection or sessions of its own. CSRF: `axum_csrf`
//! (the most-used maintained crate): the token is kept in an encrypted
//! cookie and the form carries its HMAC (`authenticity_token`). Sessions:
//! `tower-sessions` with the PostgreSQL store of `tower-sessions-sqlx-store`
//! (its table is created by `db.sql`, not at start-up). The session layer
//! wraps only these routes.

use askama::Template;
use axum::{
    Form, Json, Router,
    extract::State,
    http::StatusCode,
    response::{Html, IntoResponse, Redirect, Response},
    routing::get,
};
use axum_csrf::CsrfToken;
use serde::{Deserialize, Serialize};
use sqlx::postgres::PgPool;
use tower_sessions::{Session, SessionManagerLayer};
use tower_sessions_sqlx_store::PostgresStore;

use crate::{AppState, internal_error};

const USER_ID: &str = "user_id";

#[derive(Template)]
#[template(path = "form.html")]
struct FormPage {
    authenticity_token: String,
}

#[derive(Template)]
#[template(path = "form_result.html")]
struct FormResult {
    name: String,
    random_number: i64,
}

#[derive(Template)]
#[template(path = "login.html")]
struct LoginPage {
    authenticity_token: String,
}

/// The posted form. Every field is optional text so that the CSRF token is
/// verified before the fields are parsed and validated by hand.
#[derive(Deserialize)]
struct FormInput {
    authenticity_token: Option<String>,
    name: Option<String>,
    #[serde(rename = "randomNumber")]
    random_number: Option<String>,
}

#[derive(Deserialize)]
struct LoginInput {
    authenticity_token: Option<String>,
    username: Option<String>,
    password: Option<String>,
}

#[derive(Serialize)]
struct Me {
    id: i32,
    username: String,
    #[serde(rename = "displayName")]
    display_name: String,
}

/// The routes with the session layer; the CSRF configuration comes from the state.
pub fn routes(pool: PgPool) -> Router<AppState> {
    let sessions = SessionManagerLayer::new(PostgresStore::new(pool));
    Router::new()
        .route("/form", get(show_form).post(submit_form))
        .route("/login", get(show_login).post(login))
        .route("/me", get(me))
        .layer(sessions)
}

fn verified(token: &CsrfToken, submitted: Option<&str>) -> bool {
    submitted.is_some_and(|value| token.verify(value).is_ok())
}

fn render(page: impl Template) -> Result<Html<String>, StatusCode> {
    page.render().map(Html).map_err(internal_error)
}

/// `GET /form`: the page with the CSRF field; the response sets the CSRF cookie.
async fn show_form(token: CsrfToken) -> Result<Response, StatusCode> {
    let authenticity_token = token.authenticity_token().map_err(internal_error)?;
    Ok((token, render(FormPage { authenticity_token })?).into_response())
}

/// `POST /form`: CSRF check (403), then validation (422), then the page.
async fn submit_form(
    token: CsrfToken,
    Form(input): Form<FormInput>,
) -> Result<Html<String>, StatusCode> {
    if !verified(&token, input.authenticity_token.as_deref()) {
        return Err(StatusCode::FORBIDDEN);
    }
    let name = input.name.unwrap_or_default();
    let random_number = input
        .random_number
        .as_deref()
        .and_then(|value| value.parse::<i64>().ok())
        .filter(|value| (1..=10_000).contains(value));
    let name_length = name.chars().count();
    match random_number {
        Some(random_number) if (1..=64).contains(&name_length) => render(FormResult {
            name,
            random_number,
        }),
        _ => Err(StatusCode::UNPROCESSABLE_ENTITY),
    }
}

async fn show_login(token: CsrfToken) -> Result<Response, StatusCode> {
    let authenticity_token = token.authenticity_token().map_err(internal_error)?;
    Ok((token, render(LoginPage { authenticity_token })?).into_response())
}

/// `POST /login`: CSRF check, then the Argon2id hash of `users`; a new
/// session id on success (no session fixation), then a redirect to `/me`.
async fn login(
    State(pool): State<PgPool>,
    session: Session,
    token: CsrfToken,
    Form(input): Form<LoginInput>,
) -> Result<Response, StatusCode> {
    if !verified(&token, input.authenticity_token.as_deref()) {
        return Err(StatusCode::FORBIDDEN);
    }
    let (Some(username), Some(password)) = (input.username, input.password) else {
        return Err(StatusCode::UNPROCESSABLE_ENTITY);
    };
    let row: Option<(i32, String)> =
        sqlx::query_as("SELECT id, password_argon2id FROM users WHERE username = $1")
            .bind(&username)
            .fetch_optional(&pool)
            .await
            .map_err(internal_error)?;
    let Some((id, hash)) = row else {
        return Err(StatusCode::UNAUTHORIZED);
    };
    let valid = tokio::task::spawn_blocking(move || {
        use argon2::{Argon2, PasswordVerifier};
        Argon2::default()
            .verify_password(password.as_bytes(), hash.as_str())
            .is_ok()
    })
    .await
    .map_err(internal_error)?;
    if !valid {
        return Err(StatusCode::UNAUTHORIZED);
    }
    session.cycle_id().await.map_err(internal_error)?;
    session.insert(USER_ID, id).await.map_err(internal_error)?;
    Ok(Redirect::to("/me").into_response())
}

/// `GET /me`: the session (one read of the session table), then the user's row.
async fn me(State(pool): State<PgPool>, session: Session) -> Result<Json<Me>, StatusCode> {
    let id: i32 = session
        .get(USER_ID)
        .await
        .map_err(internal_error)?
        .ok_or(StatusCode::UNAUTHORIZED)?;
    let row: Option<(i32, String, String)> =
        sqlx::query_as("SELECT id, username, display_name FROM users WHERE id = $1")
            .bind(id)
            .fetch_optional(&pool)
            .await
            .map_err(internal_error)?;
    let (id, username, display_name) = row.ok_or(StatusCode::UNAUTHORIZED)?;
    Ok(Json(Me {
        id,
        username,
        display_name,
    }))
}
