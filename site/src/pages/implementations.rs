//! `/implementations/` and one page per implementation: versions, settings, notes, runner CPUs, scores.

use rullst::html;
use rullst::html::Markup;

use crate::charts::{self, Scale, Tone};
use crate::components::score_text;
use crate::context::Ctx;
use crate::data::{CategoryKey, Row};
use crate::format::{self, DASH, median, ratio, serves};
use crate::layout::{Page, REPO, Section, page_head, rich, table_region};
use crate::pages::tables::{row_table, text};

fn group_name(group: &str) -> &str {
    match group {
        "rust" => "Rust",
        "full-stack" => "Full-stack frameworks",
        "reference" => "Popular references",
        other => other,
    }
}

pub fn index(ctx: &Ctx) -> Page {
    let root = "../";
    let all: Vec<&Row> = ctx.data().results.iter().chain(&ctx.data().not_measured).collect();
    let (main, apart): (Vec<&Row>, Vec<&Row>) =
        all.into_iter().partition(|r| r.is_baseline || r.role == crate::data::Role::Ranked);
    let columns = vec![
        text("Group", |r: &Row| group_name(&r.group).to_string()),
        text("Version", |r: &Row| r.framework_version.clone()),
        text("Language", |r: &Row| r.language.clone()),
        text("Runtime", |r: &Row| r.runtime.clone()),
        text("Server", |r: &Row| r.server.clone()),
        text("Workers", |r: &Row| r.workers.clone()),
        text("Database layer", |r: &Row| r.database_layer.clone()),
        text("Templates", |r: &Row| r.template_engine.clone()),
        text("Status", |r: &Row| format::status_text(r).to_string()),
    ];
    let lede = html! {
        <p>"Each implementation follows its framework's documentation for production: release build, pinned "
           "versions and lockfiles, the framework's standard database layer and template engine, its documented way "
           "to run in production. Each folder's README cites the documentation behind every setting. "
           <a href={format!("{REPO}/tree/main/frameworks")}>"frameworks/"</a></p>
    };
    let structure: Markup = ctx
        .data()
        .results
        .iter()
        .filter(|r| !r.structure_note.is_empty())
        .map(|r| html! { <li><b>{format::label(r)}": "</b>{rich(&r.structure_note)}</li> })
        .collect();
    let any_structure = ctx.data().results.iter().any(|r| !r.structure_note.is_empty());
    let body = html! {
        {page_head("Implementations", "What was measured", lede)}
        {row_table(ctx, root, "Implementations", None, &main, &apart, &columns)}
        @if any_structure {
            <section class="section" aria-labelledby="structure">
                <h2 id="structure">"Structural differences"</h2>
                <p class="section-lede">"What else runs inside the server's 2 vCPUs, and runtime versions."</p>
                <ul class="footnotes">{structure}</ul>
            </section>
        }
    };
    Page {
        path: "implementations/".to_string(),
        title: "Implementations".to_string(),
        description: "The implementations of the Rullst Benchmarks: versions, runtimes, servers, database layers."
            .to_string(),
        section: Section::Implementations,
        results: true,
        body,
    }
}

fn fact(label: &str, value: &str) -> Markup {
    if value.is_empty() {
        return html! { <div><dt>{label}</dt><dd>{DASH}</dd></div> };
    }
    html! { <div><dt>{label}</dt><dd>{rich(value)}</dd></div> }
}

