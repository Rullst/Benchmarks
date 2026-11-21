//! Renders the site from the checked-in fixture (tests/fixtures/results, a trimmed copy of published
//! results with markup injected into a few text fields) and checks the structure of every page, the
//! escaping, the footer, the internal links and the "results pending" page of each fail-closed rule.

use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;

use serde_json::Value;

const MEASURED_ON: &str = "2026-11-20";
const FIXED_PAGES: [&str; 12] = [
    "",
    "hello/",
    "database/",
    "application/",
    "memory/",
    "startup/",
    "stability/",
    "endpoints/",
    "diagnostics/",
    "implementations/",
    "history/",
    "method/",
];
const VOID: [&str; 14] =
    ["area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"];

fn fixture() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/results")
}

fn scratch(name: &str) -> PathBuf {
    let dir = Path::new(env!("CARGO_TARGET_TMPDIR")).join(name);
    let _ = fs::remove_dir_all(&dir);
    fs::create_dir_all(&dir).unwrap();
    dir
}

fn copy_dir(from: &Path, to: &Path) {
    fs::create_dir_all(to).unwrap();
    for entry in fs::read_dir(from).unwrap() {
        let entry = entry.unwrap();
        let target = to.join(entry.file_name());
        if entry.file_type().unwrap().is_dir() {
            copy_dir(&entry.path(), &target);
        } else if entry.path().extension().is_some_and(|e| e == "json") {
            fs::copy(entry.path(), target).unwrap();
        }
    }
}

fn rullst_version() -> String {
    let lock = fs::read_to_string(Path::new(env!("CARGO_MANIFEST_DIR")).join("Cargo.lock")).unwrap();
    let start = lock.find("name = \"rullst\"\nversion = \"").unwrap() + "name = \"rullst\"\nversion = \"".len();
    lock[start..].split('"').next().unwrap().to_string()
}

struct Run {
    ok: bool,
    stderr: String,
    out: PathBuf,
}

fn render(results: &Path, name: &str, today: &str, extra: &[&str]) -> Run {
    let out = scratch(&format!("{name}-out"));
    let output = Command::new(env!("CARGO_BIN_EXE_bench-site"))
        .arg("--results")
        .arg(results)
        .arg("--out")
        .arg(&out)
        .args(["--today", today])
        .args(extra)
        .output()
        .unwrap();
    Run { ok: output.status.success(), stderr: String::from_utf8_lossy(&output.stderr).into_owned(), out }
}

fn page(out: &Path, path: &str) -> String {
    fs::read_to_string(out.join(path).join("index.html")).unwrap_or_else(|e| panic!("{path}index.html: {e}"))
}

fn pages(out: &Path) -> Vec<(String, String)> {
    let mut found = Vec::new();
    let mut stack = vec![out.to_path_buf()];
    while let Some(dir) = stack.pop() {
        for entry in fs::read_dir(&dir).unwrap() {
            let path = entry.unwrap().path();
            if path.is_dir() {
                stack.push(path);
            } else if path.file_name().is_some_and(|n| n == "index.html") {
                let rel = path.parent().unwrap().strip_prefix(out).unwrap().to_string_lossy().into_owned();
                let rel = if rel.is_empty() { rel } else { format!("{rel}/") };
                found.push((rel, fs::read_to_string(&path).unwrap()));
            }
        }
    }
    found.sort();
    found
}

