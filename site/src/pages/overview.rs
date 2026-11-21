//! The overview (`/`): the run, how to read the scores, the overall ranking with the category positions,
//! the sensitivity table, the reading for Rullst and a card per category.

use rullst::html;
use rullst::html::Markup;

use crate::charts;
use crate::components::{Column, flag_legend, place_and_score, ranking_table};
use crate::context::Ctx;
use crate::data::{CategoryKey, EntryStatus};
use crate::format::{self, DASH, times};
use crate::layout::{DISCLOSURE, Page, Section, readme, rich};
use crate::pages::common::{category_nav, notes, run_facts};

pub fn page(ctx: &Ctx) -> Page {
    let root = "./";
    let body = html! {
        {hero(ctx)}
        {category_nav(root, None)}
        {how_to_read()}
        {overall(ctx, root)}
        {sensitivity(ctx)}
        {reading(ctx)}
        {cards(ctx, root)}
        {notes(ctx, true, true)}
    };
    Page {
        path: String::new(),
        title: "Rullst Benchmarks".to_string(),
        description:
            "HTTP benchmarks of Rullst and other web frameworks, measured against Axum on GitHub-hosted runners."
                .to_string(),
        section: Section::Rankings,
        results: true,
        body,
    }
}

fn hero(ctx: &Ctx) -> Markup {
    let data = ctx.data();
    let endpoints = data.config.tiers.tier1.endpoints.len();
    let jobs = data.run.jobs.map(|j| j.to_string()).unwrap_or_else(|| DASH.to_string());
    let rounds = data.run.rounds.map(|r| r.to_string()).unwrap_or_else(|| DASH.to_string());
    let reference = ctx.row(&data.baseline);
    let reference_name = reference.map(|r| r.name.clone()).unwrap_or_default();
    let reference_version = reference.map(|r| r.framework_version.clone()).unwrap_or_default();
    // Frameworks, not rows: a framework with two ranked variants counts once.
    let mut frameworks: Vec<&str> = data
        .results
        .iter()
        .filter(|r| !r.is_baseline && r.role == crate::data::Role::Ranked)
        .map(|r| r.name.as_str())
        .collect();
    frameworks.sort_unstable();
    frameworks.dedup();
    let title = format!("{} web frameworks, scored against {} on the same runners", frameworks.len(), reference_name);
    let gate_problems = data.publication_gate.as_ref().filter(|g| !g.passed).map(|g| g.problems.len());
    html! {
        <section class="hero" aria-labelledby="hero-title">
            <div class="hero-grid">
                <div class="hero-main">
                    <p class="eyebrow"><span class="eyebrow-line"></span>"Cross-framework HTTP benchmark"</p>
                    <h1 id="hero-title">{title}</h1>
                    <p class="hero-lede">
                        "Every number on these pages comes from a GitHub Actions workflow that anyone can rerun: "
                        {endpoints}" endpoints, from a plain-text response to a signed-in session, under four load "
                        "tiers, with every response checked for conformance first. Each score divides an "
                        "implementation's result by Axum's, measured on the same machine in alternating rounds."
                    </p>
                    {run_facts(ctx)}
                </div>
                {glance(ctx)}
            </div>
            <dl class="stats">
                <div class="stat"><dt>"Ranked implementations"</dt><dd>{ctx.ranked}</dd></div>
                <div class="stat"><dt>"Endpoints"</dt><dd>{endpoints}</dd></div>
                <div class="stat"><dt>"Runner jobs"</dt><dd>{jobs}</dd></div>
                <div class="stat"><dt>"Rounds per job"</dt><dd>{rounds}</dd></div>
                <div class="stat"><dt>"Reference (1.00×)"</dt><dd>{reference_name}" "<span class="stat-sub">{reference_version}</span></dd></div>
            </dl>
            <p class="disclosure">
                <strong>"Disclosure. "</strong>{DISCLOSURE}" The pages print every implementation's numbers from the "
                "same results files. "<a href={readme("authorship")}>"Authorship"</a>
            </p>
            @if !data.note.is_empty() { <p class="callout"><strong>"Note: "</strong>{rich(&data.note)}</p> }
            @if let Some(problems) = gate_problems {
                <p class="callout callout-warn"><strong>"Publication gate: "</strong>"an automatic run would not "
                   "publish these results ("{problems}" problems, listed on the "<a href="method/#gate">"Method page"</a>
                   "). The notes under the tables say which numbers they affect."</p>
            }
        </section>
    }
}

