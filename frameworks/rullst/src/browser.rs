//! Browser routes: `/form`, `/login` and `/me` (docs/v3-spec.md,
//! sections 4-6), with the mechanisms `cargo rullst new` and
//! `cargo rullst auth` (13.0.0-alpha.6) generate.
//!
//! CSRF: `Server`'s security baseline (the double-submit `rullst_csrf`
//! cookie; the page embeds the token masked per response in `_token`) checks
//! every state-changing request before the handlers run. Validation:
//! `ValidatedForm` (`#[derive(Validate)]`). Sessions: the session registry
//! of `auth_middleware.rs`; the login takes the generated
//! `credential_rate_limit` and bounded Argon2id work.
use crate::auth_middleware::{auth_middleware, start_session};
use rullst::async_runtime::tokio::sync::Semaphore;
use rullst::db::Orm;
use rullst::orm::RowSnapshot;
use rullst::security::CsrfToken;
use rullst::server::{
    Extension, Form, HeaderMap, HeaderValue, IntoResponse, Json, Next, Redirect, Request, Response,
    StatusCode, from_fn, header,
};
use rullst::{Markup, Router, Validate, ValidatedForm, html, routes};
use serde::{Deserialize, Serialize};
use std::sync::{Arc, LazyLock};
use std::time::Duration;

/// The harness's `users` table (bench/db/phase2.sql), with the columns this
/// app reads. The generated `User` has a `session_epoch` column; this table
/// has none, so every account is at epoch 0.
#[derive(Debug, Clone, Orm)]
#[orm(table = "users")]
pub struct User {
    pub id: i32,
    pub username: String,
    pub display_name: String,
    pub password_argon2id: String,
    // `save()` writes only the columns that changed.
    #[sqlx(skip)]
    pub snapshot: RowSnapshot,
}

const SESSION_EPOCH: u64 = 0;

impl User {
    pub async fn find_by_username(username: &str) -> Result<Option<Self>, rullst::orm::Error> {
        Self::query()
            .where_eq("username", username.to_owned())
            .first()
            .await
    }

    /// The epoch to put in this account's login cookies.
    pub fn current_session_epoch(&self) -> Option<u64> {
        Some(SESSION_EPOCH)
    }

    /// Whether a decoded login cookie was issued for this account at its
    /// current session epoch.
    pub fn accepts_session(&self, claims: &rullst::auth::SessionClaims) -> bool {
        claims.user_id == self.id
            && self
                .current_session_epoch()
                .is_some_and(|epoch| claims.verify_epoch(epoch).is_ok())
    }
}

/// The posted form, validated by `ValidatedForm`: a missing field or a
/// `randomNumber` that is not an integer is 400, a constraint failure 422.
/// The baseline has already checked `_token` against the cookie.
#[derive(Deserialize, Validate)]
pub struct FormInput {
    #[validate(length(min = 1, max = 64))]
    pub name: String,
    #[serde(rename = "randomNumber")]
    #[validate(range(min = 1, max = 10000))]
    pub random_number: i64,
}

#[derive(Deserialize)]
pub struct LoginDto {
    pub username: String,
    pub password: String,
}

#[derive(Serialize)]
struct Me {
    id: i32,
    username: String,
    #[serde(rename = "displayName")]
    display_name: String,
}

/// `GET /form`: the page with the masked CSRF token the baseline minted (it
/// sets the `rullst_csrf` cookie on this response).
async fn form_page(Extension(csrf_token): Extension<CsrfToken>) -> Markup {
    html! {
        <!DOCTYPE html>
        <html><head><title>Form</title></head><body>
        <form method="post" action="/form">
            <input type="hidden" name="_token" value={csrf_token.as_str()} />
            <input type="text" name="name" />
            <input type="number" name="randomNumber" />
            <button type="submit">Send</button>
        </form>
        </body></html>
    }
}

/// `POST /form`: CSRF by the baseline (403), `ValidatedForm` (400/422), then
/// the page, the name escaped by `html!`.
async fn form_submit(ValidatedForm(input): ValidatedForm<FormInput>) -> Markup {
    let FormInput {
        name,
        random_number,
    } = input;
    html! {
        <!DOCTYPE html>
        <html><head><title>Form</title></head><body><h1>"Hello, "{name}</h1><p>{random_number}</p></body></html>
    }
}

fn login_page(csrf_token: &str) -> Markup {
    html! {
        <!DOCTYPE html>
        <html><head><title>Login</title></head><body>
        <form method="post" action="/login">
            <input type="hidden" name="_token" value={csrf_token} />
            <input type="text" name="username" />
            <input type="password" name="password" />
            <button type="submit">Sign in</button>
        </form>
        </body></html>
    }
}

async fn login_view(Extension(csrf_token): Extension<CsrfToken>) -> Markup {
    login_page(csrf_token.as_str())
}