/// Every element closed in order, every void element self-closed, no stray `<` in text.
fn check_tags(name: &str, html: &str) {
    let body = html.strip_prefix("<!DOCTYPE html>").unwrap_or_else(|| panic!("{name}: no doctype"));
    let mut stack: Vec<String> = Vec::new();
    let mut rest = body;
    while let Some(start) = rest.find('<') {
        let after = &rest[start + 1..];
        let end = after.find('>').unwrap_or_else(|| panic!("{name}: unterminated tag"));
        let tag = &after[..end];
        rest = &after[end + 1..];
        if let Some(closing) = tag.strip_prefix('/') {
            let open = stack.pop().unwrap_or_else(|| panic!("{name}: </{closing}> without an open element"));
            assert_eq!(open, closing, "{name}: <{open}> closed by </{closing}>");
            continue;
        }
        let tag_name: String = tag.chars().take_while(|c| c.is_ascii_alphanumeric()).collect();
        assert!(!tag_name.is_empty(), "{name}: unexpected '<{}'", &tag[..tag.len().min(20)]);
        // No script URL, inline style or event handler in any attribute.
        let lower = tag.to_ascii_lowercase();
        assert!(!lower.contains("javascript:") && !lower.contains(" style="), "{name}: <{tag}>");
        assert!(
            !lower.split_whitespace().skip(1).any(|a| a.starts_with("on") && a.contains('=')),
            "{name}: event handler in <{tag}>"
        );
        if tag.ends_with('/') {
            continue;
        }
        assert!(!VOID.contains(&tag_name.as_str()), "{name}: void <{tag_name}> is not self-closed");
        stack.push(tag_name);
    }
    assert!(stack.is_empty(), "{name}: unclosed {stack:?}");
}

fn attribute_values<'a>(html: &'a str, attribute: &str) -> Vec<&'a str> {
    let needle = format!(" {attribute}=\"");
    html.match_indices(&needle)
        .map(|(i, _)| {
            let value = &html[i + needle.len()..];
            &value[..value.find('"').unwrap()]
        })
        .collect()
}

/// Relative links point at a page or file the generator wrote (data/ is copied by the deploy workflow).
fn check_links(out: &Path, path: &str, html: &str) {
    let base = out.join(path);
    for href in attribute_values(html, "href").into_iter().chain(attribute_values(html, "src")) {
        if href.starts_with("https://") || href.starts_with('#') {
            continue;
        }
        assert!(!href.starts_with("http:") && !href.contains(':'), "{path}: unexpected link {href}");
        let target = href.split(['#', '?']).next().unwrap();
        let resolved = base.join(target);
        let normal = normalize(&resolved);
        if normal.strip_prefix(out).is_ok_and(|p| p.starts_with("data")) {
            continue;
        }
        let file = if target.is_empty() || target.ends_with('/') { normal.join("index.html") } else { normal };
        assert!(file.is_file(), "{path}: broken link {href} ({})", file.display());
    }
}

fn normalize(path: &Path) -> PathBuf {
    let mut out = PathBuf::new();
    for part in path.components() {
        match part {
            std::path::Component::ParentDir => {
                out.pop();
            }
            std::path::Component::CurDir => {}
            other => out.push(other),
        }
    }
    out
}

fn check_shell(path: &str, html: &str) {
    let version = rullst_version();
    assert!(html.starts_with("<!DOCTYPE html><html lang=\"en\">"), "{path}: document start");
    assert!(
        html.contains("<meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'none'; style-src 'self'; img-src 'self'; base-uri 'none'; form-action 'none'\" />"),
        "{path}: CSP"
    );
    assert_eq!(html.matches("<h1").count(), 1, "{path}: one h1");
    for landmark in [
        "<header class=\"site-header\">",
        "<nav class=\"site-nav\" aria-label=\"Sections\">",
        "<main id=\"main\"",
        "<footer class=\"site-footer\">",
    ] {
        assert!(html.contains(landmark), "{path}: {landmark}");
    }
    assert!(html.contains("<a class=\"skip-link\" href=\"#main\">"), "{path}: skip link");
    let footer = &html[html.find("<footer").unwrap()..];
    assert!(footer.contains("Made with <a href=\"https://rullst.win/\">Rullst</a>"), "{path}: Made with Rullst");
    assert!(footer.contains(&format!("<span class=\"version\">{version}</span>")), "{path}: rullst version {version}");
    assert!(!html.contains("<script"), "{path}: script element");
}

