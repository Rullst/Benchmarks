//! Renders the results website of Rullst/Benchmarks from the results files with Rullst's `html!`.
//!
//! ```text
//! bench-site --results ../results --out ../_site [--today YYYY-MM-DD] [--max-age-days 90] [--require-results]
//! ```
//!
//! Without usable results (missing, unknown schema, inconsistent, out of range, or measured more than
//! `--max-age-days` days before `--today`) every page says "results pending" and shows no numbers;
//! `--require-results` then exits with an error instead (for CI).

mod charts;
mod check;
mod components;
mod context;
mod data;
mod dates;
mod format;
mod layout;
mod pages;

use std::fs;
use std::path::{Path, PathBuf};
use std::process::ExitCode;

use dates::Date;
use layout::{Page, document};

const CSS: &str = include_str!("../assets/site.css");
const FAVICON: &str = include_str!("../assets/favicon.svg");
const MAX_AGE_DAYS: i64 = 90;

struct Args {
    results: PathBuf,
    out: PathBuf,
    today: Date,
    max_age_days: i64,
    require_results: bool,
}

fn parse_args() -> Result<Args, String> {
    let mut results = None;
    let mut out = None;
    let mut today = None;
    let mut max_age_days = MAX_AGE_DAYS;
    let mut require_results = false;
    let mut args = std::env::args().skip(1);
    while let Some(arg) = args.next() {
        let mut value = |name: &str| args.next().ok_or(format!("{name} needs a value"));
        match arg.as_str() {
            "--results" => results = Some(PathBuf::from(value("--results")?)),
            "--out" => out = Some(PathBuf::from(value("--out")?)),
            "--today" => {
                let text = value("--today")?;
                today = Some(Date::parse(&text).filter(|_| text.len() == 10).ok_or("--today must be YYYY-MM-DD")?);
            }
            "--max-age-days" => {
                max_age_days = value("--max-age-days")?
                    .parse()
                    .ok()
                    .filter(|d: &i64| *d >= 0)
                    .ok_or("--max-age-days must be a whole number of days")?;
            }
            "--require-results" => require_results = true,
            other => return Err(format!("unknown argument {other}")),
        }
    }
    Ok(Args {
        results: results.ok_or("--results is required")?,
        out: out.ok_or("--out is required")?,
        today: today.unwrap_or_else(Date::today),
        max_age_days,
        require_results,
    })
}

/// A short content hash for the stylesheet URL, so that a new stylesheet is not served from a cache.
fn fnv(text: &str) -> String {
    let hash = text.bytes().fold(0xcbf2_9ce4_8422_2325_u64, |h, b| (h ^ u64::from(b)).wrapping_mul(0x0100_0000_01b3));
    format!("{:012x}", hash >> 16)
}

fn write(path: &Path, contents: &str) -> Result<(), String> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|e| format!("{}: {e}", parent.display()))?;
    }
    fs::write(path, contents).map_err(|e| format!("{}: {e}", path.display()))
}

fn run(args: &Args) -> Result<(), String> {
    let (pages, pending): (Vec<Page>, Option<String>) = match check::load(&args.results, args.today, args.max_age_days)
    {
        Ok(results) => {
            let ctx = context::Ctx::new(&results);
            (pages::render(&ctx), None)
        }
        Err(reason) => (pages::pending::pages(&reason), Some(reason)),
    };
    if let Some(reason) = &pending {
        if args.require_results {
            return Err(format!("results pending: {reason}"));
        }
        eprintln!("results pending: {reason}");
    }
    let css = format!("assets/site.css?v={}", fnv(CSS));
    write(&args.out.join("assets/site.css"), CSS)?;
    write(&args.out.join("assets/favicon.svg"), FAVICON)?;
    for page in &pages {
        write(&args.out.join(&page.path).join("index.html"), document(page, &css).as_str())?;
    }
    eprintln!("wrote {} pages to {}", pages.len(), args.out.display());
    Ok(())
}

fn main() -> ExitCode {
    match parse_args().and_then(|args| run(&args)) {
        Ok(()) => ExitCode::SUCCESS,
        Err(error) => {
            eprintln!("bench-site: {error}");
            ExitCode::FAILURE
        }
    }
}
