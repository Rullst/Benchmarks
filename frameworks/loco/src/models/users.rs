//! The signed-in user for `CurrentUser` (Loco's `auth_session` feature).

use loco_rs::{auth::session::SessionUser, prelude::*};

use super::_entities::users;

/// `CurrentUser<users::Model>` reads the user's row on every request, by the
/// id the signed session cookie holds. Loco's documentation suggests a
/// non-guessable `pid`; the harness's `users` table has only the integer id,
/// which the signed cookie protects from tampering.
#[async_trait]
impl SessionUser for users::Model {
    async fn find_by_session_id(ctx: &AppContext, id: &str) -> Result<Option<Self>> {
        let Ok(id) = id.parse::<i32>() else {
            return Ok(None);
        };
        Ok(users::Entity::find_by_id(id).one(&ctx.db).await?)
    }
}

impl users::Model {
    /// Finds a user by username.
    ///
    /// # Errors
    ///
    /// When the query fails.
    pub async fn find_by_username(ctx: &AppContext, username: &str) -> Result<Option<Self>> {
        Ok(users::Entity::find()
            .filter(users::Column::Username.eq(username))
            .one(&ctx.db)
            .await?)
    }
}
