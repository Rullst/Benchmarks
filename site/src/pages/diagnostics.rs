//! `/diagnostics/`: the unranked rows (axum-no-ping, Rullst minimal) and the A/A control, apart from the
//! rankings, with what each measures and the tie margins the control gives.

use rullst::html;
use rullst::html::Markup;

use crate::charts::{self, Scale, Tone};
use crate::components::score_text;
use crate::context::Ctx;
use crate::data::{CategoryKey, Row};
use crate::format::{self, DASH};
use crate::layout::{Page, Section, page_head, readme, rich, table_region};

pub fn page(ctx: &Ctx) -> Page {
    let root = "../";
    let rows: Vec<&Row> =
        ctx.measured().into_iter().filter(|r| !r.is_baseline && r.role != crate::data::Role::Ranked).collect();
    let cards: Markup = rows
        .iter()
        .map(|row| {
            let note = if row.listing_note.is_empty() { row.role_note.as_str() } else { row.listing_note.as_str() };
            let href = format!("{root}implementations/{}/", row.slug);
            html! {
                <article class="card card-wide">
                    <h3><a href={href}>{format::label(row)}</a></h3>
                    <p class="role">{format::role_text(row).unwrap_or("")}</p>
                    <p>{rich(note)}</p>
                </article>
            }
        })
        .collect();
    let lede = html! {
        <p>"These rows are measured exactly like the ranked implementations, in alternating rounds against Axum "
           "on the same runners, and kept out of every ranking: each diagnostic isolates one setting, and the A/A "
           "control, an identical copy of Axum, shows how far two identical servers drift apart, which is where the "
           "tie margins start."</p>
    };
    let body = html! {
        {page_head("Not ranked", "Diagnostics and the A/A control", lede)}
        <section class="section" aria-labelledby="rows">
            <h2 id="rows">"What each row measures"</h2>
            <div class="cards">{cards}</div>
        </section>
        {scores(ctx, root, &rows)}
        {rullst_gap(ctx)}
        {pool_note(ctx)}
        {control(ctx)}
    };
    Page {
        path: "diagnostics/".to_string(),
        title: "Diagnostics".to_string(),
        description: "The unranked diagnostics and the A/A control of the Rullst Benchmarks.".to_string(),
        section: Section::Diagnostics,
        results: true,
        body,
    }
}

fn scores(ctx: &Ctx, root: &str, rows: &[&Row]) -> Markup {
    let headers: Markup = CategoryKey::ALL
        .iter()
        .map(|&key| html! { <th scope="col" class="num">{ctx.category(key).title.as_str()}</th> })
        .collect();
    let overall = ctx.data().rankings.overall.as_ref().filter(|_| ctx.data().rankings.publish_overall);
    let lines: Markup = rows
        .iter()
        .map(|row| {
            let cells: Markup = CategoryKey::ALL
                .iter()
                .map(|&key| {
                    let text =
                        ctx.entry(key, &row.slug).map(|e| score_text(ctx, Some(key), e)).unwrap_or(DASH.to_string());
                    html! { <td class="num">{text}</td> }
                })
                .collect();
            let total = overall
                .and_then(|o| o.entries.iter().find(|e| e.slug == row.slug))
                .map(|e| score_text(ctx, None, e))
                .unwrap_or(DASH.to_string());
            let href = format!("{root}implementations/{}/", row.slug);
            html! {
                <tr>
                    <th scope="row"><a href={href}>{format::label(row)}</a></th>
                    <td class="num">{total}</td>
                    {cells}
                    <td>{format::runners(row)}</td>
                </tr>
            }
        })
        .collect();
    let table = html! {
        <table class="plain">
            <caption>"Scores relative to Axum (1.00×), computed like the ranked rows' and given no position."</caption>
            <thead><tr><th scope="col">"Implementation"</th><th scope="col" class="num">"Overall"</th>{headers}<th scope="col">"Runner CPUs"</th></tr></thead>
            <tbody>{lines}</tbody>
        </table>
    };
    html! {
        <section class="section" aria-labelledby="scores">
            <h2 id="scores">"Their scores"</h2>
            {table_region("Scores of the diagnostics and the A/A control", table)}
        </section>
    }
}

