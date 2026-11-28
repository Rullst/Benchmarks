//! `/history/`: the Rullst variants across measured Rullst versions (versions.json), with the load
//! generator of each run, since numbers from different load generators are not comparable.

use rullst::html;
use rullst::html::Markup;

use crate::charts::{self, Scale, Tone};
use crate::context::Ctx;
use crate::data::{RowStatus, VersionEntry};
use crate::dates::Date;
use crate::format::{self, DASH};
use crate::layout::{Page, Section, page_head, readme, rich, table_region};

const VARIANTS: [(&str, &str); 2] = [("rullst", "as generated"), ("rullst-minimal", "minimal")];
const THROUGHPUT: [(&str, &str); 3] =
    [("tier1.json.rps", "/json req/s"), ("tier1.db-single.rps", "/db-single req/s"), ("tier1.html.rps", "/html req/s")];
const COSTS: [(&str, &str); 2] = [("tier2.latency_ms.p99", "Tier 2 p99"), ("tier3.load_ram_peak_mib", "Peak RAM")];

/// What limits a comparison of two published runs, shown when both versions are in versions.json.
/// It is the generator's text: the stored results are never edited.
fn comparisons() -> [(&'static str, &'static str, Markup); 1] {
    [(
        "13.0.0-alpha.6",
        "13.0.0-rc.1",
        html! {
            "Rullst 13.0.0-rc.1 pings a pooled PostgreSQL connection before handing it out only when it has been "
            "idle for at least 500 ms; 13.0.0-alpha.6 pinged on every acquisition, SQLx's default. That change likely "
            "accounts for most of the Database change (0.79× to 1.03×): on EPYC 9V74, the one runner CPU both runs "
            "used, the ratio to Axum of requests per CPU-second of the server and PostgreSQL went from 0.84 to 1.01 "
            "for /db-single, 0.88 to 1.08 for /queries and 0.72 to 0.89 for /fortunes, while /text stayed at 0.55 "
            "and 0.56. No run measured 13.0.0-rc.1 with the ping on, and the runners changed (13.0.0-alpha.6: two "
            "EPYC 7763 jobs and one EPYC 9V74; 13.0.0-rc.1: two EPYC 9V45 and one EPYC 9V74, where Rullst's ratios "
            "on EPYC 9V45 were 0.08 to 0.13 higher than on EPYC 9V74), so part of the Database change, and the "
            "Hello world change (0.50× to 0.64×), comes from the runners. Application is not comparable between "
            "the two runs: the 13.0.0-alpha.6 run used the harness before "
            <a href="https://github.com/Rullst/Benchmarks/commit/c24153c">"c24153c"</a>
            ", whose PUT /world/{id} mostly sent the value already stored, so Rullst's "<code>"RowSnapshot"</code>
            " save mostly wrote nothing (PUT /world/{id}: 1.16× Axum in 13.0.0-alpha.6, 0.56× in 13.0.0-rc.1)."
        },
    )]
}

