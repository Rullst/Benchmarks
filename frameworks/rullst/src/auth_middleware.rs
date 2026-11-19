//! Login sessions, as `cargo rullst auth` (13.0.0-alpha.6) generates
//! `src/middlewares/auth_middleware.rs` for a PostgreSQL project: each sign-in
//! is a row of `rullst_auth_sessions` (created by `db.sql`, the SQL of the
//! generated `*_create_rullst_auth_sessions_table` migration), and the
//! `rullst_session` cookie, sealed with `APP_KEY`, names it. Each request is
//! one primary-key lookup of the session and one read of the user's row.
//!
//! Differences from the generated file: the harness's `users` table has no
//! `session_epoch` column, so every account is at epoch 0 (the epoch check
//! still runs), and the long-lived-response `revalidation` helper is left out
//! (no SSE or WebSocket route uses it).
use crate::browser::User;
use rullst::async_runtime::tokio::sync::OnceCell;
use rullst::auth::session_registry::{
    AuthenticatedSession, DeviceSummary, NewSession, SessionRegistryError,
};
use rullst::server::{HeaderMap, IntoResponse, Next, Redirect, Request, Response, StatusCode};

/// The session registry over the ORM's pool (PostgreSQL, as the
/// `auth-session-registry-postgres` feature in Cargo.toml).
pub type Sessions = rullst::auth::session_registry::SessionRegistryFor<rullst::orm::RullstPool>;

static SESSIONS: OnceCell<Sessions> = OnceCell::const_new();

/// The session registry, connected on first use to the table `db.sql`
/// created (without it this fails, and no request authenticates).
pub async fn sessions() -> Result<&'static Sessions, SessionRegistryError> {
    SESSIONS
        .get_or_try_init(|| async {
            let pool = rullst::db::Orm::pool().map_err(|_| SessionRegistryError::Unavailable)?;
            Sessions::connect(pool.clone()).await
        })
        .await
}

/// Registers a sign-in of `user` at its current session epoch and returns
/// the `Set-Cookie` value. The request's `User-Agent` names the device in
/// the session list (browser and platform only).
pub async fn start_session(
    user: &User,
    headers: &HeaderMap,
) -> Result<String, SessionRegistryError> {
    let epoch = user
        .current_session_epoch()
        .ok_or(SessionRegistryError::Revoked)?;
    let login = NewSession::new(user.id, epoch).with_device(DeviceSummary::from_headers(headers));
    sessions().await?.sign_in(&login).await
}

/// Why the signed-in account could not be read. A missing, invalid,
/// expired or revoked session is not an error: it is `Ok(None)`.
#[derive(Debug)]
pub enum SessionError {
    Sessions(SessionRegistryError),
    Users(rullst::orm::Error),
}

impl std::fmt::Display for SessionError {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Sessions(error) => write!(formatter, "session registry: {error}"),
            Self::Users(error) => write!(formatter, "user query: {error}"),
        }
    }
}

/// The signed-in account of a request and its session: a live registered
/// session whose cookie carries the account's current session epoch.
pub async fn signed_in(
    headers: &HeaderMap,
) -> Result<Option<(User, AuthenticatedSession)>, SessionError> {
    if rullst::auth::extract_session_cookie(headers).is_none() {
        return Ok(None);
    }
    let registry = sessions().await.map_err(SessionError::Sessions)?;
    let session = match registry.authenticate_request(headers).await {
        Ok(session) => session,
        Err(error) if error.is_signed_out() => return Ok(None),
        Err(error) => return Err(SessionError::Sessions(error)),
    };
    match User::find(session.user_id()).await {
        Ok(Some(user)) if user.accepts_session(&session.claims()) => Ok(Some((user, session))),
        // Unknown account or an earlier session epoch.
        Ok(_) => Ok(None),
        Err(error) => Err(SessionError::Users(error)),
    }
}

/// Route middleware: runs the handler with the signed-in account's id as
/// `Extension<i32>`, the account as `Extension<User>` (loaded for this
/// request, so a handler needs no second query) and its session as
/// `Extension<AuthenticatedSession>`; any other request is sent to `/login`.
pub async fn auth_middleware(mut req: Request, next: Next) -> Response {
    let account = signed_in(req.headers()).await;
    match account {
        Ok(Some((user, session))) => {
            req.extensions_mut().insert(user.id);
            req.extensions_mut().insert(session);
            req.extensions_mut().insert(user);
            next.run(req).await
        }
        Ok(None) => Redirect::to("/login").into_response(),
        Err(error) => {
            eprintln!("Authentication failed: {error}");
            StatusCode::SERVICE_UNAVAILABLE.into_response()
        }
    }
}
