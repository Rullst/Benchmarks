//! One page per category (`/hello/` … `/startup/`): the ranking with its tie groups, the per-endpoint
//! ratios, the unranked rows apart, and how each position was decided.

use rullst::html;
use rullst::html::Markup;

use crate::components::{Column, flag_legend, ranking_table, unranked_table};
use crate::context::{Ctx, split};
use crate::data::{Category, CategoryKey, Entry, EntryStatus};
use crate::format::{self, DASH, times};
use crate::layout::{Page, Section, page_head, table_region};
use crate::pages::common::{category_nav, category_path, notes};

pub fn page(ctx: &Ctx, key: CategoryKey) -> Page {
    let path = category_path(key);
    let root = "../";
    let category = ctx.category(key);
    let rule = category.tie_rule.as_ref();
    let margins = format!(
        "Tie margins in this category: A/A {}, pooled floor {}{}.",
        format::pct(rule.and_then(|r| r.aa_percent)),
        format::pct(rule.and_then(|r| r.floor_percent)),
        rule.and_then(|r| r.floor_from).map(|n| format!(" (from {n} implementations)")).unwrap_or_default()
    );
    let eyebrow =
        if category.tier.is_empty() { "Category".to_string() } else { format!("Category · {}", category.tier) };
    let lede = html! {
        <p>{sentence(&category.description)}</p>
        <p class="muted">{margins}</p>
    };
    let columns = columns(ctx, key);
    let cpu = key.is_throughput();
    let put = key == CategoryKey::Application && ctx.put_note().is_some();
    let database = category.entries.iter().any(|e| !e.database_note.is_empty());
    let caption = html! {
        {category.title.as_str()}": positions and scores (Axum = 1.00×, higher is better)"
        @if cpu { "; endpoint columns are capacity ratios" }
        "."
    };
    let unranked = unranked_table(
        ctx,
        root,
        &format!("{}: diagnostics and the A/A control", category.title),
        html! { "Not ranked: these rows have a score and no position." },
        Some(key),
        &category.entries,
        &columns,
    );
    let body = html! {
        {page_head(&eyebrow, &category.title, lede)}
        {category_nav(root, Some(&path))}
        <section class="section" aria-labelledby="ranking">
            <h2 id="ranking">"Ranking"</h2>
            {flag_legend(put, database, cpu)}
            {ranking_table(ctx, root, &format!("{} ranking", category.title), caption, Some(key), &category.entries, &columns)}
        </section>
        @if let Some(unranked) = unranked {
            <section class="section section-unranked" aria-labelledby="unranked">
                <h2 id="unranked">"Diagnostics and the A/A control"</h2>
                <p class="section-lede">"Measured like the others and kept out of the ranking: a diagnostic isolates "
                   "one setting, the A/A control (an identical copy of Axum) gives the noise the tie margins start from. "
                   <a href={format!("{root}diagnostics/")}>"Diagnostics"</a></p>
                {unranked}
            </section>
        }
        {decided(ctx, category)}
        {endpoint_links(ctx, root, category)}
        {notes(ctx, put, database)}
    };
    Page {
        path,
        title: category.title.clone(),
        description: format!(
            "{} ranking of the Rullst Benchmarks: scores relative to Axum, tie groups and margins.",
            category.title
        ),
        section: Section::Rankings,
        results: true,
        body,
    }
}

/// The description from the data as a sentence.
pub fn sentence(text: &str) -> String {
    let mut chars = text.chars();
    match chars.next() {
        Some(first) => {
            let mut out: String = first.to_uppercase().chain(chars).collect();
            if !out.ends_with('.') {
                out.push('.');
            }
            out
        }
        None => String::new(),
    }
}

fn endpoints(category: &Category) -> Vec<String> {
    category.runs.iter().filter_map(|run| run.strip_prefix("tier1.").map(str::to_string)).collect()
}

fn capacity(entry: &Entry, endpoint: &str) -> String {
    if entry.status == EntryStatus::Reference {
        return "1.00".to_string();
    }
    let detail = &entry.detail;
    if let Some(rate) = detail.error_rates.get(endpoint).copied().flatten().filter(|r| *r > 0.01) {
        return format!("{:.1}% errors", rate * 100.0);
    }
    match detail.capacity.get(endpoint).copied().flatten() {
        Some(value) => {
            let cpu = detail.basis.get(endpoint).is_some_and(|b| b == "cpu");
            format!("{}{}", times(value), if cpu { "*" } else { "" })
        }
        None => match detail.rps_ratio.get(endpoint).copied().flatten() {
            Some(rps) => format!("({rps:.2})"),
            None => DASH.to_string(),
        },
    }
}