pub fn page(ctx: &Ctx) -> Page {
    let root = "../";
    let versions = &ctx.results.versions.versions;
    let generators = &ctx.results.load_generators;
    let mut values = Vec::new();
    for entry in versions {
        for (slug, _) in VARIANTS {
            if let Some(imp) = entry.implementations.get(slug) {
                values.extend(THROUGHPUT.iter().filter_map(|(k, _)| imp.ratios.get(*k).copied().flatten()));
            }
        }
    }
    let scale = Scale::new(values);
    let headers: Markup = THROUGHPUT
        .iter()
        .map(|(_, title)| html! { <th scope="col" class="score-head">{*title}{charts::axis(&scale)}</th> })
        .chain(COSTS.iter().map(|(_, title)| html! { <th scope="col" class="num">{*title}</th> }))
        .collect();
    let rows: Markup = versions
        .iter()
        .zip(generators)
        .rev()
        .map(|(entry, generator)| version_rows(root, entry, generator, &scale))
        .collect();
    let notes: Markup = versions
        .iter()
        .rev()
        .filter(|v| !v.note.is_empty())
        .map(|v| html! { <li><b>{v.version.as_str()}": "</b>{rich(&v.note)}</li> })
        .collect();
    let any_notes = versions.iter().any(|v| !v.note.is_empty());
    let measured = |version: &str| versions.iter().any(|v| v.version == version);
    let comparisons: Vec<Markup> = comparisons()
        .into_iter()
        .filter(|(from, to, _)| measured(from) && measured(to))
        .map(|(from, to, text)| html! { <li><b>{from}" and "{to}": "</b>{text}</li> })
        .collect();
    let any_comparison = !comparisons.is_empty();
    let comparisons: Markup = comparisons.into_iter().collect();
    let table = html! {
        <table class="ranking history">
            <caption>"Ratios to Axum measured on the same runners (1.00 = Axum). Requests/s: higher is better. "
                "Tier 2 p99 latency and peak RAM: above 1.00 means more latency or more RAM than Axum."</caption>
            <thead><tr>
                <th scope="col">"Rullst version"</th>
                <th scope="col">"Measured"</th>
                <th scope="col">"Load generator"</th>
                <th scope="col">"Variant"</th>
                {headers}
            </tr></thead>
            {rows}
        </table>
    };
    let lede = html! {
        <p>"Every Rullst release on crates.io is measured once, with the newest harness; each version keeps its "
           "own results file. Rows from runs with different load generators or scoring rules are not comparable "
           "in absolute numbers or positions; the ratios to Axum are always measured with the same tool in the same "
           "job. "<a href={readme("history")}>"History of the method"</a></p>
    };
    let body = html! {
        {page_head("Across versions", "Rullst across measured versions", lede)}
        <section class="section" aria-labelledby="versions">
            <h2 id="versions">"Ratios to Axum per version"</h2>
            {table_region("Rullst across versions", table)}
        </section>
        @if any_comparison {
            <section class="section" aria-labelledby="comparing">
                <h2 id="comparing">"Comparing two runs"</h2>
                <ul class="footnotes">{comparisons}</ul>
            </section>
        }
        @if any_notes {
            <section class="section" aria-labelledby="version-notes">
                <h2 id="version-notes">"Version notes"</h2>
                <ul class="footnotes">{notes}</ul>
            </section>
        }
        <section class="section" aria-labelledby="before">
            <h2 id="before">"Before the rebuild"</h2>
            <p>"The results measured by hand on a laptop on 22 June 2026 are kept for the record in "
               <a href="https://github.com/Rullst/Benchmarks/blob/main/history/2026-06-22-laptop.md">"history/2026-06-22-laptop.md"</a>
               "; they used different hardware and code and are not comparable."</p>
        </section>
    };
    Page {
        path: "history/".to_string(),
        title: "History".to_string(),
        description: "Rullst's ratios to Axum across measured Rullst versions.".to_string(),
        section: Section::History,
        results: true,
        body,
    }
}

fn version_rows(root: &str, entry: &VersionEntry, generator: &str, scale: &Scale) -> Markup {
    let measured = Date::parse(&entry.measured_from).map(|d| d.to_string()).unwrap_or(DASH.to_string());
    let file = format!("{root}data/{}", entry.file);
    let span = VARIANTS.len();
    let lines: Markup = VARIANTS
        .iter()
        .enumerate()
        .map(|(i, (slug, variant))| {
            let imp = entry.implementations.get(*slug);
            let measured_ok = imp.is_some_and(|i| matches!(i.status, RowStatus::Measured | RowStatus::Crashed));
            let tone = if *slug == "rullst" { Tone::Ranked } else { Tone::Unranked };
            let bars: Markup = THROUGHPUT
                .iter()
                .map(|(key, title)| {
                    let value = imp.filter(|_| measured_ok).and_then(|i| i.ratios.get(*key).copied().flatten());
                    let text = value.map(|v| format!("{v:.2}")).unwrap_or(DASH.to_string());
                    let name = format!("Rullst {} ({variant}), {title}", entry.version);
                    html! { <td class="score-cell"><span class="score-value">{text}</span>{charts::bar(value, scale, tone, &name)}</td> }
                })
                .collect();
            let costs: Markup = COSTS
                .iter()
                .map(|(key, _)| {
                    let value = imp.filter(|_| measured_ok).and_then(|i| i.ratios.get(*key).copied().flatten());
                    html! { <td class="num">{format::num(value, 2)}</td> }
                })
                .collect();
            let status = match imp {
                None => Some("not in this run".to_string()),
                Some(_) if !measured_ok => Some("not measured".to_string()),
                _ => None,
            };
            html! {
                <tr>
                    @if i == 0 {
                        <th scope="rowgroup" rowspan={span}><a href={file.as_str()}>{entry.version.as_str()}</a></th>
                        <td rowspan={span} class="nowrap">{measured.as_str()}</td>
                        <td rowspan={span}>{generator}</td>
                    }
                    <td class="nowrap">{*variant}@if let Some(status) = status { " "<span class="muted">"("{status}")"</span> }</td>
                    {bars}
                    {costs}
                </tr>
            }
        })
        .collect();
    html! { <tbody class="group">{lines}</tbody> }
}
