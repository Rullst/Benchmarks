//! `/endpoints/`: the summary tables, one table per Tier 1 endpoint, the hot-rows run and Tiers 2 to 4.

use rullst::html;
use rullst::html::Markup;

use crate::context::Ctx;
use crate::data::Row;
use crate::format::{self, DASH, median, paired, range, ratio, serves};
use crate::layout::{Page, Section, page_head, rich};
use crate::pages::common::notes;
use crate::pages::tables::{RowColumn, num, row_table, text};

const SUMMARY: [&str; 6] = ["json", "html", "db-single", "queries", "updates", "fortunes"];
const APPLICATION: [&str; 5] = ["world", "worlds", "world-update", "form", "me"];

pub fn page(ctx: &Ctx) -> Page {
    let root = "../";
    let data = ctx.data();
    let config = &data.config;
    let tiers = &config.tiers;
    let (main, apart) = ctx.measured_split();
    let toc: Markup = data
        .config
        .tiers
        .tier1
        .endpoints
        .iter()
        .map(|ep| html! { <li><a href={format!("#ep-{ep}")}>{format::endpoint_label(config, ep)}</a></li> })
        .collect();
    let lede = html! {
        <p>"The numbers behind the scores: requests per second (median of every round, with the lowest and "
           "highest round), the ratio to Axum on the same runners, efficiency (requests per server CPU-second), "
           "latency, errors and CPU. Absolute numbers come from different runners: compare them only within a "
           "row, and across rows through the ratios."</p>
    };
    let per_endpoint: Markup =
        tiers.tier1.endpoints.iter().map(|ep| endpoint_section(ctx, root, ep, &main, &apart)).collect();
    let body = html! {
        {page_head("Tier 1 to Tier 4", "Endpoints and load tiers", lede)}
        <nav class="toc" aria-label="On this page">
            <ul>
                <li><a href="#summary">"Summary"</a></li>
                <li><a href="#application">"Application endpoints"</a></li>
                {toc}
                <li><a href="#hot-rows">"Hot rows"</a></li>
                <li><a href="#tier2">"Tier 2"</a></li>
                <li><a href="#tier3">"Tier 3 (memory)"</a></li>
                <li><a href="#tier4">"Tier 4"</a></li>
            </ul>
        </nav>
        {summary(ctx, root, &main, &apart)}
        {application(ctx, root, &main, &apart)}
        <section class="section" aria-labelledby="tier1">
            <h2 id="tier1">{format!("Tier 1: {} connections, {} s per endpoint", tiers.tier1.connections, format::num(Some(tiers.tier1.duration_s), 0))}</h2>
            <p class="section-lede">"Each endpoint is warmed up just before its run (longer for runtimes with a JIT "
               "compiler). Efficiency is requests per server CPU-second; CPU µs/req is the server's and "
               "PostgreSQL's CPU time per request together, PG µs/req PostgreSQL's alone."</p>
            {per_endpoint}
        </section>
        {hot_rows(ctx, root, &main, &apart)}
        {tier2(ctx, root, &main, &apart)}
        {tier3(ctx, root, &main, &apart)}
        {tier4(ctx, root, &main, &apart)}
        {warmup(ctx, root)}
        {not_measured(ctx, root)}
        {notes(ctx, true, true)}
    };
    Page {
        path: "endpoints/".to_string(),
        title: "Endpoints and load tiers".to_string(),
        description: "Per-endpoint results of the Rullst Benchmarks: requests per second, ratios to Axum, latency, \
                      errors, CPU and memory."
            .to_string(),
        section: Section::Endpoints,
        results: true,
        body,
    }
}

fn served_ratio(row: &Row, endpoint: &str) -> String {
    if serves(row, endpoint) { ratio(row, &format!("tier1.{endpoint}.rps")) } else { "n/i".to_string() }
}

