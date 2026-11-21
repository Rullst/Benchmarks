//! Every page of the site.

pub mod category;
pub mod common;
pub mod diagnostics;
pub mod endpoints;
pub mod history;
pub mod implementations;
pub mod method;
pub mod overview;
pub mod pending;
pub mod stability;
pub mod tables;

use crate::context::Ctx;
use crate::data::CategoryKey;
use crate::layout::Page;

pub fn render(ctx: &Ctx) -> Vec<Page> {
    let mut pages = vec![overview::page(ctx)];
    pages.extend(CategoryKey::ALL.iter().map(|&key| category::page(ctx, key)));
    pages.extend(stability::page(ctx));
    pages.push(endpoints::page(ctx));
    pages.push(diagnostics::page(ctx));
    pages.push(implementations::index(ctx));
    let data = ctx.data();
    pages.extend(data.results.iter().chain(&data.not_measured).map(|row| implementations::detail(ctx, row)));
    pages.push(history::page(ctx));
    pages.push(method::page(ctx));
    pages
}