// From the generated `auth_controller.rs`.
const DUMMY_PASSWORD_HASH: &str =
    "$argon2id$v=19$m=19456,t=2,p=1$VE9CZ2d5dHVyWldOajNXZA$M0zU6o5hE/R6B+nJ9hX8+A";

/// Each Argon2id hash or verification holds about 19 MiB on Tokio's blocking
/// pool, so a burst of submissions must not run unbounded.
const MAX_CONCURRENT_PASSWORD_WORK: usize = 4;
/// How long a submission waits for password capacity before receiving 503.
const PASSWORD_WORK_WAIT: Duration = Duration::from_secs(2);
/// Credential submissions each client may make per minute (burst and
/// refill). Benchmark deviation: the generated value is 10; the harness signs
/// in 125 users from 127.0.0.1 at the start of every round (README).
const CREDENTIAL_ATTEMPTS_PER_MINUTE: f64 = 1000.0;

static PASSWORD_WORK: LazyLock<Arc<Semaphore>> =
    LazyLock::new(|| Arc::new(Semaphore::new(MAX_CONCURRENT_PASSWORD_WORK)));

static CREDENTIAL_LIMITER: LazyLock<rullst::RateLimiter> = LazyLock::new(|| {
    rullst::RateLimiter::new(rullst::RateLimitConfig::per_minute(
        CREDENTIAL_ATTEMPTS_PER_MINUTE,
    ))
});

/// Route middleware for `POST /login`, as the generated router mounts it:
/// credential submissions are budgeted per client before the handler runs.
async fn credential_rate_limit(request: Request, next: Next) -> Response {
    rullst::rate_limit_middleware(
        rullst::RateLimiter::clone(&CREDENTIAL_LIMITER),
        request,
        next,
    )
    .await
}

/// Runs the Argon2id verification on the blocking pool while holding one of
/// the bounded permits (`None`: no capacity within the wait, or a panic).
async fn verify_password(password: String, hash: String) -> Option<bool> {
    let permit = rullst::runtime::time::timeout(
        PASSWORD_WORK_WAIT,
        Arc::clone(&*PASSWORD_WORK).acquire_owned(),
    )
    .await
    .ok()?
    .ok()?;
    rullst::runtime::task::spawn_blocking(move || {
        let valid = rullst::auth::verify_password(&password, &hash);
        drop(permit);
        valid
    })
    .await
    .ok()
}

/// `POST /login`: CSRF by the baseline, then the user by `username` and
/// `rullst::auth::verify_password` (Argon2id, `users.password_argon2id`);
/// a registered session and a redirect to `/me`, or 401.
async fn login_submit(headers: HeaderMap, Form(payload): Form<LoginDto>) -> Response {
    let user = match User::find_by_username(&payload.username).await {
        Ok(user) => user,
        Err(error) => {
            eprintln!("Authentication query failed: {error}");
            return StatusCode::SERVICE_UNAVAILABLE.into_response();
        }
    };
    let password_hash = user
        .as_ref()
        .map_or(DUMMY_PASSWORD_HASH, |candidate| {
            candidate.password_argon2id.as_str()
        })
        .to_owned();
    let Some(password_valid) = verify_password(payload.password, password_hash).await else {
        return StatusCode::SERVICE_UNAVAILABLE.into_response();
    };
    let Some(user) = user.filter(|_| password_valid) else {
        return (StatusCode::UNAUTHORIZED, "Incorrect username or password").into_response();
    };
    match start_session(&user, &headers).await {
        Ok(cookie) => match HeaderValue::from_str(&cookie) {
            Ok(cookie) => {
                let mut response = Redirect::to("/me").into_response();
                response.headers_mut().insert(header::SET_COOKIE, cookie);
                response
            }
            Err(_) => StatusCode::INTERNAL_SERVER_ERROR.into_response(),
        },
        Err(error) => {
            eprintln!("Session creation failed: {error}");
            StatusCode::SERVICE_UNAVAILABLE.into_response()
        }
    }
}

/// `GET /me`, behind `auth_middleware`: the account it loaded for this
/// request (the session's row, then the user's row).
async fn me(Extension(user): Extension<User>) -> Json<Me> {
    Json(Me {
        id: user.id,
        username: user.username,
        display_name: user.display_name,
    })
}

/// The browser routes, as the generated router mounts the auth routes:
/// `credential_rate_limit` on `POST /login`, `auth_middleware` on `/me`.
pub fn routes() -> Router {
    let signed_in = routes![get("/me" => me)].layer(from_fn(auth_middleware));
    let router = routes![
        get("/form" => form_page),
        post("/form" => form_submit),
        get("/login" => login_view),
    ]
    .merge_axum(signed_in.into_axum());
    router.route(
        "/login",
        rullst::routing::post(login_submit).layer(from_fn(credential_rate_limit)),
    )
}