fn columns<'a>(ctx: &'a Ctx, key: CategoryKey) -> Vec<Column<'a>> {
    let category = ctx.category(key);
    match key {
        CategoryKey::Hello | CategoryKey::Database | CategoryKey::Application => {
            let mut columns: Vec<Column> = endpoints(category)
                .into_iter()
                .map(|ep| {
                    let title = format::endpoint_label(&ctx.data().config, &ep);
                    let flagged = ep == "world-update" && ctx.put_note().is_some();
                    let title = if flagged { format!("{title} ‡") } else { title };
                    Column::text(title, move |e| {
                        let text = capacity(e, &ep);
                        if ep == "world-update" && ctx.put_flagged.contains(e.slug.as_str()) && text != DASH {
                            format!("{text} ‡")
                        } else {
                            text
                        }
                    })
                })
                .collect();
            if key == CategoryKey::Application {
                columns.push(Column::text("CSRF", |e| e.detail.csrf.clone().unwrap_or_else(|| DASH.to_string())));
                columns.push(Column::text("Session store", |e| {
                    e.detail.session_store.clone().unwrap_or_else(|| DASH.to_string())
                }));
            }
            columns
        }
        CategoryKey::Memory => vec![
            Column::text("High-water mark (MiB)", |e| format::num(e.detail.value, 1)),
            Column::text("Axum, same runners (MiB)", |e| format::num(e.detail.reference, 1)),
            Column::text(format!("Peak after the {} logins (MiB), not scored", ctx.logins()), move |e| {
                ctx.row(&e.slug).map(|r| format::paired(r, "application.ram_peak_mib", 0)).unwrap_or_default()
            }),
        ],
        CategoryKey::Startup => vec![
            Column::text("Start-up (s)", |e| format::num(e.detail.value, 2)),
            Column::text("Axum, same runners (s)", |e| format::num(e.detail.reference, 2)),
        ],
    }
}

fn job_scores(entry: &Entry) -> Markup {
    let Some(spread) = &entry.spread else { return html! { {DASH} } };
    if spread.scores.is_empty() {
        return html! { {DASH} };
    }
    spread
        .scores
        .iter()
        .zip(&spread.cpu_models)
        .map(|(score, cpu)| {
            let cpu = format::short_cpu(cpu);
            html! { <span class="job">{times(*score)}" "<span class="muted">{cpu}</span></span> }
        })
        .collect()
}

fn spread_text(entry: &Entry) -> String {
    match &entry.spread {
        Some(spread) if entry.status != EntryStatus::Reference => {
            let mut text = format::pct(spread.effective_percent);
            if !spread.basis.is_empty() && spread.basis != "own" {
                let own = spread.own_percent.map(|p| format!(", own ±{p:.1}%")).unwrap_or_default();
                text += &format!(" ({}{own})", spread.basis);
            }
            text
        }
        _ => DASH.to_string(),
    }
}

fn check_text(ctx: &Ctx, entry: &Entry) -> String {
    match &entry.tie_check {
        Some(check) => format!(
            "{} vs {}, gap {}: {}",
            format::pct(check.percent),
            ctx.name(&check.against),
            check.gap_percent.map(|g| format!("{g:.1}%")).unwrap_or_else(|| DASH.to_string()),
            if check.tied { "same group" } else { "new group" }
        ),
        None => DASH.to_string(),
    }
}

fn reference_text(entry: &Entry) -> String {
    match entry.reference_margin.as_ref().and_then(|m| m.percent) {
        Some(p) => format!("±{p:.1}%{}", if entry.within_reference_margin == Some(true) { " ≈" } else { "" }),
        None => DASH.to_string(),
    }
}

fn limits_text(ctx: &Ctx, entry: &Entry, category: &Category) -> String {
    let Some(row) = ctx.row(&entry.slug) else { return DASH.to_string() };
    let mut parts: Vec<String> = category
        .runs
        .iter()
        .filter_map(|run| {
            let bound = format::bound(row, run);
            (!bound.is_empty()).then(|| format!("/{}: {bound}", run.trim_start_matches("tier1.")))
        })
        .collect();
    if !entry.mixed_limit_runs.is_empty() {
        let runs: Vec<&str> = entry.mixed_limit_runs.iter().map(|r| r.trim_start_matches("tier1.")).collect();
        parts.push(format!("margin widened: /{} measured at different loads on the two sides", runs.join(", /")));
    }
    if parts.is_empty() { DASH.to_string() } else { parts.join("; ") }
}