#[test]
fn renders_every_page_from_the_fixture() {
    let run = render(&fixture(), "ok", "2026-11-21", &["--require-results"]);
    assert!(run.ok, "{}", run.stderr);
    let all = pages(&run.out);
    for path in FIXED_PAGES {
        assert!(all.iter().any(|(p, _)| p == path), "missing page {path}");
    }
    let latest: Value = serde_json::from_str(&fs::read_to_string(fixture().join("latest.json")).unwrap()).unwrap();
    for row in latest["results"].as_array().unwrap() {
        let slug = row["slug"].as_str().unwrap();
        assert!(all.iter().any(|(p, _)| *p == format!("implementations/{slug}/")), "no page for {slug}");
    }
    assert!(run.out.join("assets/site.css").is_file() && run.out.join("assets/favicon.svg").is_file());
    for (path, html) in &all {
        check_shell(path, html);
        check_tags(path, html);
        check_links(&run.out, path, html);
        assert!(!html.contains("Results pending"), "{path}: pending");
        assert!(html.contains("This benchmark is maintained by Rullst&#x27;s maintainer"), "{path}: disclosure");
    }
}

#[test]
fn shows_the_rankings_reading_and_diagnostics_apart() {
    let run = render(&fixture(), "content", "2026-11-21", &[]);
    assert!(run.ok, "{}", run.stderr);
    let overview = page(&run.out, "");
    // Position ranges, tie groups, margins, flags and the sensitivity table.
    assert!(overview.contains("<span class=\"pos-num\">4–5</span><span class=\"pos-tie\">tie</span>"));
    assert!(overview.contains("±5.5%"));
    assert!(overview.contains("0.75‡"));
    assert!(overview.contains("Other weightings") && overview.contains("Equal weights"));
    // The generated reading in both languages, with its disclosure.
    assert!(overview.contains("What this means for Rullst"));
    assert!(overview.contains("Rullst as <code>cargo rullst new</code> generates it"));
    assert!(
        overview.contains("lang=\"pt-BR\"")
            && overview.contains("O Rullst como o <code>cargo rullst new</code> o gera")
    );
    // Diagnostics and the A/A control are not rows of the ranking table.
    let ranking = &overview[overview.find("<table class=\"ranking\">").unwrap()..];
    let ranking = &ranking[..ranking.find("</table>").unwrap()];
    for slug in ["axum-no-ping", "axum-control", "rullst-minimal"] {
        assert!(!ranking.contains(&format!("implementations/{slug}/")), "{slug} in the ranking");
    }
    let database = page(&run.out, "database/");
    assert!(database.contains("0.057*†"), "† flag");
    assert!(database.contains("Diagnostics and the A/A control"));
    let memory = page(&run.out, "memory/");
    assert!(memory.contains("Peak after the 125 logins (MiB), not scored"));
    assert!(memory.contains("470 (927)"), "post-login peak with Axum's");
    let endpoints = page(&run.out, "endpoints/");
    for id in ["ep-text", "ep-world-update", "ep-me", "hot-rows", "tier2", "tier3", "tier4"] {
        assert!(endpoints.contains(&format!("id=\"{id}\"")), "endpoints: {id}");
    }
    let history = page(&run.out, "history/");
    assert!(history.contains("bombardier 2.0.2") && history.contains("wrk 4.2.0"));
    let rullst = page(&run.out, "implementations/rullst/");
    assert!(rullst.contains("EPYC 9V74") && rullst.contains("13.0.0-alpha.6"));
}

#[test]
fn escapes_text_from_the_results() {
    let run = render(&fixture(), "escape", "2026-11-21", &[]);
    assert!(run.ok, "{}", run.stderr);
    let all: String = pages(&run.out).into_iter().map(|(_, html)| html).collect();
    assert!(all.contains("&lt;script&gt;alert(&quot;structure_note&quot;)&lt;/script&gt;"));
    assert!(all.contains("&lt;img src=x onerror=alert(1)&gt; &amp; &quot;quotes&quot;"));
    assert!(all.contains("&lt;b&gt;not bold&lt;/b&gt;"));
    assert!(!all.contains("<b>not bold</b>") && !all.contains("<img"));
}

