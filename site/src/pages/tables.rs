//! A table of implementations (one row per measured implementation), with the diagnostics and the A/A
//! control in their own row group under a divider.

use rullst::html;
use rullst::html::Markup;

use crate::context::Ctx;
use crate::data::Row;
use crate::format;
use crate::layout::table_region;

pub struct RowColumn<'a> {
    pub title: String,
    pub numeric: bool,
    pub cell: Box<dyn Fn(&Row) -> String + 'a>,
}

/// A numeric column.
pub fn num<'a>(title: impl Into<String>, cell: impl Fn(&Row) -> String + 'a) -> RowColumn<'a> {
    RowColumn { title: title.into(), numeric: true, cell: Box::new(cell) }
}

/// A text column.
pub fn text<'a>(title: impl Into<String>, cell: impl Fn(&Row) -> String + 'a) -> RowColumn<'a> {
    RowColumn { title: title.into(), numeric: false, cell: Box::new(cell) }
}

fn implementation(ctx: &Ctx, root: &str, row: &Row) -> Markup {
    let href = format!("{root}implementations/{}/", row.slug);
    let role = format::role_text(row);
    let rullst = ctx.is_rullst(&row.slug);
    html! {
        <th scope="row" class="impl">
            <a href={href}>{format::label(row)}</a>
            @if rullst { " "<span class="tag tag-rullst">"Rullst"</span> }
            @if let Some(role) = role { <span class="role">{role}</span> }
        </th>
    }
}

fn body(ctx: &Ctx, root: &str, rows: &[&Row], columns: &[RowColumn]) -> Markup {
    rows.iter()
        .map(|row| {
            let cells: Markup = columns
                .iter()
                .map(|c| {
                    let value = (c.cell)(row);
                    html! { <td class={if c.numeric { "num" } else { "text" }}>{value}</td> }
                })
                .collect();
            html! {
                <tr class={if ctx.is_rullst(&row.slug) { "is-rullst" } else { "" }}>
                    {implementation(ctx, root, row)}
                    {cells}
                </tr>
            }
        })
        .collect()
}

pub fn row_table(
    ctx: &Ctx,
    root: &str,
    label: &str,
    caption: Option<Markup>,
    main: &[&Row],
    apart: &[&Row],
    columns: &[RowColumn],
) -> Markup {
    let headers: Markup = columns
        .iter()
        .map(|c| html! { <th scope="col" class={if c.numeric { "num" } else { "text" }}>{c.title.as_str()}</th> })
        .collect();
    let span = columns.len() + 1;
    let table = html! {
        <table class="plain">
            @if let Some(caption) = caption { <caption>{caption}</caption> }
            <thead><tr><th scope="col">"Implementation"</th>{headers}</tr></thead>
            <tbody>{body(ctx, root, main, columns)}</tbody>
            @if !apart.is_empty() {
                <tbody class="group-apart">
                    <tr class="row-divider"><th scope="rowgroup" colspan={span}>"Diagnostics and the A/A control (not ranked)"</th></tr>
                    {body(ctx, root, apart, columns)}
                </tbody>
            }
        </table>
    };
    table_region(label, table)
}