fn summary(ctx: &Ctx, root: &str, main: &[&Row], apart: &[&Row]) -> Markup {
    let mut columns: Vec<RowColumn> =
        vec![text("Version", |r| r.framework_version.clone()), text("Language", |r| r.language.clone())];
    for ep in SUMMARY {
        columns.push(num(format!("/{ep} vs Axum"), move |r| served_ratio(r, ep)));
    }
    columns.push(num("/json req/s (Axum)", |r| paired(r, "tier1.json.rps", 0)));
    columns.push(num("Idle RAM (MiB)", |r| format::num(median(r, "tier3.idle_ram_mib"), 1)));
    columns.push(num("Peak RAM (MiB)", |r| format::num(median(r, "tier3.load_ram_peak_mib"), 1)));
    columns.push(text("Runner CPUs", format::runners));
    html! {
        <section class="section" aria-labelledby="summary">
            <h2 id="summary">"Summary"</h2>
            {row_table(ctx, root, "Summary", None, main, apart, &columns)}
            <p class="table-note">"Ratios are requests/s divided by Axum's on the same runners (higher is better); "
               "the scores in the rankings use capacity ratios instead. \"/json req/s (Axum)\" is the absolute number "
               "with Axum's on the same runners in brackets. Peak RAM is the Memory category's high-water mark, "
               "measured before the logins of the application endpoints. \"n/i\": not implemented. /queries and "
               "/updates use queries=20."</p>
        </section>
    }
}

fn application(ctx: &Ctx, root: &str, main: &[&Row], apart: &[&Row]) -> Markup {
    let mut columns: Vec<RowColumn> = Vec::new();
    for ep in APPLICATION {
        let label = format::endpoint_label(&ctx.data().config, ep);
        let flagged = ep == "world-update" && ctx.put_note().is_some();
        let title = if flagged { format!("{label} vs Axum ‡") } else { format!("{label} vs Axum") };
        columns.push(num(title, move |r| {
            let value = served_ratio(r, ep);
            if ep == "world-update" && ctx.put_flagged.contains(r.slug.as_str()) && value != DASH && value != "n/i" {
                format!("{value} ‡")
            } else {
                value
            }
        }));
    }
    columns.push(text("CSRF", |r| if serves(r, "form") { format::mechanism(r, true) } else { "n/i".to_string() }));
    columns
        .push(text("Session store", |r| if serves(r, "me") { format::mechanism(r, false) } else { "n/i".to_string() }));
    columns.push(num(format!("Peak RAM after the {} logins (MiB)", ctx.logins()), |r| {
        paired(r, "application.ram_peak_mib", 0)
    }));
    columns.push(num("Hot rows p99 (ms)", |r| format::num(median(r, "hot_rows.latency_ms.p99"), 2)));
    columns.push(num("Hot rows errors", |r| format::error_rate(median(r, "hot_rows.error_rate"))));
    html! {
        <section class="section" aria-labelledby="application">
            <h2 id="application">"Application endpoints"</h2>
            {row_table(ctx, root, "Application endpoints", None, main, apart, &columns)}
            <p class="table-note">"CSRF is the design of the form protection (token: a secret the form echoes; "
               "fetch-metadata: Sec-Fetch-Site/Origin checks) and the session store is each framework's default for a "
               "signed-in user, with where the mechanism comes from (built-in, generator, stdlib, documented, "
               "library): POST /form and GET /me compare those defaults, not one common mechanism. Peak RAM after the "
               "logins: the server's highest RAM while answering the application endpoints and the hot-rows run, "
               "after each round signed its users in (a memory-hard password hash can leave hundreds of MiB in the "
               "allocator), with Axum's in brackets; no score includes it. Hot rows: PUT /world/{id} on ids 1-10 only; "
               "reported, not ranked."</p>
        </section>
    }
}

fn endpoint_notes(ctx: &Ctx, row: &Row, endpoint: &str) -> String {
    if !serves(row, endpoint) {
        return "not implemented".to_string();
    }
    let run = format!("tier1.{endpoint}");
    let mut notes: Vec<String> = Vec::new();
    if !row.database_note.is_empty() && format::DB_ENDPOINTS.contains(&endpoint) {
        notes.push(format!("† {}", row.database_note));
    }
    if endpoint == "world-update" && ctx.put_flagged.contains(row.slug.as_str()) {
        notes.push("‡ most measured requests did not write (see the note)".to_string());
    }
    let bound = format::bound(row, &run);
    if !bound.is_empty() {
        notes.push(bound);
    }
    if let Some(updated) = median(row, &format!("{run}.rows_updated_per_request")) {
        notes.push(format!("{updated:.2} rows updated per request"));
    }
    if let Some(warm) = row.flags.warmup_errors.get(endpoint).filter(|n| **n > 0) {
        notes.push(format!("{warm} warm-up errors"));
    }
    if endpoint == "form" {
        notes.push(format!("CSRF: {}", format::mechanism(row, true)));
    }
    if endpoint == "me" {
        notes.push(format!("session: {}", format::mechanism(row, false)));
    }
    notes.join("; ")
}