/// The overall ranking at a glance, next to the title: every ranked score with its position range.
fn glance(ctx: &Ctx) -> Option<Markup> {
    let rankings = &ctx.data().rankings;
    let overall = rankings.overall.as_ref().filter(|_| rankings.publish_overall)?;
    let parts = crate::context::split(&overall.entries);
    let scale = charts::Scale::new(overall.entries.iter().filter_map(|e| e.score));
    let put = ctx.put_note().is_some();
    let items: Markup = parts
        .groups
        .iter()
        .map(|group| {
            let rows: Markup = group
                .iter()
                .enumerate()
                .map(|(i, entry)| {
                    let name = ctx.name(&entry.slug);
                    let value = format::times_or_dash(entry.score);
                    let flags = crate::components::flags(ctx, None, entry);
                    let place = if i == 0 { format::position_text(entry) } else { String::new() };
                    let class = if ctx.is_rullst(&entry.slug) { "glance-row is-rullst" } else { "glance-row" };
                    html! {
                        <li class={class}>
                            <span class="glance-pos">{place}</span>
                            <span class="glance-name">{name.as_str()}</span>
                            {charts::bar(entry.score, &scale, charts::Tone::Ranked, &name)}
                            <span class="glance-value">{value}{flags}</span>
                        </li>
                    }
                })
                .collect();
            let class = if group.len() > 1 { "glance-group glance-tie" } else { "glance-group" };
            html! { <li class={class}><ol class="glance-members">{rows}</ol></li> }
        })
        .collect();
    Some(html! {
        <aside class="glance" aria-labelledby="glance-title">
            <h2 id="glance-title" class="glance-title">"Overall score"<span>"Axum = 1.00×, higher is better"</span></h2>
            <ol class="glance-list">{items}</ol>
            <p class="glance-note">"A bracket marks a tie: those positions in no particular order. "
               @if put { "‡: includes a PUT /world/{id} run that did not write in most measured requests ("<a href="#notes">"Notes"</a>"). " }
               <a href="#overall">"Full ranking"</a></p>
        </aside>
    })
}

fn how_to_read() -> Markup {
    html! {
        <section class="section" aria-labelledby="how-to-read">
            <h2 id="how-to-read">"How to read these results"</h2>
            <div class="howto">
                <article class="howto-card">
                    <h3>"1.00× is Axum"</h3>
                    <p>"Every score divides a framework's result by Axum's, a small Rust framework used as the "
                       "reference and measured on the same machine in alternating rounds. 0.50× is half of Axum's "
                       "result and 2.00× twice. Higher is better in every score: for memory and start-up time the "
                       "ratio is turned around, so a higher score means less RAM or a faster start."</p>
                </article>
                <article class="howto-card">
                    <h3>"Ties and ±"</h3>
                    <p>"The runners are shared cloud machines with different CPU models, so results vary from run to "
                       "run. \"±6%\" next to a score is the margin within which it cannot be told apart from the score "
                       "above it. Scores that close share a range of positions, such as \"3–7\": positions 3 to 7 in no "
                       "particular order."</p>
                </article>
                <article class="howto-card">
                    <h3>"The categories answer different questions"</h3>
                    <p><em>"Hello world"</em>": what a framework costs per request when the page is trivial. "
                       <em>"Database"</em>": how it reads, writes and renders rows. "<em>"Application"</em>": what it "
                       "does with a real request (input, validation, a write, a form with CSRF protection, a signed-in "
                       "user). "<em>"Memory"</em>": how much RAM it needs under load. "<em>"Startup"</em>": how fast it "
                       "starts. "<em>"Stability"</em>" (pass or fail): whether it keeps working under heavier load."</p>
                </article>
                <article class="howto-card">
                    <h3>"The database usually comes first"</h3>
                    <p>"In a real application the database is usually the limit before the framework is, so a large "
                       "gap in Hello world shrinks or disappears once requests read and write data. When a run was "
                       "limited by the database or the load generator rather than the server (\"*\"), the score "
                       "compares CPU cost per request instead of requests per second."</p>
                </article>
                <article class="howto-card">
                    <h3>"The overall score is a summary"</h3>
                    <p>"It combines the five category scores, with Hello world, Database and Application counted "
                       "twice and Memory and Startup once. The categories are the result: other weights change the "
                       "order, as the table under the overall ranking shows."</p>
                </article>
                <article class="howto-card">
                    <h3>"Rullst is measured twice"</h3>
                    <p><em>"Rullst (as generated)"</em>" is the application "<code>"cargo rullst new"</code>" and "
                       <code>"cargo rullst deploy"</code>" create, with the production middleware they turn on (WAF, "
                       "CSRF protection, secure cookies, security headers); it is the ranked Rullst. "
                       <em>"Rullst (minimal)"</em>" serves Rullst's router, ORM and "<code>"html!"</code>" through "
                       "Axum's own server, without that middleware: an unranked diagnostic. The gap between the two "
                       "shows what the default stack costs."</p>
                </article>
            </div>
        </section>
    }
}