fn mutate(name: &str, file: &str, change: impl FnOnce(&mut Value)) -> PathBuf {
    let dir = scratch(name);
    copy_dir(&fixture(), &dir);
    let path = dir.join(file);
    let mut value: Value = serde_json::from_str(&fs::read_to_string(&path).unwrap()).unwrap();
    change(&mut value);
    fs::write(&path, serde_json::to_string(&value).unwrap()).unwrap();
    dir
}

fn assert_pending(run: &Run, reason: &str) {
    assert!(run.ok, "pending pages are still written: {}", run.stderr);
    assert!(run.stderr.contains(reason), "reason {reason:?} not in {:?}", run.stderr);
    let all = pages(&run.out);
    assert_eq!(all.len(), FIXED_PAGES.len(), "only the fixed pages");
    for (path, html) in &all {
        check_shell(path, html);
        check_tags(path, html);
        assert!(html.contains("<h1>Results pending</h1>"), "{path}: pending");
        for number in ["0.75", "Actix Web", "pos-num", "score-value", "Topcoat"] {
            assert!(!html.contains(number), "{path}: shows {number}");
        }
        assert!(!html.contains("Who runs this benchmark"), "{path}: results disclosure without results");
    }
}

#[test]
fn fails_closed() {
    let missing = scratch("missing");
    copy_dir(&fixture(), &missing);
    fs::remove_file(missing.join("latest.json")).unwrap();
    assert_pending(&render(&missing, "missing", "2026-11-21", &[]), "latest.json: cannot be read");

    let schema = mutate("schema", "latest.json", |v| v["schema"] = "rullst.benchmarks.latest.v2".into());
    assert_pending(&render(&schema, "schema", "2026-11-21", &[]), "schema is not");

    let invalid = scratch("invalid");
    copy_dir(&fixture(), &invalid);
    let text = fs::read_to_string(invalid.join("site.json")).unwrap();
    fs::write(invalid.join("site.json"), &text[..text.len() / 2]).unwrap();
    assert_pending(&render(&invalid, "invalid", "2026-11-21", &[]), "site.json: not in the expected shape");

    assert_pending(&render(&fixture(), "stale", "2027-02-19", &[]), "more than 90 days");
    assert!(render(&fixture(), "fresh", "2027-02-18", &["--require-results"]).ok, "90 days is still shown");
    assert_pending(&render(&fixture(), "short", "2026-11-22", &["--max-age-days", "1"]), "more than 1 days");
    assert_pending(
        &render(&fixture(), "future", "2026-11-19", &[]),
        &format!("measured_on {MEASURED_ON} is after today"),
    );

    let status =
        mutate("status", "latest.json", |v| v["rankings"]["categories"][0]["entries"][0]["status"] = "promoted".into());
    assert_pending(&render(&status, "status", "2026-11-21", &[]), "latest.json: not in the expected shape");

    let run = mutate("run", "site.json", |v| v["run"]["id"] = "1".into());
    assert_pending(&render(&run, "run", "2026-11-21", &[]), "same run as latest.json");

    let flag = mutate("flag", "site.json", |v| v["flags"]["new_flag"] = "§".into());
    assert_pending(&render(&flag, "flag", "2026-11-21", &[]), "unknown flags");

    let path = mutate("path", "versions.json", |v| v["versions"][0]["file"] = "../latest.json".into());
    assert_pending(&render(&path, "path", "2026-11-21", &[]), "unexpected version entry");

    let url = mutate("url", "latest.json", |v| v["run"]["url"] = "javascript:alert(1)".into());
    assert_pending(&render(&url, "url", "2026-11-21", &[]), "unexpected run");

    let required = render(&schema, "required", "2026-11-21", &["--require-results"]);
    assert!(!required.ok && required.stderr.contains("results pending"), "{}", required.stderr);
}
