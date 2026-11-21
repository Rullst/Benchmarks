//! Blocks several pages repeat: the run facts, the category navigation and the footnotes.

use rullst::html;
use rullst::html::Markup;

use crate::context::Ctx;
use crate::data::CategoryKey;
use crate::dates::Date;
use crate::format::DASH;
use crate::layout::rich;

const CATEGORY_NAV: [(&str, &str); 7] = [
    ("", "Overall"),
    ("hello/", "Hello world"),
    ("database/", "Database"),
    ("application/", "Application"),
    ("memory/", "Memory"),
    ("startup/", "Startup"),
    ("stability/", "Stability"),
];

/// The ranking pages, as pills under the page heading. `current` is the page's own path.
pub fn category_nav(root: &str, current: Option<&str>) -> Markup {
    let current = current.unwrap_or("");
    let items: Markup = CATEGORY_NAV
        .iter()
        .map(|&(target, text)| {
            let href = format!("{root}{target}");
            let here = (target == current).then_some("page");
            html! { <li><a href={href} aria-current?={here}>{text}</a></li> }
        })
        .collect();
    html! { <nav class="pills" aria-label="Rankings"><ul>{items}</ul></nav> }
}

pub fn category_path(key: CategoryKey) -> String {
    format!("{}/", key.slug())
}

/// When and how the results were measured, with the workflow run.
pub fn run_facts(ctx: &Ctx) -> Markup {
    let data = ctx.data();
    let from = Date::parse(&data.measured_from).map(Date::long).unwrap_or_else(|| DASH.to_string());
    let to = Date::parse(&data.measured_to).map(Date::long);
    let updated = Date::parse(&data.generated_at).map(|d| d.to_string()).unwrap_or_else(|| DASH.to_string());
    let when = match to {
        Some(to) if to != from => format!("{from} to {to}"),
        _ => from,
    };
    let source = match data.rullst_source.as_ref().map(|s| s.kind.as_str()) {
        Some("crates.io") => " from crates.io".to_string(),
        Some("git") => format!(
            " built from {}, a git revision, not the crates.io release",
            data.rullst_source.as_ref().map(|s| s.label.as_str()).unwrap_or("")
        ),
        _ => String::new(),
    };
    let run_text = format!("workflow run {}", data.run.id);
    let server = data.config.server.as_ref().map(|s| {
        let memory = s.memory.strip_suffix('g').map(|g| format!("{g} GiB")).unwrap_or_else(|| s.memory.clone());
        format!("{} vCPUs and {memory} per server", crate::format::num(Some(s.cpus), 0))
    });
    html! {
        <ul class="run-facts">
            <li><span class="fact-label">"Measured"</span>" "{when}</li>
            <li><span class="fact-label">"Rullst"</span>" "<span class="mono">{data.rullst_version.as_str()}</span>{source}</li>
            <li><span class="fact-label">"Source"</span>" "<a href={data.run.url.as_str()}>{run_text}</a></li>
            @if let Some(server) = server { <li><span class="fact-label">"Limits"</span>" "{server}</li> }
            <li><span class="fact-label">"Updated"</span>" "{updated}</li>
        </ul>
    }
}

/// The footnotes of the ‡ (PUT /world/{id}) and † (database setup) signs.
pub fn notes(ctx: &Ctx, put: bool, database: bool) -> Option<Markup> {
    let put_note = if put { ctx.put_note() } else { None };
    let database_notes: Vec<(String, String)> = if database {
        ctx.category(CategoryKey::Database)
            .entries
            .iter()
            .filter(|e| !e.database_note.is_empty())
            .map(|e| (ctx.name(&e.slug), e.database_note.clone()))
            .collect()
    } else {
        Vec::new()
    };
    let corrections: Vec<(String, &str)> = ctx
        .data()
        .results
        .iter()
        .filter(|r| !r.excluded.is_empty())
        .map(|r| (crate::format::label(r), r.problem.as_str()))
        .collect();
    if put_note.is_none() && database_notes.is_empty() && corrections.is_empty() {
        return None;
    }
    let correction_items: Markup = corrections
        .iter()
        .map(|(name, problem)| html! { <li><b>"Correction, "{name.as_str()}": "</b>{rich(problem)}" Left-out results are shown as –."</li> })
        .collect();
    let database_items: Markup = database_notes
        .iter()
        .map(|(name, note)| html! { <li><b>"† "</b>{name.as_str()}": "{rich(note)}</li> })
        .collect();
    Some(html! {
        <section class="section notes" aria-labelledby="notes">
            <h2 id="notes">"Notes"</h2>
            <ul class="footnotes">
                @if let Some(note) = put_note { <li class="footnote-put">{rich(note)}</li> }
                {database_items}
                {correction_items}
            </ul>
        </section>
    })
}