fn weights_text(ctx: &Ctx) -> String {
    let rankings = &ctx.data().rankings;
    let Some(overall) = &rankings.overall else { return String::new() };
    rankings
        .categories
        .iter()
        .filter_map(|c| overall.weight_ratio.get(c.key.slug()).map(|w| format!("{} ×{w}", c.title)))
        .collect::<Vec<_>>()
        .join(", ")
}

fn overall(ctx: &Ctx, root: &str) -> Markup {
    let rankings = &ctx.data().rankings;
    let Some(overall) = rankings.overall.as_ref().filter(|_| rankings.publish_overall) else {
        return html! {
            <section class="section" aria-labelledby="overall">
                <h2 id="overall">"Overall"</h2>
                <p class="callout">"This run publishes no overall score; the categories are the result."</p>
            </section>
        };
    };
    let mut columns: Vec<Column> = CategoryKey::ALL
        .iter()
        .map(|&key| {
            let title = ctx.category(key).title.clone();
            Column::new(title, move |e| place_and_score(ctx, key, ctx.entry(key, &e.slug)))
        })
        .collect();
    columns.push(Column::text("Stability", |e| e.stability.clone().unwrap_or_else(|| DASH.to_string())));
    let caption = html! {
        "Overall: the weighted geometric mean of the five category scores ("{weights_text(ctx)}"), with the "
        "same tie margins and position ranges as the categories. Category columns: position and score."
    };
    let unranked = crate::components::unranked_table(
        ctx,
        root,
        "Overall scores of the diagnostics and the A/A control",
        html! { "Not ranked: the diagnostics and the A/A control, with their overall scores." },
        None,
        &overall.entries,
        &[],
    );
    html! {
        <section class="section" aria-labelledby="overall">
            <h2 id="overall">"Overall ranking"</h2>
            <p class="section-lede">"A summary for quick reading: the categories are the result, and other "
               "weightings change the order (the next table). An implementation that fails Stability has no overall "
               "position."</p>
            {flag_legend(ctx.put_note().is_some(), true, true)}
            {ranking_table(ctx, root, "Overall ranking", caption, None, &overall.entries, &columns)}
            <details class="unranked-details">
                <summary>"Diagnostics and the A/A control (not ranked)"</summary>
                {unranked}
                <p><a href={format!("{root}diagnostics/")}>"What each diagnostic measures"</a></p>
            </details>
        </section>
    }
}

fn sensitivity(ctx: &Ctx) -> Option<Markup> {
    let rankings = &ctx.data().rankings;
    if !rankings.publish_overall || rankings.sensitivity.is_empty() {
        return None;
    }
    let overall = rankings.overall.as_ref()?;
    let headers: Markup = rankings
        .sensitivity
        .iter()
        .map(|w| {
            let weights: Vec<String> = rankings
                .categories
                .iter()
                .filter_map(|c| w.weights.get(c.key.slug()).map(|v| format!("{} ×{v}", c.title)))
                .collect();
            let weights = weights.join(", ");
            html! { <th scope="col"><span class="th-main">{w.title.as_str()}</span><span class="th-sub">{weights}</span></th> }
        })
        .collect();
    let rows: Markup = overall
        .entries
        .iter()
        .filter(|e| matches!(e.status, EntryStatus::Ranked | EntryStatus::Unstable))
        .map(|entry| {
            let cells: Markup = rankings
                .sensitivity
                .iter()
                .map(|w| {
                    let item = w.entries.iter().find(|i| i.slug == entry.slug);
                    let text = match item {
                        Some(i) if i.score.is_some() => {
                            format!("{} · {}", format::position_text(i), times(i.score.unwrap_or(0.0)))
                        }
                        _ => DASH.to_string(),
                    };
                    html! { <td class="num">{text}</td> }
                })
                .collect();
            let base = format!("{} · {}", format::position_text(entry), format::times_or_dash(entry.score));
            let class = if ctx.is_rullst(&entry.slug) { "is-rullst" } else { "" };
            html! {
                <tr class={class}>
                    <th scope="row">{ctx.name(&entry.slug)}</th>
                    <td class="num">{base}</td>
                    {cells}
                </tr>
            }
        })
        .collect();
    let table = html! {
        <table class="plain">
            <caption>"Positions and scores under other weightings: how much the overall order depends on the weights."</caption>
            <thead><tr><th scope="col">"Implementation"</th><th scope="col"><span class="th-main">"Published (2:2:2:1:1)"</span></th>{headers}</tr></thead>
            <tbody>{rows}</tbody>
        </table>
    };
    Some(html! {
        <section class="section" aria-labelledby="sensitivity">
            <h2 id="sensitivity">"Other weightings"</h2>
            {crate::layout::table_region("Positions under other weightings", table)}
        </section>
    })
}

