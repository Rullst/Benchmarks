//! `/stability/`: the pass, warn or fail check of Tiers 2 and 4 (not a score).

use rullst::html;
use rullst::html::Markup;

use crate::context::Ctx;
use crate::data::{StabilityEntry, StabilityTier};
use crate::format::{self, DASH};
use crate::layout::{Page, Section, page_head, table_region};
use crate::pages::category::sentence;
use crate::pages::common::category_nav;

fn worst(tier: Option<&StabilityTier>) -> String {
    match tier.and_then(|t| t.error_rate_max) {
        None => DASH.to_string(),
        Some(0.0) => "0".to_string(),
        Some(rate) => format!("{:.2}%", rate * 100.0),
    }
}

fn row(ctx: &Ctx, root: &str, entry: &StabilityEntry) -> Markup {
    let t2 = entry.detail.tier2.as_ref();
    let t4 = entry.detail.tier4.as_ref();
    let result = entry.result.map(|r| r.text()).unwrap_or(DASH);
    let badge = format!("badge badge-{result}");
    let runners = ctx.row(&entry.slug).map(format::runners).unwrap_or_default();
    let href = format!("{root}implementations/{}/", entry.slug);
    let role = ctx.row(&entry.slug).and_then(format::role_text);
    html! {
        <tr class={if ctx.is_rullst(&entry.slug) { "is-rullst" } else { "" }}>
            <th scope="row"><a href={href}>{ctx.name(&entry.slug)}</a>
                @if let Some(role) = role { <span class="role">{role}</span> }</th>
            <td><span class={badge}>{result}</span></td>
            <td class="num">{format::num(t2.and_then(|t| t.rps), 0)}</td>
            <td class="num">{format::num(t2.and_then(|t| t.p99_ms), 1)}</td>
            <td class="num">{worst(t2)}</td>
            <td class="num">{format::num(t4.and_then(|t| t.rps), 0)}</td>
            <td class="num">{format::num(t4.and_then(|t| t.p99_ms), 1)}</td>
            <td class="num">{worst(t4)}</td>
            <td class="num">{format::num(t4.and_then(|t| t.timeouts), 0)}</td>
            <td>{if entry.reasons.is_empty() { DASH.to_string() } else { entry.reasons.join("; ") }}</td>
            <td>{runners}</td>
        </tr>
    }
}

pub fn page(ctx: &Ctx) -> Option<Page> {
    let stability = ctx.data().rankings.stability.as_ref()?;
    let root = "../";
    let (main, apart): (Vec<&StabilityEntry>, Vec<&StabilityEntry>) =
        stability.entries.iter().partition(|e| !e.status.is_unranked_role());
    let main_rows: Markup = main.iter().map(|e| row(ctx, root, e)).collect();
    let apart_rows: Markup = apart.iter().map(|e| row(ctx, root, e)).collect();
    let table = html! {
        <table class="plain">
            <caption>"Result per implementation, with the Tier 2 and Tier 4 numbers it comes from (medians over "
                "rounds; worst errors: the highest error rate of a round)."</caption>
            <thead>
                <tr>
                    <th scope="col">"Implementation"</th>
                    <th scope="col">"Result"</th>
                    <th scope="col">"Tier 2 req/s"</th>
                    <th scope="col">"Tier 2 p99 (ms)"</th>
                    <th scope="col">"Tier 2 worst errors"</th>
                    <th scope="col">"Tier 4 req/s"</th>
                    <th scope="col">"Tier 4 p99 (ms)"</th>
                    <th scope="col">"Tier 4 worst errors"</th>
                    <th scope="col">"Tier 4 timeouts"</th>
                    <th scope="col">"Notes"</th>
                    <th scope="col">"Runner CPUs"</th>
                </tr>
            </thead>
            <tbody>{main_rows}</tbody>
            @if !apart.is_empty() {
                <tbody class="group-apart">
                    <tr class="row-divider"><th scope="rowgroup" colspan="11">"Diagnostics and the A/A control"</th></tr>
                    {apart_rows}
                </tbody>
            }
        </table>
    };
    let lede = html! {
        <p>{sentence(&stability.description)}</p>
        <p class="muted">"Stability has no score and no position; an implementation that fails it has no overall position."</p>
    };
    let eyebrow = if stability.tier.is_empty() { "Check".to_string() } else { format!("Check · {}", stability.tier) };
    let body = html! {
        {page_head(&eyebrow, &stability.title, lede)}
        {category_nav(root, Some("stability/"))}
        <section class="section" aria-labelledby="results">
            <h2 id="results">"Results"</h2>
            {table_region("Stability results", table)}
            <p class="section-lede">"Full Tier 2 and Tier 4 tables (efficiency, latency, RAM growth): "
               <a href={format!("{root}endpoints/#tier2")}>"Tier 2"</a>", "
               <a href={format!("{root}endpoints/#tier4")}>"Tier 4"</a>"."</p>
        </section>
    };
    Some(Page {
        path: "stability/".to_string(),
        title: stability.title.clone(),
        description: "Stability check of the Rullst Benchmarks: pass, warn or fail under Tiers 2 and 4.".to_string(),
        section: Section::Rankings,
        results: true,
        body,
    })
}
