//! `SeaORM` entity for the harness's `users` table (bench/db/phase2.sql), in
//! the format sea-orm-codegen writes for Loco apps.

use sea_orm::entity::prelude::*;

#[derive(Clone, Debug, PartialEq, Eq, DeriveEntityModel)]
#[sea_orm(table_name = "users")]
pub struct Model {
    #[sea_orm(primary_key, auto_increment = false)]
    pub id: i32,
    #[sea_orm(unique)]
    pub username: String,
    pub display_name: String,
    pub password_bcrypt: String,
    pub password_argon2id: String,
}

#[derive(Copy, Clone, Debug, EnumIter, DeriveRelation)]
pub enum Relation {}

impl ActiveModelBehavior for ActiveModel {}
