//! `/method/`: what is measured and how the scores are computed (from the data), the environment, the
//! publication gate, and short summaries of the README's method, fairness and limitations sections.

use rullst::html;
use rullst::html::Markup;

use crate::context::Ctx;
use crate::format::{self, DASH, short_cpu};
use crate::layout::{Page, Section, page_head, readme, rich, table_region};

pub fn page(ctx: &Ctx) -> Page {
    let data = ctx.data();
    let config = &data.config;
    let tiers = &config.tiers;
    let env = &data.environment;
    let endpoints: Markup = tiers
        .tier1
        .endpoints
        .iter()
        .map(|ep| html! { <li><code>{format::endpoint_label(config, ep)}</code></li> })
        .collect();
    let rules: Markup = data
        .rankings
        .method
        .iter()
        .map(|(name, text)| {
            let mut title: String = name.chars().take(1).flat_map(char::to_uppercase).collect();
            title.extend(name.chars().skip(1));
            html! { <div><dt>{title}</dt><dd>{rich(text)}</dd></div> }
        })
        .collect();
    let runners: Markup =
        data.runners.iter().map(|r| html! { <li>{short_cpu(&r.cpu_model)}" ×"{r.jobs}</li> }).collect();
    let server = config.server.as_ref();
    let cpus = server.map(|s| format::num(Some(s.cpus), 0)).unwrap_or(DASH.to_string());
    // Docker's "2g" reads as "2 GiB", as on the front page.
    let memory = server
        .map(|s| s.memory.strip_suffix('g').map(|g| format!("{g} GiB")).unwrap_or_else(|| s.memory.clone()))
        .unwrap_or_default();
    let pool = server.and_then(|s| s.pool_size).map(|p| p.to_string()).unwrap_or(DASH.to_string());
    let generator = env
        .load_generator
        .as_ref()
        .map(|lg| format!("{} {} ({})", lg.name, lg.version, lg.build))
        .unwrap_or(DASH.to_string());
    let warmup = config.warmup.as_ref();
    let warm = format!(
        "{} s per endpoint, {} s for runtimes with a JIT compiler",
        format::num(warmup.and_then(|w| w.duration_s), 0),
        format::num(warmup.and_then(|w| w.jit_duration_s), 0)
    );
    let database = config.database.as_ref();
    let postgres = format!(
        "PostgreSQL {} on the same machine; {} rows in world; max {} connections",
        env.postgres,
        format::num(database.and_then(|d| d.rows).map(f64::from), 0),
        format::num(database.and_then(|d| d.max_connections).map(f64::from), 0)
    );
    let threads = match &data.server_cores {
        Some(c) if c.jobs > 0 && c.jobs == c.smt_threads_of_one_core => {
            "; the server's two vCPUs were the two SMT threads of one physical core on every runner".to_string()
        }
        Some(c) if c.jobs > 0 => format!(
            "; the server's two vCPUs were the two SMT threads of one physical core on {} of {} runners",
            c.smt_threads_of_one_core, c.jobs
        ),
        _ => String::new(),
    };
    let machine = format!(
        "GitHub-hosted, {} vCPUs and {} GiB of RAM each; client, server and PostgreSQL share the machine{threads}",
        env.cpu_count.map(|c| c.to_string()).unwrap_or(DASH.to_string()),
        format::num(env.memory_total_mib.map(|m| m / 1024.0), 0)
    );
    let image = database.map(|d| d.image.clone()).unwrap_or_default();
    let tier = |name: &str, t: &crate::data::LoadTier| {
        format!(
            "{name}: /{} with {} connections for {} s",
            t.endpoint,
            t.connections,
            format::num(Some(t.duration_s), 0)
        )
    };
    let lede = html! {
        <p>"A summary of the method, generated from the configuration and rules the results carry. The README "
           "has the full method, the reasons behind each rule and its history."</p>
    };
    let body = html! {
        {page_head("Method", "How it is measured", lede)}
        <section class="section" aria-labelledby="measured">
            <h2 id="measured">"What is measured"</h2>
            <dl class="facts">
                <div><dt>"Tier 1 endpoints"</dt><dd><ul class="chips">{endpoints}</ul>
                    {format!("{} connections for {} s each", tiers.tier1.connections, format::num(Some(tiers.tier1.duration_s), 0))}</dd></div>
                <div><dt>"Load tiers"</dt><dd>{tier("Tier 2", &tiers.tier2)}"; "{tier("Tier 3", &tiers.tier3)}"; "{tier("Tier 4", &tiers.tier4)}</dd></div>
                <div><dt>"Server limits"</dt><dd>{format!("{cpus} vCPUs and {memory} of RAM per server; database pool of {pool} connections")}</dd></div>
                <div><dt>"Warm-up"</dt><dd>{warm}</dd></div>
                <div><dt>"Database"</dt><dd>{postgres}</dd></div>
                <div><dt>"Load generator"</dt><dd>{generator}</dd></div>
                <div><dt>"Rounds"</dt><dd>{format!("{} rounds on each of {} jobs per implementation, in ABBA order against Axum on the same runner",
                    data.run.rounds.unwrap_or(0), data.run.jobs_per_framework.unwrap_or(0))}</dd></div>
            </dl>
            <p><a href={readme("what-is-measured")}>"What is measured"</a>" · "<a href={readme("method")}>"Method"</a>
               " · "<a href={readme("cpu-split")}>"CPU split"</a></p>
        </section>
        <section class="section" aria-labelledby="rules">
            <h2 id="rules">"How the scores are computed"</h2>
            <p class="section-lede">"The rules as the results state them ("<code>"rankings.method"</code>" in latest.json):"</p>
            <dl class="facts facts-wide">{rules}</dl>
            <p><a href={readme("how-the-scores-are-computed")}>"How the scores are computed"</a></p>
        </section>
        <section class="section" aria-labelledby="environment">
            <h2 id="environment">"Environment"</h2>
            <dl class="facts">
                <div><dt>"Runners"</dt><dd>{machine}</dd></div>
                <div><dt>"Runner CPUs (jobs)"</dt><dd><ul class="chips">{runners}</ul></dd></div>
                <div><dt>"Operating system"</dt><dd>{format!("{}, kernel {}", env.os, env.kernel)}</dd></div>
                <div><dt>"Runner image"</dt><dd>{env.runner_image.as_str()}</dd></div>
                <div><dt>"Docker"</dt><dd>{env.docker.as_str()}</dd></div>
                <div><dt>"PostgreSQL image"</dt><dd><code>{image}</code></dd></div>
            </dl>
        </section>
        {gate(ctx)}
        <section class="section" aria-labelledby="readme-sections">
            <h2 id="readme-sections">"Fairness, authorship and limitations"</h2>
            <div class="howto">
                <article class="howto-card">
                    <h3><a href={readme("fairness")}>"Fairness"</a></h3>
                    <p>"One rule for every implementation, Rullst included: what the framework's own documentation "
                       "recommends for production. Defaults still differ between stacks, and the results show them."</p>
                </article>
                <article class="howto-card">
                    <h3><a href={readme("authorship")}>"Authorship"</a></h3>
                    <p>"One person, the maintainer of Rullst, wrote every implementation, with the help of AI coding "
                       "assistants, and designed the method. Reviews from people who run these frameworks in "
                       "production are welcome."</p>
                </article>
                <article class="howto-card">
                    <h3><a href={readme("limitations")}>"Limitations"</a></h3>
                    <p>"Shared virtual runners with different CPU models, a load generator that cannot saturate the "
                       "fastest servers, short tiers, one small machine over loopback, small endpoints."</p>
                </article>
                <article class="howto-card">
                    <h3><a href={readme("what-this-benchmark-does-not-measure")}>"What it does not measure"</a></h3>
                    <p>"Logins and password hashing, large request bodies, one common session store, real "
                       "deployments with TLS and network latency, scaling beyond 2 vCPUs, latency at a fixed request "
                       "rate, JIT steady state, a database on another host, HTTP/2 and compression."</p>
                </article>
            </div>
        </section>
    };
    Page {
        path: "method/".to_string(),
        title: "Method".to_string(),
        description: "How the Rullst Benchmarks are measured and scored.".to_string(),
        section: Section::Method,
        results: true,
        body,
    }
}

fn gate(ctx: &Ctx) -> Option<Markup> {
    let gate = ctx.data().publication_gate.as_ref()?;
    let table = html! {
        <table class="plain">
            <caption>"Why an automatic run would not have published these results."</caption>
            <thead><tr><th scope="col">"Problem"</th></tr></thead>
            <tbody>{gate.problems.iter().map(|p| html! { <tr><td>{rich(p)}</td></tr> }).collect::<Markup>()}</tbody>
        </table>
    };
    Some(html! {
        <section class="section" aria-labelledby="gate">
            <h2 id="gate">"Publication gate"</h2>
            @if gate.passed {
                <p class="callout callout-ok">"Passed: an automatic run may publish these results."</p>
            } @else {
                <p class="callout callout-warn">{format!("Failed: an automatic run would not publish these results ({} problems):", gate.problems.len())}</p>
                {table_region("Publication gate problems", table)}
            }
            <p><a href={readme("automatic-updates")}>"Automatic updates and the publication gate"</a></p>
        </section>
    })
}