fn endpoint_section(ctx: &Ctx, root: &str, endpoint: &str, main: &[&Row], apart: &[&Row]) -> Markup {
    let base = format!("tier1.{endpoint}");
    let database = format::DB_ENDPOINTS.contains(&endpoint);
    let path = |name: &str| format!("{base}.{name}");
    let (rps, rpc, cpu, db, db_r) = (
        path("rps"),
        path("rps_per_cpu"),
        path("cpu_us_per_request"),
        path("db_us_per_request"),
        path("db_us_per_request"),
    );
    let (p50, p99, err, server, dbc) = (
        path("latency_ms.p50"),
        path("latency_ms.p99"),
        path("error_rate"),
        path("server_cpu_cores"),
        path("db_cpu_cores"),
    );
    let mut columns: Vec<RowColumn> = vec![
        num("req/s", {
            let p = rps.clone();
            move |r| range(r, &p, 0)
        }),
        num("vs Axum", {
            let p = rps.clone();
            move |r| ratio(r, &p)
        }),
        num("Efficiency (req/CPU-s)", {
            let p = rpc.clone();
            move |r| format::num(median(r, &p), 0)
        }),
        num("vs Axum", {
            let p = rpc.clone();
            move |r| ratio(r, &p)
        }),
        num("CPU µs/req", move |r| format::num(median(r, &cpu), 1)),
    ];
    if database {
        columns.push(num("PG µs/req", move |r| format::num(median(r, &db), 1)));
        columns.push(num("vs Axum", move |r| ratio(r, &db_r)));
    }
    columns.push(num("p50 (ms)", move |r| format::num(median(r, &p50), 2)));
    columns.push(num("p99 (ms)", move |r| format::num(median(r, &p99), 2)));
    columns.push(num("Errors", move |r| format::error_rate(median(r, &err))));
    columns.push(num("Server CPU (cores)", move |r| format::num(median(r, &server), 2)));
    columns.push(num("DB CPU (cores)", move |r| format::num(median(r, &dbc), 2)));
    let owned = endpoint.to_string();
    columns.push(text("Notes", move |r| endpoint_notes(ctx, r, &owned)));
    let title = format::endpoint_label(&ctx.data().config, endpoint);
    let id = format!("ep-{endpoint}");
    html! {
        <section class="subsection" aria-labelledby={id.as_str()}>
            <h3 id={id.as_str()}>{title.as_str()}</h3>
            {row_table(ctx, root, &title, None, main, apart, &columns)}
        </section>
    }
}

fn hot_rows(ctx: &Ctx, root: &str, main: &[&Row], apart: &[&Row]) -> Option<Markup> {
    let hot = ctx.data().config.hot_rows.as_ref();
    let endpoint = hot.map(|h| h.endpoint.as_str()).filter(|e| !e.is_empty()).unwrap_or("world-update");
    let ids = hot.and_then(|h| h.ids).unwrap_or(10);
    if !main.iter().chain(apart).any(|r| median(r, "hot_rows.rps").is_some()) {
        return None;
    }
    fn serving<'r>(rows: &[&'r Row], endpoint: &str) -> Vec<&'r Row> {
        rows.iter().copied().filter(|r| serves(r, endpoint)).collect()
    }
    let columns: Vec<RowColumn> = vec![
        num("req/s", |r| range(r, "hot_rows.rps", 0)),
        num("vs Axum", |r| ratio(r, "hot_rows.rps")),
        num("p50 (ms)", |r| format::num(median(r, "hot_rows.latency_ms.p50"), 2)),
        num("p99 (ms)", |r| format::num(median(r, "hot_rows.latency_ms.p99"), 2)),
        num("p99 vs Axum", |r| ratio(r, "hot_rows.latency_ms.p99")),
        num("Errors", |r| format::error_rate(median(r, "hot_rows.error_rate"))),
        num("Timeouts", |r| format::num(median(r, "hot_rows.timeouts"), 0)),
        num("PG µs/req", |r| format::num(median(r, "hot_rows.db_us_per_request"), 1)),
        num("DB CPU (cores)", |r| format::num(median(r, "hot_rows.db_cpu_cores"), 2)),
    ];
    let t1 = &ctx.data().config.tiers.tier1;
    Some(html! {
        <section class="section" aria-labelledby="hot-rows">
            <h2 id="hot-rows">{format!("Write contention: PUT /world/{{id}} on ids 1-{ids} (hot rows)")}</h2>
            <p class="section-lede">{format!("{} connections for {} s write the same {ids} rows, so requests wait \
               for each other's row locks. Reported, not ranked: compare the errors, timeouts and p99 latency.",
               t1.connections, format::num(Some(t1.duration_s), 0))}</p>
            {row_table(ctx, root, "Hot rows", None, &serving(main, endpoint), &serving(apart, endpoint), &columns)}
        </section>
    })
}