pub fn detail(ctx: &Ctx, row: &Row) -> Page {
    let name = format::label(row);
    let role = format::role_text(row).unwrap_or("ranked");
    let source = row.dependency_source.as_ref().map(|s| s.label.clone()).unwrap_or_default();
    let versions: Markup = row
        .versions
        .iter()
        .map(|(package, version)| html! { <li><code>{package.as_str()}</code>" "{version.as_str()}</li> })
        .collect();
    let jobs: Markup = row
        .jobs
        .iter()
        .map(|job| {
            let cpu = job.cpu_model.as_deref().map(format::short_cpu).unwrap_or(DASH.to_string());
            let rounds = job.rounds.map(|r| r.to_string()).unwrap_or(DASH.to_string());
            html! { <tr><th scope="row">{job.job}</th><td>{cpu}</td><td class="num">{rounds}</td><td>{job.status.as_str()}</td></tr> }
        })
        .collect();
    let notes: Vec<(&str, &str)> = [
        ("Problem", row.problem.as_str()),
        ("Role", row.role_note.as_str()),
        ("Listing", row.listing_note.as_str()),
        ("Structure", row.structure_note.as_str()),
        ("Database", row.database_note.as_str()),
        ("Maturity", row.maturity_note.as_str()),
    ]
    .into_iter()
    .filter(|(_, v)| !v.is_empty())
    .collect();
    let note_items: Markup = notes.iter().map(|(k, v)| html! { <li><b>{*k}": "</b>{rich(v)}</li> }).collect();
    let phase2 = row.phase2.as_ref().map(|p| {
        let csrf = p.csrf.as_ref().map(|m| format!("{} ({}): {}", m.design, m.source, m.mechanism)).unwrap_or_default();
        let session =
            p.session.as_ref().map(|m| format!("{} ({}): {}", m.store, m.source, m.mechanism)).unwrap_or_default();
        html! {
            <section class="section" aria-labelledby="phase2">
                <h2 id="phase2">"Application endpoints: mechanisms"</h2>
                <dl class="facts">
                    {fact("Validation", &p.validation)}
                    {fact("CSRF", &csrf)}
                    {fact("Session store", &session)}
                </dl>
            </section>
        }
    });
    let lede = html! {
        <p>{format!("{} {} · {} · {}", row.name, row.framework_version, row.language, group_name(&row.group))}" · "{role}</p>
    };
    let folder = format!("{REPO}/tree/main/frameworks/{}", row.slug);
    let body = html! {
        {page_head("Implementation", &name, lede)}
        <p><a class="button" href={folder}>{format!("frameworks/{} on GitHub", row.slug)}</a></p>
        {scores(ctx, row)}
        <section class="section" aria-labelledby="settings">
            <h2 id="settings">"Settings"</h2>
            <dl class="facts">
                {fact("Runtime", &row.runtime)}
                {fact("Server", &row.server)}
                {fact("Workers", &row.workers)}
                {fact("Database layer", &row.database_layer)}
                {fact("Templates", &row.template_engine)}
                {fact("Logging", &row.logging)}
                {fact("Dependency source", &source)}
                {fact("Status", format::status_text(row))}
            </dl>
        </section>
        @if !notes.is_empty() {
            <section class="section" aria-labelledby="impl-notes">
                <h2 id="impl-notes">"Notes"</h2>
                <ul class="footnotes">{note_items}</ul>
            </section>
        }
        {phase2}
        {ratios(ctx, row)}
        <section class="section" aria-labelledby="versions">
            <h2 id="versions">"Measured versions"</h2>
            <ul class="chips">{versions}</ul>
        </section>
        <section class="section" aria-labelledby="jobs">
            <h2 id="jobs">"Runner jobs"</h2>
            {table_region("Runner jobs", html! {
                <table class="plain">
                    <caption>"Each job ran on its own GitHub-hosted runner; the CPU model differs between jobs."</caption>
                    <thead><tr><th scope="col">"Job"</th><th scope="col">"CPU model"</th><th scope="col" class="num">"Rounds"</th><th scope="col">"Status"</th></tr></thead>
                    <tbody>{jobs}</tbody>
                </table>
            })}
        </section>
    };
    Page {
        path: format!("implementations/{}/", row.slug),
        title: name.clone(),
        description: format!("{name} in the Rullst Benchmarks: settings, versions, scores and runner CPUs."),
        section: Section::Implementations,
        results: true,
        body,
    }
}