/// Rullst as generated next to Rullst minimal, per category: what the generated production stack costs.
fn rullst_gap(ctx: &Ctx) -> Option<Markup> {
    let generated = ctx.row("rullst")?;
    let minimal = ctx.row("rullst-minimal")?;
    let mut values = Vec::new();
    for key in CategoryKey::ALL {
        values.extend(ctx.entry(key, "rullst").and_then(|e| e.score));
        values.extend(ctx.entry(key, "rullst-minimal").and_then(|e| e.score));
    }
    let scale = Scale::new(values);
    let lines: Markup = CategoryKey::ALL
        .iter()
        .map(|&key| {
            let a = ctx.entry(key, "rullst");
            let b = ctx.entry(key, "rullst-minimal");
            let cell = |entry: Option<&crate::data::Entry>, tone: Tone, name: &str| {
                let text = entry.map(|e| score_text(ctx, Some(key), e)).unwrap_or(DASH.to_string());
                let bar = charts::bar(entry.and_then(|e| e.score), &scale, tone, name);
                html! { <td class="score-cell"><span class="score-value">{text}</span>{bar}</td> }
            };
            html! {
                <tr>
                    <th scope="row">{ctx.category(key).title.as_str()}</th>
                    {cell(a, Tone::Ranked, &format::label(generated))}
                    {cell(b, Tone::Unranked, &format::label(minimal))}
                </tr>
            }
        })
        .collect();
    let table = html! {
        <table class="ranking compare">
            <caption>"The same Rullst version measured twice: as "<code>"cargo rullst new"</code>" generates it "
                "(ranked) and without the generated production middleware (diagnostic)."</caption>
            <thead><tr>
                <th scope="col">"Category"</th>
                <th scope="col" class="score-head">{format::label(generated)}{charts::axis(&scale)}</th>
                <th scope="col" class="score-head">{format::label(minimal)}{charts::axis(&scale)}</th>
            </tr></thead>
            <tbody>{lines}</tbody>
        </table>
    };
    Some(html! {
        <section class="section" aria-labelledby="rullst-gap">
            <h2 id="rullst-gap">"Rullst as generated and Rullst minimal"</h2>
            <p class="section-lede">"The gap between the two rows shows what the default production stack costs "
               "(WAF, CSRF protection, secure cookies, security headers). Rullst minimal is not how "
               <code>"cargo rullst new"</code>" sets up an application, so it takes no position."</p>
            {table_region("Rullst as generated and minimal", table)}
        </section>
    })
}

/// The connection-pool note (bench/report.py POOL_NOTE) with the no-ping diagnostic's scores.
fn pool_note(ctx: &Ctx) -> Option<Markup> {
    ctx.row("axum-no-ping")?;
    let score = |key| ctx.entry(key, "axum-no-ping").and_then(|e| e.score).map(format::times);
    let measured = match (score(CategoryKey::Database), score(CategoryKey::Application)) {
        (Some(db), Some(app)) => {
            format!("in these results Axum scored {db} in Database and {app} in Application with it switched off")
        }
        _ => "it has no Database and Application scores in these results".to_string(),
    };
    Some(html! {
        <section class="section" aria-labelledby="pool">
            <h2 id="pool">"Database-layer defaults"</h2>
            <p>"The Database and Application rankings partly measure the defaults of each stack's database layer, and "
               "they differ: SQLx (Axum, Actix Web, Loco, Rullst) tests each pooled connection with a round trip "
               "before handing it out ("<code>"test_before_acquire"</code>", on by default; the unranked "
               <code>"axum-no-ping"</code>" diagnostic, measured for Axum only, shows its size: "{measured}"); "
               "node-postgres (Fastify, NestJS) sends unprepared statements; Laravel on PHP-FPM opens a new "
               "PostgreSQL connection for every request; Npgsql (ASP.NET Core) resets a pooled connection's state "
               "before each query EF Core runs; GORM (Gin) wraps each write in a transaction by default; Rails uses 6 "
               "of its 16 connections. "<a href={readme("fairness")}>"Fairness"</a>" and each folder README list the "
               "settings changed from the defaults, and why."</p>
        </section>
    })
}

fn control(ctx: &Ctx) -> Markup {
    let rankings = &ctx.data().rankings;
    let lines: Markup = rankings
        .categories
        .iter()
        .map(|c| {
            let margin = rankings.tie_margins.get(c.key.slug());
            let scores = margin
                .map(|m| m.scores.iter().map(|s| format::times(*s)).collect::<Vec<_>>().join(", "))
                .unwrap_or_default();
            let rule = c.tie_rule.as_ref();
            html! {
                <tr>
                    <th scope="row">{c.title.as_str()}</th>
                    <td class="num">{format::pct(rule.and_then(|r| r.aa_percent).or(margin.and_then(|m| m.percent)))}</td>
                    <td class="num">{scores}</td>
                    <td class="num">{format::pct(rule.and_then(|r| r.floor_percent))}</td>
                    <td class="num">{rule.and_then(|r| r.floor_from).map(|n| n.to_string()).unwrap_or(DASH.to_string())}</td>
                </tr>
            }
        })
        .collect();
    let table = html! {
        <table class="plain">
            <caption>"A/A margin: the largest deviation from 1.00 of the A/A control's scores, per job and pooled. "
                "Pooled floor: the median between-job spread of the ranked implementations measured on at least two "
                "jobs. Two scores tie when their gap is within the largest of the A/A margin, the root of the sum of "
                "squares of their two spreads and the pooled floor."</caption>
            <thead><tr>
                <th scope="col">"Category"</th>
                <th scope="col" class="num">"A/A margin"</th>
                <th scope="col" class="num">"A/A control scores (per job, pooled)"</th>
                <th scope="col" class="num">"Pooled floor"</th>
                <th scope="col" class="num">"Floor from (implementations)"</th>
            </tr></thead>
            <tbody>{lines}</tbody>
        </table>
    };
    html! {
        <section class="section" aria-labelledby="control">
            <h2 id="control">"Tie margins from the A/A control"</h2>
            {table_region("Tie margins", table)}
            <p class="table-note"><a href={readme("how-the-scores-are-computed")}>"How the scores are computed"</a></p>
        </section>
    }
}