fn tier2(ctx: &Ctx, root: &str, main: &[&Row], apart: &[&Row]) -> Markup {
    let t2 = &ctx.data().config.tiers.tier2;
    let columns: Vec<RowColumn> = vec![
        num("req/s", |r| range(r, "tier2.rps", 0)),
        num("vs Axum", |r| ratio(r, "tier2.rps")),
        num("Efficiency (req/CPU-s)", |r| format::num(median(r, "tier2.rps_per_cpu"), 0)),
        num("vs Axum", |r| ratio(r, "tier2.rps_per_cpu")),
        num("p50 (ms)", |r| format::num(median(r, "tier2.latency_ms.p50"), 2)),
        num("p99 (ms)", |r| range(r, "tier2.latency_ms.p99", 2)),
        num("p99 vs Axum", |r| ratio(r, "tier2.latency_ms.p99")),
        num("Errors", |r| format::error_rate(median(r, "tier2.error_rate"))),
        num("Timeouts", |r| format::num(median(r, "tier2.timeouts"), 0)),
        text("Notes", |r| format::bound(r, "tier2")),
    ];
    let title = format!(
        "Tier 2 (stability check): /{}, {} connections, {} s",
        t2.endpoint,
        t2.connections,
        format::num(Some(t2.duration_s), 0)
    );
    html! {
        <section class="section" aria-labelledby="tier2">
            <h2 id="tier2">{title}</h2>
            {row_table(ctx, root, "Tier 2", None, main, apart, &columns)}
            <p class="table-note">"For latency, a ratio above 1.00 means more latency than Axum (lower is better)."</p>
        </section>
    }
}

fn tier3(ctx: &Ctx, root: &str, main: &[&Row], apart: &[&Row]) -> Markup {
    let t3 = &ctx.data().config.tiers.tier3;
    let columns: Vec<RowColumn> = vec![
        num("Idle RAM (MiB)", |r| range(r, "tier3.idle_ram_mib", 1)),
        num("vs Axum", |r| ratio(r, "tier3.idle_ram_mib")),
        num("Idle CPU", |r| format::num(median(r, "tier3.idle_cpu_cores"), 3)),
        num("Peak RAM (MiB)", |r| range(r, "tier3.load_ram_peak_mib", 1)),
        num("vs Axum", |r| ratio(r, "tier3.load_ram_peak_mib")),
        num(format!("Peak after the {} logins (MiB)", ctx.logins()), |r| paired(r, "application.ram_peak_mib", 0)),
        num("Load CPU", |r| format::num(median(r, "tier3.load_cpu_cores"), 2)),
        num("req/s", |r| format::num(median(r, "tier3.rps"), 0)),
        num("Tier 1 /json req/s per MiB", |r| format::num(r.rps_per_mib, 1)),
        num("Threads", |r| format::num(median(r, "idle.tasks"), 0)),
        text("Notes", |r| format::bound(r, "tier3_load")),
    ];
    let title = format!(
        "Tier 3: idle, then /{} with {} connections for {} s",
        t3.endpoint,
        t3.connections,
        format::num(Some(t3.duration_s), 0)
    );
    html! {
        <section class="section" aria-labelledby="tier3">
            <h2 id="tier3">{title}</h2>
            {row_table(ctx, root, "Tier 3", None, main, apart, &columns)}
            <p class="table-note">"Idle is measured after start-up, before any load. Peak RAM (the Memory "
               "category's high-water mark) is measured after the phase-1 Tier 1 runs, Tiers 2 and 4 and an idle "
               "period, and before the logins; the peak after the logins, with Axum's in brackets, is part of no "
               "score. For RAM, a ratio above 1.00 means more RAM than Axum. CPU is in cores (2.00 = both server "
               "vCPUs busy)."</p>
        </section>
    }
}