fn scores(ctx: &Ctx, row: &Row) -> Option<Markup> {
    if !format::is_measured(row) {
        return None;
    }
    let entries: Vec<(CategoryKey, Option<&crate::data::Entry>)> =
        CategoryKey::ALL.iter().map(|&k| (k, ctx.entry(k, &row.slug))).collect();
    let scale = Scale::new(entries.iter().filter_map(|(_, e)| e.and_then(|e| e.score)));
    let tone = if row.is_baseline {
        Tone::Reference
    } else if row.role == crate::data::Role::Ranked {
        Tone::Ranked
    } else {
        Tone::Unranked
    };
    let lines: Markup = entries
        .iter()
        .map(|(key, entry)| {
            let place = entry.map(format::position_text).unwrap_or(DASH.to_string());
            let text = entry.map(|e| score_text(ctx, Some(*key), e)).unwrap_or(DASH.to_string());
            let margin = entry.and_then(|e| e.tie_check.as_ref()).and_then(|c| c.percent);
            let href = format!("../../{}/", key.slug());
            html! {
                <tr>
                    <th scope="row"><a href={href}>{ctx.category(*key).title.as_str()}</a></th>
                    <td class="num">{place}</td>
                    <td class="score-cell"><span class="score-value">{text}</span>{charts::bar(entry.and_then(|e| e.score), &scale, tone, &format::label(row))}</td>
                    <td class="num">{format::pct(margin)}</td>
                </tr>
            }
        })
        .collect();
    let stability = ctx
        .data()
        .rankings
        .stability
        .as_ref()
        .and_then(|s| s.entries.iter().find(|e| e.slug == row.slug))
        .and_then(|e| e.result)
        .map(|r| r.text())
        .unwrap_or(DASH);
    Some(html! {
        <section class="section" aria-labelledby="scores">
            <h2 id="scores">"Scores"</h2>
            {table_region("Scores", html! {
                <table class="ranking compare">
                    <caption>{format!("Score relative to Axum (1.00×, higher is better) and position among the {} ranked implementations; Stability: {stability}.", ctx.ranked)}</caption>
                    <thead><tr><th scope="col">"Category"</th><th scope="col" class="num">"Position"</th><th scope="col" class="score-head">"Score"{charts::axis(&scale)}</th><th scope="col" class="num">"±"</th></tr></thead>
                    <tbody>{lines}</tbody>
                </table>
            })}
            <p class="table-note">"Runner CPUs: "{format::runners(row)}</p>
        </section>
    })
}

fn ratios(ctx: &Ctx, row: &Row) -> Option<Markup> {
    if !format::is_measured(row) {
        return None;
    }
    let config = &ctx.data().config;
    let lines: Markup = config
        .tiers
        .tier1
        .endpoints
        .iter()
        .map(|ep| {
            let base = format!("tier1.{ep}");
            let served = serves(row, ep);
            let (rps, vs, eff, p99, err) = if served {
                (
                    format::range(row, &format!("{base}.rps"), 0),
                    ratio(row, &format!("{base}.rps")),
                    format::num(median(row, &format!("{base}.rps_per_cpu")), 0),
                    format::num(median(row, &format!("{base}.latency_ms.p99")), 2),
                    format::error_rate(median(row, &format!("{base}.error_rate"))),
                )
            } else {
                let ni = || "n/i".to_string();
                (ni(), ni(), ni(), ni(), ni())
            };
            html! {
                <tr>
                    <th scope="row"><a href={format!("../../endpoints/#ep-{ep}")}>{format::endpoint_label(config, ep)}</a></th>
                    <td class="num">{rps}</td>
                    <td class="num">{vs}</td>
                    <td class="num">{eff}</td>
                    <td class="num">{p99}</td>
                    <td class="num">{err}</td>
                    <td>{format::bound(row, &base)}</td>
                </tr>
            }
        })
        .collect();
    Some(html! {
        <section class="section" aria-labelledby="endpoints">
            <h2 id="endpoints">"Tier 1 endpoints"</h2>
            {table_region("Tier 1 endpoints", html! {
                <table class="plain">
                    <caption>"Medians over every round (lowest and highest round in brackets); vs Axum: the median of the per-round ratios on the same runners."</caption>
                    <thead><tr>
                        <th scope="col">"Endpoint"</th><th scope="col" class="num">"req/s"</th><th scope="col" class="num">"vs Axum"</th>
                        <th scope="col" class="num">"Efficiency (req/CPU-s)"</th><th scope="col" class="num">"p99 (ms)"</th>
                        <th scope="col" class="num">"Errors"</th><th scope="col">"Limits"</th>
                    </tr></thead>
                    <tbody>{lines}</tbody>
                </table>
            })}
        </section>
    })
}
