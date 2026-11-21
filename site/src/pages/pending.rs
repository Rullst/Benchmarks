//! The page every URL shows when the results cannot be used: no numbers, the reason, and where to look.

use rullst::html;

use crate::layout::{Page, REPO, Section, page_head, readme};

/// The fixed pages; the per-implementation pages exist only with valid results.
pub const PATHS: [(&str, Section); 12] = [
    ("", Section::Rankings),
    ("hello/", Section::Rankings),
    ("database/", Section::Rankings),
    ("application/", Section::Rankings),
    ("memory/", Section::Rankings),
    ("startup/", Section::Rankings),
    ("stability/", Section::Rankings),
    ("endpoints/", Section::Endpoints),
    ("diagnostics/", Section::Diagnostics),
    ("implementations/", Section::Implementations),
    ("history/", Section::History),
    ("method/", Section::Method),
];

pub fn pages(reason: &str) -> Vec<Page> {
    PATHS
        .iter()
        .map(|&(path, section)| {
            let lede = html! {
                <p>"The published results could not be used, so these pages show no numbers rather than older or "
                   "partial ones. They come back with the next set of results that passes the checks."</p>
            };
            let body = html! {
                {page_head("Rullst Benchmarks", "Results pending", lede)}
                <section class="section pending" aria-labelledby="why">
                    <h2 id="why">"Why"</h2>
                    <p class="callout callout-warn"><code>{reason}</code></p>
                    <p>"The method and the measured implementations are described in the "
                       <a href={readme("method")}>"README"</a>"; the results files are in "
                       <a href={format!("{REPO}/tree/main/results")}>"results/"</a>" with their dates."</p>
                </section>
            };
            Page {
                path: path.to_string(),
                title: "Results pending".to_string(),
                description: "The Rullst Benchmarks results are pending.".to_string(),
                section,
                results: false,
                body,
            }
        })
        .collect()
}
