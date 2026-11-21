//! Pieces several pages share: score flags, the ranking table with its tie groups, and the table of
//! unranked rows.

use rullst::html;
use rullst::html::Markup;

use crate::charts::{self, Scale, Tone};
use crate::context::{Ctx, split};
use crate::data::{CategoryKey, Entry, EntryStatus};
use crate::format::{self, DASH, times};
use crate::layout::table_region;

/// One extra column of a ranking table.
pub struct Column<'a> {
    pub title: String,
    pub cell: Box<dyn Fn(&Entry) -> Markup + 'a>,
}

impl<'a> Column<'a> {
    pub fn new(title: impl Into<String>, cell: impl Fn(&Entry) -> Markup + 'a) -> Column<'a> {
        Column { title: title.into(), cell: Box::new(cell) }
    }

    /// A column of plain text.
    pub fn text(title: impl Into<String>, cell: impl Fn(&Entry) -> String + 'a) -> Column<'a> {
        Column::new(title, move |e| {
            let text = cell(e);
            html! { {text} }
        })
    }
}

/// The signs a score carries: "*" CPU-cost basis, "†" database setup, "‡" PUT that did not write, "≈"
/// within the tie margin of Axum. `key` is None for the overall score.
pub fn flags(ctx: &Ctx, key: Option<CategoryKey>, entry: &Entry) -> String {
    if entry.score.is_none() {
        return String::new();
    }
    let mut out = String::new();
    if key.is_some_and(CategoryKey::is_throughput) && !entry.efficiency_runs.is_empty() {
        out.push('*');
    }
    if !entry.database_note.is_empty() {
        out.push('†');
    }
    if matches!(key, None | Some(CategoryKey::Application)) && ctx.put_flagged.contains(entry.slug.as_str()) {
        out.push('‡');
    }
    if entry.within_reference_margin == Some(true) {
        out.push('≈');
    }
    out
}

/// A score with its flags, or the reason it has none (errors with their rates).
pub fn score_text(ctx: &Ctx, key: Option<CategoryKey>, entry: &Entry) -> String {
    match entry.score {
        Some(score) => format!("{}{}", times(score), flags(ctx, key, entry)),
        None if entry.status == EntryStatus::Errors && !entry.error_runs.is_empty() => {
            let rates: Vec<String> =
                entry.error_runs.iter().map(|(ep, rate)| format!("/{ep} {:.1}%", rate * 100.0)).collect();
            format!("errors ({})", rates.join(", "))
        }
        None => entry.status.text().to_string(),
    }
}

/// "4–5 · 0.75" for a category cell of the overall table.
pub fn place_and_score(ctx: &Ctx, key: CategoryKey, entry: Option<&Entry>) -> Markup {
    let Some(entry) = entry else { return html! { {DASH} } };
    match entry.score {
        None => html! { <span class="muted">{entry.status.text()}</span> },
        Some(_) => {
            let place = format::position_text(entry);
            let score = score_text(ctx, Some(key), entry);
            html! { <span class="cell-pair"><span class="place">{place}</span>" "<span class="score-small">{score}</span></span> }
        }
    }
}

fn implementation_cell(ctx: &Ctx, root: &str, slug: &str) -> Markup {
    let href = format!("{root}implementations/{slug}/");
    let name = ctx.name(slug);
    let rullst = ctx.is_rullst(slug);
    html! {
        <th scope="row" class="impl">
            <a href={href}>{name}</a>
            @if rullst { " "<span class="tag tag-rullst">"Rullst"</span> }
        </th>
    }
}

fn score_cell(ctx: &Ctx, key: Option<CategoryKey>, entry: &Entry, scale: &Scale, tone: Tone) -> Markup {
    let text = score_text(ctx, key, entry);
    let name = ctx.name(&entry.slug);
    html! {
        <td class="score-cell">
            <span class="score-value">{text}</span>
            {charts::bar(entry.score, scale, tone, &name)}
        </td>
    }
}

fn margin_cell(entry: &Entry) -> String {
    match &entry.tie_check {
        Some(check) if entry.position.is_some() => format::pct(check.percent),
        _ => DASH.to_string(),
    }
}

fn row_class(ctx: &Ctx, entry: &Entry, base: &str) -> String {
    if ctx.is_rullst(&entry.slug) { format!("{base} is-rullst") } else { base.to_string() }
}

/// A ranking: Axum first as the reference, then the ranked implementations by position with each tie
/// group in its own `tbody` (its position range printed once), then ranked implementations without a
/// position. Diagnostics and the A/A control are not in it (see `unranked_table`).
pub fn ranking_table(
    ctx: &Ctx,
    root: &str,
    label: &str,
    caption: Markup,
    key: Option<CategoryKey>,
    entries: &[Entry],
    columns: &[Column],
) -> Markup {
    let parts = split(entries);
    let scale = Scale::new(entries.iter().filter_map(|e| e.score));
    let headers: Markup = columns.iter().map(|c| html! { <th scope="col">{c.title.as_str()}</th> }).collect();
    let extra = |entry: &Entry| -> Markup { columns.iter().map(|c| html! { <td>{(c.cell)(entry)}</td> }).collect() };
    let reference = parts.reference.map(|entry| {
        html! {
            <tbody class="group-reference">
                <tr class="row-reference">
                    <td class="pos"><span class="pos-ref">"ref."</span></td>
                    {implementation_cell(ctx, root, &entry.slug)}
                    {score_cell(ctx, key, entry, &scale, Tone::Reference)}
                    <td class="num">{DASH}</td>
                    {extra(entry)}
                </tr>
            </tbody>
        }
    });
    let groups: Markup = parts
        .groups
        .iter()
        .map(|group| {
            let size = group.len();
            let tie = size > 1;
            let rows: Markup = group
                .iter()
                .enumerate()
                .map(|(i, entry)| {
                    let place = format::position_text(entry);
                    html! {
                        <tr class={row_class(ctx, entry, "row-ranked")}>
                            @if i == 0 {
                                <td class="pos" rowspan={size}>
                                    <span class="pos-num">{place}</span>
                                    @if tie { <span class="pos-tie">"tie"</span> }
                                </td>
                            }
                            {implementation_cell(ctx, root, &entry.slug)}
                            {score_cell(ctx, key, entry, &scale, Tone::Ranked)}
                            <td class="num">{margin_cell(entry)}</td>
                            {extra(entry)}
                        </tr>
                    }
                })
                .collect();
            let class = if tie { "group group-tie" } else { "group" };
            html! { <tbody class={class}>{rows}</tbody> }
        })
        .collect();
    let unplaced: Markup = parts
        .unplaced
        .iter()
        .map(|entry| {
            let reason = if entry.reason.is_empty() { entry.status.text().to_string() } else { entry.reason.clone() };
            html! {
                <tr class={row_class(ctx, entry, "row-unplaced")}>
                    <td class="pos"><span class="pos-status">{entry.status.text()}</span></td>
                    {implementation_cell(ctx, root, &entry.slug)}
                    {score_cell(ctx, key, entry, &scale, Tone::Ranked)}
                    <td class="num">{DASH}</td>
                    {extra(entry)}
                </tr>
                <tr class="row-reason"><td></td><td colspan={columns.len() + 3}>{reason}</td></tr>
            }
        })
        .collect();
    let table = html! {
        <table class="ranking">
            <caption>{caption}</caption>
            <thead>
                <tr>
                    <th scope="col" class="pos">"Position"</th>
                    <th scope="col">"Implementation"</th>
                    <th scope="col" class="score-head">"Score vs Axum"{charts::axis(&scale)}</th>
                    <th scope="col" class="num" title="Tie margin of the comparison with the score above">"±"</th>
                    {headers}
                </tr>
            </thead>
            {reference}
            {groups}
            @if !parts.unplaced.is_empty() { <tbody class="group-unplaced">{unplaced}</tbody> }
        </table>
    };
    table_region(label, table)
}

/// Diagnostics and the A/A control of a ranking: scores without a position, with what each row measures.
pub fn unranked_table(
    ctx: &Ctx,
    root: &str,
    label: &str,
    caption: Markup,
    key: Option<CategoryKey>,
    entries: &[Entry],
    columns: &[Column],
) -> Option<Markup> {
    let parts = split(entries);
    if parts.unranked.is_empty() {
        return None;
    }
    let scale = Scale::new(entries.iter().filter_map(|e| e.score));
    let headers: Markup = columns.iter().map(|c| html! { <th scope="col">{c.title.as_str()}</th> }).collect();
    let rows: Markup = parts
        .unranked
        .iter()
        .map(|entry| {
            let note = ctx
                .row(&entry.slug)
                .map(|r| if r.listing_note.is_empty() { r.role_note.as_str() } else { r.listing_note.as_str() })
                .unwrap_or("");
            let extra: Markup = columns.iter().map(|c| html! { <td>{(c.cell)(entry)}</td> }).collect();
            html! {
                <tr class={row_class(ctx, entry, "row-unranked")}>
                    <td class="pos"><span class="pos-status">{entry.status.text()}</span></td>
                    {implementation_cell(ctx, root, &entry.slug)}
                    {score_cell(ctx, key, entry, &scale, Tone::Unranked)}
                    {extra}
                    <td class="note-cell">{crate::layout::rich(note)}</td>
                </tr>
            }
        })
        .collect();
    let table = html! {
        <table class="ranking ranking-unranked">
            <caption>{caption}</caption>
            <thead>
                <tr>
                    <th scope="col" class="pos">"Role"</th>
                    <th scope="col">"Implementation"</th>
                    <th scope="col" class="score-head">"Score vs Axum"{charts::axis(&scale)}</th>
                    {headers}
                    <th scope="col">"What it measures"</th>
                </tr>
            </thead>
            <tbody>{rows}</tbody>
        </table>
    };
    Some(table_region(label, table))
}

/// The legend of the signs a table uses.
pub fn flag_legend(put: bool, database: bool, cpu: bool) -> Markup {
    html! {
        <ul class="legend">
            <li><span class="legend-bar"></span>"Bar: the score, longer is better"</li>
            <li><span class="legend-ref"></span>"Line: Axum, the reference (1.00×)"</li>
            @if cpu { <li><b>"*"</b>" a run counted with its CPU-cost ratio (requests per CPU-second of the server and PostgreSQL) because a side was client-bound"</li> }
            @if database { <li><b>"†"</b>" a database setup the notes explain"</li> }
            @if put { <li><b>"‡"</b>" includes a PUT /world/{id} run that did not write in most measured requests"</li> }
            <li><b>"≈"</b>" within the tie margin of Axum's 1.00×: not distinguishable from Axum"</li>
            <li><b>"±"</b>" the tie margin of the comparison with the score above (the first position has none)"</li>
        </ul>
    }
}