fn reading(ctx: &Ctx) -> Markup {
    let reading = &ctx.results.site.reading;
    html! {
        <section class="section reading" aria-labelledby="rullst-reading">
            <h2 id="rullst-reading">"What this means for Rullst"</h2>
            <p class="reading-text">{rich(&reading.en)}</p>
            <p class="reading-source">"Written from the data by "<code>"bench/reading.py"</code>"; the same "
               "sentences whichever way the numbers point. "<a href={readme("authorship")}>"Authorship"</a></p>
            <details class="reading-pt" lang="pt-BR">
                <summary>"O que isto significa para o Rullst (em português)"</summary>
                <p class="reading-text">{rich(&reading.pt_br)}</p>
            </details>
        </section>
    }
}

const QUESTIONS: [(CategoryKey, &str); 5] = [
    (CategoryKey::Hello, "What a framework costs per request when the page is trivial."),
    (CategoryKey::Database, "How it reads, writes and renders rows."),
    (CategoryKey::Application, "What it does with a real request: input, validation, a write, CSRF, a session."),
    (CategoryKey::Memory, "How much RAM it needs under load."),
    (CategoryKey::Startup, "How fast it starts."),
];

fn cards(ctx: &Ctx, root: &str) -> Markup {
    let cards: Markup = QUESTIONS
        .iter()
        .map(|&(key, question)| {
            let category = ctx.category(key);
            let mut ranked: Vec<_> =
                category.entries.iter().filter(|e| e.status == EntryStatus::Ranked && e.score.is_some()).collect();
            ranked.sort_by(|a, b| b.score.partial_cmp(&a.score).unwrap_or(std::cmp::Ordering::Equal));
            let scores: Vec<(f64, bool)> =
                ranked.iter().map(|e| (e.score.unwrap_or(0.0), e.slug == "rullst")).collect();
            let label = format!(
                "{}: the scores of the {} ranked implementations, highest first; the line marks Axum (1.00×)",
                category.title,
                scores.len()
            );
            let leaders: Vec<_> = ranked.iter().filter(|e| e.position == Some(1)).collect();
            let first = match leaders.as_slice() {
                [one] => format!("{} ({}×)", ctx.name(&one.slug), format::times_or_dash(one.score)),
                [a, b] => format!("{}, {} (tie)", ctx.name(&a.slug), ctx.name(&b.slug)),
                many => format!(
                    "{} implementations tied ({})",
                    many.len(),
                    many.first().and_then(|e| format::position_words(e)).unwrap_or_default()
                ),
            };
            let rullst = ctx.entry(key, "rullst").map(|e| match (format::position_words(e), e.score) {
                (Some(place), Some(score)) => format!("{place} ({}×)", times(score)),
                _ => e.status.text().to_string(),
            });
            let href = format!("{root}{}/", key.slug());
            html! {
                <article class="card">
                    <h3><a href={href}>{category.title.as_str()}</a></h3>
                    <p class="card-question">{question}</p>
                    {charts::columns(&scores, &label)}
                    <dl class="card-facts">
                        <div><dt>"Position 1"</dt><dd>{first}</dd></div>
                        @if let Some(rullst) = rullst { <div><dt>"Rullst (as generated)"</dt><dd>{rullst}</dd></div> }
                    </dl>
                </article>
            }
        })
        .collect();
    let stability = ctx.data().rankings.stability.as_ref().map(|s| {
        let count = |result| s.entries.iter().filter(|e| e.status == EntryStatus::Ranked && e.result == Some(result)).count();
        let pass = count(crate::data::StabilityResult::Pass);
        let warn = count(crate::data::StabilityResult::Warn);
        let fail = count(crate::data::StabilityResult::Fail);
        let href = format!("{root}stability/");
        html! {
            <article class="card">
                <h3><a href={href}>{s.title.as_str()}</a></h3>
                <p class="card-question">"Whether it keeps working under heavier load (pass, warn or fail; not a score). Ranked implementations:"</p>
                <dl class="card-facts card-stability">
                    <div><dt>"pass"</dt><dd>{pass}</dd></div>
                    <div><dt>"warn"</dt><dd>{warn}</dd></div>
                    <div><dt>"fail"</dt><dd>{fail}</dd></div>
                </dl>
            </article>
        }
    });
    html! {
        <section class="section" aria-labelledby="categories">
            <h2 id="categories">"The categories"</h2>
            <p class="section-lede">"Each card shows every ranked score of its category, highest first; the "
               "highlighted column is Rullst as generated. Each page has the full ranking, the per-endpoint ratios "
               "and how each position was decided."</p>
            <div class="cards">{cards}{stability}</div>
        </section>
    }
}
