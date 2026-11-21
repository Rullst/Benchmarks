//! The page shell: head (with the Content-Security-Policy), header, navigation and footer.

use rullst::html;
use rullst::html::Markup;

pub const REPO: &str = "https://github.com/Rullst/Benchmarks";
pub const README: &str = "https://github.com/Rullst/Benchmarks/blob/main/README.md";
pub const RULLST_SITE: &str = "https://rullst.win/";
/// The `rullst` crate this generator was built with (build.rs reads it from Cargo.lock).
pub const RULLST_VERSION: &str = env!("RULLST_VERSION");
/// bench/reading.py DISCLOSURE: who maintains the benchmark.
pub const DISCLOSURE: &str = "This benchmark is maintained by Rullst's maintainer, who also wrote every implementation \
                              in it and designed the method.";

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Section {
    Rankings,
    Endpoints,
    Diagnostics,
    Implementations,
    History,
    Method,
}

const NAV: [(&str, &str, Section); 6] = [
    ("", "Rankings", Section::Rankings),
    ("endpoints/", "Endpoints", Section::Endpoints),
    ("diagnostics/", "Diagnostics", Section::Diagnostics),
    ("implementations/", "Implementations", Section::Implementations),
    ("history/", "History", Section::History),
    ("method/", "Method", Section::Method),
];

pub struct Page {
    /// The output directory of the page: "" for the overview, "hello/", "implementations/rullst/".
    pub path: String,
    pub title: String,
    pub description: String,
    pub section: Section,
    /// The page shows results: the footer carries the authorship disclosure.
    pub results: bool,
    pub body: Markup,
}

/// The relative prefix from a page to the site root.
pub fn root(path: &str) -> String {
    match path.matches('/').count() {
        0 => "./".to_string(),
        depth => "../".repeat(depth),
    }
}

pub fn readme(anchor: &str) -> String {
    format!("{README}#{anchor}")
}

pub fn document(page: &Page, css: &str) -> Markup {
    let root = root(&page.path);
    let css_href = format!("{root}{css}");
    let icon = format!("{root}assets/favicon.svg");
    let title = if page.path.is_empty() { page.title.clone() } else { format!("{} · Rullst Benchmarks", page.title) };
    let nav: Markup = NAV
        .iter()
        .map(|&(target, text, section)| {
            let href = format!("{root}{target}");
            let current = (section == page.section).then_some(if target == page.path { "page" } else { "true" });
            html! { <li><a href={href} aria-current?={current}>{text}</a></li> }
        })
        .collect();
    html! {
        <!DOCTYPE html>
        <html lang="en">
            <head>
                <meta charset="utf-8" />
                <meta name="viewport" content="width=device-width, initial-scale=1" />
                // No script, no inline style, no remote resource: the strictest policy a meta tag can set on
                // GitHub Pages (frame-ancestors and report-uri are ignored in a meta policy).
                <meta http-equiv="Content-Security-Policy"
                    content="default-src 'none'; style-src 'self'; img-src 'self'; base-uri 'none'; form-action 'none'" />
                <meta name="referrer" content="strict-origin-when-cross-origin" />
                <meta name="color-scheme" content="light dark" />
                <title>{title}</title>
                <meta name="description" content={page.description.as_str()} />
                <link rel="icon" type="image/svg+xml" href={icon} />
                <link rel="stylesheet" href={css_href} />
            </head>
            <body>
                <a class="skip-link" href="#main">"Skip to the content"</a>
                <header class="site-header">
                    <div class="shell header-bar">
                        <a class="brand" href={root.as_str()}>
                            <span class="brand-word">"Rullst"</span><span class="brand-period">"."</span>
                            <span class="brand-sub">"Benchmarks"</span>
                        </a>
                        <nav class="site-nav" aria-label="Sections"><ul>{nav}</ul></nav>
                    </div>
                </header>
                <main id="main" class="shell" tabindex="-1">{&page.body}</main>
                {footer(page, &root)}
            </body>
        </html>
    }
}

fn footer(page: &Page, root: &str) -> Markup {
    let data = |name: &str| format!("{root}data/{name}");
    html! {
        <footer class="site-footer">
            <div class="shell footer-inner">
                @if page.results {
                    <p class="footer-disclosure">
                        <strong>"Who runs this benchmark: "</strong>{DISCLOSURE}" "
                        <a href={readme("authorship")}>"Authorship"</a>" · "
                        <a href={format!("{REPO}/blob/main/CONTRIBUTING.md")}>"How to correct an implementation"</a>
                    </p>
                }
                <p class="made-with">
                    "Made with "<a href={RULLST_SITE}>"Rullst"</a>" "<span class="version">{RULLST_VERSION}</span>
                    <span class="made-detail">": static pages rendered by Rullst's "<code>"html!"</code>
                    " macro from the published results files."</span>
                </p>
                <ul class="footer-links">
                    <li><a href={REPO}>"Source"</a></li>
                    <li><a href={README}>"README"</a></li>
                    <li><a href={format!("{REPO}/blob/main/benchmarks_results.md")}>"Results (Markdown)"</a></li>
                    @if page.results {
                        <li><a href={data("latest.json")}>"latest.json"</a></li>
                        <li><a href={data("site.json")}>"site.json"</a></li>
                        <li><a href={data("versions.json")}>"versions.json"</a></li>
                    }
                    <li><a href={format!("{REPO}/blob/main/LICENSE")}>"MIT License"</a></li>
                </ul>
            </div>
        </footer>
    }
}

/// Text from the results with its backtick-quoted parts as code; an unpaired backtick leaves the text as is.
pub fn rich(text: &str) -> Markup {
    if text.matches('`').count() % 2 == 1 {
        return html! { {text} };
    }
    text.split('`')
        .enumerate()
        .map(|(i, part)| {
            if i % 2 == 1 {
                html! { <code>{part}</code> }
            } else {
                html! { {part} }
            }
        })
        .collect()
}

/// A table in its own scrolling region, so that a wide table never widens the page.
pub fn table_region(label: &str, table: Markup) -> Markup {
    html! { <div class="table-wrap" role="region" aria-label={label} tabindex="0">{table}</div> }
}

/// The page heading block: an eyebrow, the title and a lede.
pub fn page_head(eyebrow: &str, title: &str, lede: Markup) -> Markup {
    html! {
        <div class="page-head">
            <p class="eyebrow"><span class="eyebrow-line"></span>{eyebrow}</p>
            <h1>{title}</h1>
            <div class="lede">{lede}</div>
        </div>
    }
}
