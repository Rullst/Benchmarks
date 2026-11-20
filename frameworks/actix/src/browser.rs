//! Browser routes: `/form`, `/login` and `/me` (docs/v3-spec.md, sections 4-6).
//!
//! Actix Web has no CSRF protection of its own. CSRF: `actix-csrf`, the
//! double-submit cookie middleware for Actix Web: `GET /form` and `GET /login`
//! set a random token in the `__Host-Csrf-Token` cookie and the page echoes it
//! in the `csrf_token` field; the `Csrf<Form<_>>` extractor compares the two.
//! Sessions: `actix-session` with its cookie store (Actix has no PostgreSQL
//! session store), the session state encrypted in the `id` cookie with a key
//! shared by every worker. Both middlewares wrap only this scope.

use actix_csrf::CsrfMiddleware;
use actix_csrf::extractor::{Csrf, CsrfGuarded, CsrfToken};
use actix_session::config::CookieContentSecurity;
use actix_session::storage::CookieSessionStore;
use actix_session::{Session, SessionMiddleware};
use actix_web::cookie::Key;
use actix_web::http::Method;
use actix_web::http::header::{self, ContentType};
use actix_web::{HttpResponse, web};
use askama::Template;
use rand_08::rngs::StdRng;
use serde::{Deserialize, Serialize};
use sqlx::postgres::PgPool;

const USER_ID: &str = "user_id";

#[derive(Template)]
#[template(path = "form.html")]
struct FormPage<'a> {
    csrf_token: &'a str,
}

#[derive(Template)]
#[template(path = "form_result.html")]
struct FormResult {
    name: String,
    random_number: i64,
}

#[derive(Template)]
#[template(path = "login.html")]
struct LoginPage<'a> {
    csrf_token: &'a str,
}

/// The posted form: the CSRF token, then the fields. A missing field or a
/// `randomNumber` that is not an integer is refused by `web::Form` (400);
/// the ranges are checked by hand (422).
#[derive(Deserialize)]
struct FormInput {
    csrf_token: CsrfToken,
    name: String,
    #[serde(rename = "randomNumber")]
    random_number: i64,
}

impl CsrfGuarded for FormInput {
    fn csrf_token(&self) -> &CsrfToken {
        &self.csrf_token
    }
}

#[derive(Deserialize)]
struct LoginInput {
    csrf_token: CsrfToken,
    username: String,
    password: String,
}

impl CsrfGuarded for LoginInput {
    fn csrf_token(&self) -> &CsrfToken {
        &self.csrf_token
    }
}

#[derive(Serialize)]
struct Me {
    id: i32,
    username: String,
    #[serde(rename = "displayName")]
    display_name: String,
}

/// The browser scope: CSRF (the cookie set by `GET /form` and `GET /login`)
/// and the cookie session around `/form`, `/login` and `/me`. Registered
/// last, because a scope without a prefix matches every path.
pub fn configure(key: Key) -> impl FnOnce(&mut web::ServiceConfig) {
    move |config| {
        let csrf = CsrfMiddleware::<StdRng>::new()
            .set_cookie(Method::GET, "/form")
            .set_cookie(Method::GET, "/login");
        let sessions = SessionMiddleware::builder(CookieSessionStore::default(), key)
            .cookie_content_security(CookieContentSecurity::Private)
            .build();
        config.service(
            web::scope("")
                .wrap(csrf)
                .wrap(sessions)
                .service(
                    web::resource("/form")
                        .route(web::get().to(show_form))
                        .route(web::post().to(submit_form)),
                )
                .service(
                    web::resource("/login")
                        .route(web::get().to(show_login))
                        .route(web::post().to(login)),
                )
                .service(web::resource("/me").route(web::get().to(me))),
        );
    }
}

fn html(page: impl Template) -> HttpResponse {
    match page.render() {
        Ok(body) => HttpResponse::Ok()
            .content_type(ContentType::html())
            .body(body),
        Err(_) => HttpResponse::InternalServerError().finish(),
    }
}

/// `GET /form`: the middleware sets the CSRF cookie; the page echoes the token.
async fn show_form(token: CsrfToken) -> HttpResponse {
    html(FormPage {
        csrf_token: token.get(),
    })
}

/// `POST /form`: CSRF check by the extractor (422), form parsing (400), the
/// ranges by hand (422), then the page with the name escaped by Askama.
async fn submit_form(form: Csrf<web::Form<FormInput>>) -> HttpResponse {
    let input = form.into_inner().into_inner();
    let name_length = input.name.chars().count();
    if !(1..=64).contains(&name_length) || !(1..=10_000).contains(&input.random_number) {
        return HttpResponse::UnprocessableEntity().finish();
    }
    html(FormResult {
        name: input.name,
        random_number: input.random_number,
    })
}

async fn show_login(token: CsrfToken) -> HttpResponse {
    html(LoginPage {
        csrf_token: token.get(),
    })
}

/// `POST /login`: CSRF check, then the Argon2id hash of `users`; on success
/// the session is renewed and holds the user id, then a redirect to `/me`.
async fn login(
    pool: web::Data<PgPool>,
    session: Session,
    form: Csrf<web::Form<LoginInput>>,
) -> HttpResponse {
    let input = form.into_inner().into_inner();
    let row: Result<Option<(i32, String)>, _> =
        sqlx::query_as("SELECT id, password_argon2id FROM users WHERE username = $1")
            .bind(&input.username)
            .fetch_optional(pool.get_ref())
            .await;
    let (id, hash) = match row {
        Ok(Some(row)) => row,
        Ok(None) => return HttpResponse::Unauthorized().finish(),
        Err(_) => return HttpResponse::InternalServerError().finish(),
    };
    let password = input.password;
    let valid = web::block(move || {
        use argon2::{Argon2, PasswordVerifier};
        Argon2::default()
            .verify_password(password.as_bytes(), hash.as_str())
            .is_ok()
    })
    .await;
    match valid {
        Ok(true) => {}
        Ok(false) => return HttpResponse::Unauthorized().finish(),
        Err(_) => return HttpResponse::InternalServerError().finish(),
    }
    session.renew();
    if session.insert(USER_ID, id).is_err() {
        return HttpResponse::InternalServerError().finish();
    }
    HttpResponse::SeeOther()
        .insert_header((header::LOCATION, "/me"))
        .finish()
}

/// `GET /me`: the session (decrypted from its cookie), then the user's row.
async fn me(pool: web::Data<PgPool>, session: Session) -> HttpResponse {
    let id = match session.get::<i32>(USER_ID) {
        Ok(Some(id)) => id,
        Ok(None) => return HttpResponse::Unauthorized().finish(),
        Err(_) => return HttpResponse::InternalServerError().finish(),
    };
    let row: Result<Option<(i32, String, String)>, _> =
        sqlx::query_as("SELECT id, username, display_name FROM users WHERE id = $1")
            .bind(id)
            .fetch_optional(pool.get_ref())
            .await;
    match row {
        Ok(Some((id, username, display_name))) => HttpResponse::Ok().json(Me {
            id,
            username,
            display_name,
        }),
        Ok(None) => HttpResponse::Unauthorized().finish(),
        Err(_) => HttpResponse::InternalServerError().finish(),
    }
}