/// How each position was decided: the score of each job, the spreads and the comparison with the score above.
fn decided(ctx: &Ctx, category: &Category) -> Markup {
    let parts = split(&category.entries);
    let ordered: Vec<&Entry> = parts.groups.iter().flatten().copied().chain(parts.unplaced.iter().copied()).collect();
    let throughput = category.key.is_throughput();
    let database: Vec<String> =
        endpoints(category).into_iter().filter(|ep| format::DB_ENDPOINTS.contains(&ep.as_str())).collect();
    let config = &ctx.data().config;
    let db_headers: Markup = database
        .iter()
        .map(|ep| html! { <th scope="col">"PG µs/req "{format::endpoint_label(config, ep)}</th> })
        .collect();
    let rows: Markup = ordered
        .iter()
        .map(|entry| {
            let db_cells: Markup = database
                .iter()
                .map(|ep| {
                    let own = entry.detail.db_us_per_request.get(ep.as_str()).copied().flatten();
                    let rel = entry.detail.db_us_ratio.get(ep.as_str()).copied().flatten();
                    let text = match (own, rel) {
                        (None, _) => DASH.to_string(),
                        (Some(own), Some(rel)) => format!("{} ({rel:.2}×)", format::num(Some(own), 0)),
                        (Some(own), None) => format::num(Some(own), 0),
                    };
                    html! { <td class="num">{text}</td> }
                })
                .collect();
            let runners = ctx.row(&entry.slug).map(format::runners).unwrap_or_default();
            html! {
                <tr class={if ctx.is_rullst(&entry.slug) { "is-rullst" } else { "" }}>
                    <th scope="row">{ctx.name(&entry.slug)}</th>
                    <td class="num">{format::position_text(entry)}</td>
                    <td class="jobs">{job_scores(entry)}</td>
                    <td class="num">{spread_text(entry)}</td>
                    <td>{check_text(ctx, entry)}</td>
                    <td class="num">{reference_text(entry)}</td>
                    @if throughput { <td class="limits">{limits_text(ctx, entry, category)}</td> }
                    {db_cells}
                    <td>{runners}</td>
                </tr>
            }
        })
        .collect();
    let table = html! {
        <table class="plain">
            <caption>"Job scores: the score of each job (runner) with its CPU model. Spread: the between-job spread the "
                "tie margins use (its own, or the pooled floor). Position check: the comparison with the score above "
                "(within the margin: the same group). vs Axum margin: the margin of the ≈ check against 1.00."
                @if throughput { " PG µs/req: PostgreSQL's CPU time per request, with its ratio to Axum's on the same runners." }
            </caption>
            <thead>
                <tr>
                    <th scope="col">"Implementation"</th>
                    <th scope="col">"Position"</th>
                    <th scope="col">"Job scores"</th>
                    <th scope="col">"Spread"</th>
                    <th scope="col">"Position check"</th>
                    <th scope="col">"vs Axum margin"</th>
                    @if throughput { <th scope="col">"Limits"</th> }
                    {db_headers}
                    <th scope="col">"Runner CPUs"</th>
                </tr>
            </thead>
            <tbody>{rows}</tbody>
        </table>
    };
    html! {
        <section class="section" aria-labelledby="decided">
            <h2 id="decided">"How each position was decided"</h2>
            {table_region("How each position was decided", table)}
        </section>
    }
}

fn endpoint_links(ctx: &Ctx, root: &str, category: &Category) -> Option<Markup> {
    let eps = endpoints(category);
    if eps.is_empty() {
        return None;
    }
    let config = &ctx.data().config;
    let links: Markup = eps
        .iter()
        .map(|ep| {
            let href = format!("{root}endpoints/#ep-{ep}");
            html! { <li><a href={href}>{format::endpoint_label(config, ep)}</a></li> }
        })
        .collect();
    Some(html! {
        <section class="section" aria-labelledby="endpoint-tables">
            <h2 id="endpoint-tables">"Per-endpoint numbers"</h2>
            <p class="section-lede">"Requests per second, efficiency, latency, errors and CPU of every run in this "
               "category:"</p>
            <ul class="chips">{links}</ul>
        </section>
    })
}