fn tier4(ctx: &Ctx, root: &str, main: &[&Row], apart: &[&Row]) -> Markup {
    let t4 = &ctx.data().config.tiers.tier4;
    let columns: Vec<RowColumn> = vec![
        num("req/s", |r| range(r, "tier4.rps", 0)),
        num("vs Axum", |r| ratio(r, "tier4.rps")),
        num("Efficiency (req/CPU-s)", |r| format::num(median(r, "tier4.rps_per_cpu"), 0)),
        num("p99 (ms)", |r| format::num(median(r, "tier4.latency_ms.p99"), 2)),
        num("Errors", |r| format::error_rate(median(r, "tier4.error_rate"))),
        num("Timeouts", |r| format::num(median(r, "tier4.timeouts"), 0)),
        num("RAM at end (MiB)", |r| format::num(median(r, "tier4.ram_end_mib"), 1)),
        num("RAM growth (MiB)", |r| format::num(median(r, "tier4.ram_growth_mib"), 1)),
        num("memory.peak (MiB)", |r| format::num(median(r, "after.memory_peak_mib"), 1)),
        text("Notes", |r| {
            let mut notes = Vec::new();
            if r.flags.crashed_rounds > 0 {
                notes.push(format!("stopped in {}/{} rounds", r.flags.crashed_rounds, r.flags.rounds));
            }
            if r.flags.ram_growing_rounds > 0 {
                notes.push(format!("RAM still growing in Tier 4 ({}/{})", r.flags.ram_growing_rounds, r.flags.rounds));
            }
            if !r.maturity_note.is_empty() {
                notes.push(r.maturity_note.clone());
            }
            notes.join("; ")
        }),
    ];
    let minutes = t4.duration_s / 60.0;
    let title = format!(
        "Tier 4 (stability check): /{}, {} connections for {} minutes",
        t4.endpoint,
        t4.connections,
        format::num(Some(minutes), 0)
    );
    html! {
        <section class="section" aria-labelledby="tier4">
            <h2 id="tier4">{title}</h2>
            {row_table(ctx, root, "Tier 4", None, main, apart, &columns)}
            <p class="table-note">"RAM growth compares the middle and the last tenth of the test. \"Still growing\" "
               "means it rose by more than 10% and 8 MiB; for garbage-collected runtimes this can be heap growth "
               "rather than a leak."</p>
        </section>
    }
}

fn warmup(ctx: &Ctx, root: &str) -> Option<Markup> {
    let rows: Vec<&Row> =
        ctx.measured().into_iter().filter(|r| r.flags.warmup_errors.values().any(|n| *n > 0)).collect();
    if rows.is_empty() {
        return None;
    }
    let columns = vec![text("Warm-up errors", |r: &Row| {
        r.flags
            .warmup_errors
            .iter()
            .filter(|(_, n)| **n > 0)
            .map(|(ep, n)| format!("/{ep}: {n}"))
            .collect::<Vec<_>>()
            .join(", ")
    })];
    Some(html! {
        <section class="section" aria-labelledby="warmup">
            <h2 id="warmup">"Warm-up errors"</h2>
            <p class="section-lede">"Responses that were not 2xx or failed during the warm-ups, summed over the "
               "rounds; the warm-ups are not scored."</p>
            {row_table(ctx, root, "Warm-up errors", None, &rows, &[], &columns)}
        </section>
    })
}

fn not_measured(ctx: &Ctx, root: &str) -> Option<Markup> {
    let rows: Vec<&Row> = ctx.data().not_measured.iter().collect();
    if rows.is_empty() {
        return None;
    }
    let columns =
        vec![text("Status", |r: &Row| format::status_text(r).to_string()), text("Reason", |r: &Row| r.problem.clone())];
    Some(html! {
        <section class="section" aria-labelledby="not-measured">
            <h2 id="not-measured">"Not measured"</h2>
            <p class="section-lede">"These implementations were not measured in this run. A failed conformance check "
               "means at least one endpoint did not return the expected response."</p>
            {row_table(ctx, root, "Not measured", None, &rows, &[], &columns)}
            <p class="table-note">{rich("Each folder's README under `frameworks/` says how it is set up.")}</p>
        </section>
    })
}
