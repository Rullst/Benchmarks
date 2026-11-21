//! Reads and checks the results files. Anything missing, of an unknown schema, inconsistent between the
//! files, out of range or older than the configured age is an error: the site then shows "results
//! pending" instead of numbers (the same rules the Rullst website applies to results/site.json).

use std::collections::{BTreeMap, BTreeSet};
use std::fs;
use std::path::Path;

use serde::de::DeserializeOwned;

use crate::data::{CategoryKey, EntryStatus, Latest, Row, Site, VersionFile, Versions};
use crate::dates::Date;

pub const LATEST_SCHEMA: &str = "rullst.benchmarks.latest.v1";
pub const SITE_SCHEMA: &str = "rullst.benchmarks.site.v2";
pub const VERSIONS_SCHEMA: &str = "rullst.benchmarks.versions.v1";
/// The flags a score can carry and their signs: the pages explain these and no others.
pub const FLAGS: [(&str, &str); 4] =
    [("cpu_cost", "*"), ("database_note", "†"), ("put_not_written", "‡"), ("within_reference_margin", "≈")];
/// The overall weights the pages describe (Hello world, Database and Application twice).
const OVERALL_WEIGHTS: [(&str, f64); 5] =
    [("hello", 2.0), ("database", 2.0), ("application", 2.0), ("memory", 1.0), ("startup", 1.0)];
const FILE_LIMIT: u64 = 16 * 1024 * 1024;

/// Everything the pages show, checked.
pub struct Results {
    pub latest: Latest,
    pub site: Site,
    pub versions: Versions,
    /// The load generator of each entry of versions.json, in its order.
    pub load_generators: Vec<String>,
}

pub fn load(dir: &Path, today: Date, max_age_days: i64) -> Result<Results, String> {
    let latest: Latest = read(dir, "latest.json")?;
    let site: Site = read(dir, "site.json")?;
    let versions: Versions = read(dir, "versions.json")?;
    check_latest(&latest, today, max_age_days).map_err(|e| format!("latest.json: {e}"))?;
    check_site(&site, &latest).map_err(|e| format!("site.json: {e}"))?;
    let load_generators = check_versions(dir, &versions, &latest).map_err(|e| format!("versions.json: {e}"))?;
    Ok(Results { latest, site, versions, load_generators })
}

fn read<T: DeserializeOwned>(dir: &Path, name: &str) -> Result<T, String> {
    let path = dir.join(name);
    let meta = fs::metadata(&path).map_err(|e| format!("{name}: cannot be read ({e})"))?;
    if !meta.is_file() || meta.len() > FILE_LIMIT {
        return Err(format!("{name}: not a regular file of at most 16 MiB"));
    }
    let text = fs::read_to_string(&path).map_err(|e| format!("{name}: cannot be read ({e})"))?;
    serde_json::from_str(&text).map_err(|e| format!("{name}: not in the expected shape ({e})"))
}

fn is_version(text: &str) -> bool {
    !text.is_empty()
        && text.len() <= 64
        && text.bytes().all(|b| b.is_ascii_alphanumeric() || matches!(b, b'.' | b'-' | b'+'))
        && text.as_bytes()[0].is_ascii_digit()
}

/// `https://github.com/<owner>/<repo>/actions/runs/<id>`.
fn is_run_url(url: &str, id: &str) -> bool {
    let Some(rest) = url.strip_prefix("https://github.com/") else { return false };
    let parts: Vec<&str> = rest.split('/').collect();
    let name_ok =
        |s: &str| !s.is_empty() && s.bytes().all(|b| b.is_ascii_alphanumeric() || matches!(b, b'-' | b'_' | b'.'));
    parts.len() == 5
        && name_ok(parts[0])
        && name_ok(parts[1])
        && parts[2] == "actions"
        && parts[3] == "runs"
        && parts[4] == id
        && !id.is_empty()
        && id.bytes().all(|b| b.is_ascii_digit())
}

fn finite_score(name: &str, value: Option<f64>) -> Result<(), String> {
    match value {
        Some(v) if !v.is_finite() || !(0.0..=1000.0).contains(&v) => Err(format!("{name}: score {v} out of range")),
        _ => Ok(()),
    }
}

fn check_latest(data: &Latest, today: Date, max_age_days: i64) -> Result<Date, String> {
    if data.schema != LATEST_SCHEMA || data.results_schema != 1 {
        return Err(format!("schema is not {LATEST_SCHEMA} (results_schema 1)"));
    }
    let measured_on = Date::parse(&data.measured_on).ok_or("measured_on is not a date")?;
    if measured_on > today {
        return Err(format!("measured_on {measured_on} is after today ({today})"));
    }
    if today.days_since(measured_on) > max_age_days {
        return Err(format!(
            "the results were measured on {measured_on}, more than {max_age_days} days before {today}"
        ));
    }
    if Date::parse(&data.generated_at).is_none() || Date::parse(&data.measured_from).is_none() {
        return Err("generated_at or measured_from is not a date".to_string());
    }
    if !is_version(&data.rullst_version) {
        return Err(format!("unexpected Rullst version {:?}", data.rullst_version));
    }
    if !is_run_url(&data.run.url, &data.run.id) {
        return Err(format!("unexpected run {:?} ({:?})", data.run.id, data.run.url));
    }
    let mut slugs = BTreeSet::new();
    for row in data.results.iter().chain(&data.not_measured) {
        if !is_slug(&row.slug) || !slugs.insert(row.slug.as_str()) {
            return Err(format!("implementation {:?} is not a unique folder name", row.slug));
        }
    }
    let rows: BTreeMap<&str, &Row> = data.results.iter().map(|r| (r.slug.as_str(), r)).collect();
    if data.rankings.reference != data.baseline || !rows.get(data.baseline.as_str()).is_some_and(|r| r.is_baseline) {
        return Err("the reference is not the measured baseline".to_string());
    }
    let keys: Vec<CategoryKey> = data.rankings.categories.iter().map(|c| c.key).collect();
    if keys != CategoryKey::ALL {
        return Err("the categories are not hello, database, application, memory and startup".to_string());
    }
    let ranked = data.rankings.categories[0].tie_rule.as_ref().and_then(|r| r.ranked).ok_or("no ranked count")?;
    for category in &data.rankings.categories {
        check_entries(&category.title, &category.entries, &slugs, ranked)?;
    }
    if data.rankings.publish_overall {
        let overall = data.rankings.overall.as_ref().ok_or("the overall ranking is published but missing")?;
        for (key, weight) in OVERALL_WEIGHTS {
            if overall.weight_ratio.get(key) != Some(&weight) || overall.weight_ratio.len() != OVERALL_WEIGHTS.len() {
                return Err("the overall weights are not 2:2:2:1:1".to_string());
            }
        }
        check_entries("overall", &overall.entries, &slugs, ranked)?;
        for weighting in &data.rankings.sensitivity {
            check_entries(&weighting.title, &weighting.entries, &slugs, ranked)?;
        }
    }
    let stability = data.rankings.stability.as_ref().ok_or("no stability check")?;
    for entry in &stability.entries {
        if !slugs.contains(entry.slug.as_str()) {
            return Err(format!("stability names an unknown implementation {:?}", entry.slug));
        }
    }
    if let Some(label) = &data.labels.put_world
        && label.flagged.iter().any(|slug| !slugs.contains(slug.as_str()))
    {
        return Err("the PUT /world/{id} label names an unknown implementation".to_string());
    }
    Ok(measured_on)
}

fn is_slug(text: &str) -> bool {
    !text.is_empty()
        && text.len() <= 64
        && text.bytes().all(|b| b.is_ascii_lowercase() || b.is_ascii_digit() || b == b'-')
}

fn check_entries(
    name: &str,
    entries: &[crate::data::Entry],
    slugs: &BTreeSet<&str>,
    ranked: u32,
) -> Result<(), String> {
    let mut seen = BTreeSet::new();
    for entry in entries {
        if !slugs.contains(entry.slug.as_str()) || !seen.insert(entry.slug.as_str()) {
            return Err(format!("{name}: unknown or repeated implementation {:?}", entry.slug));
        }
        finite_score(name, entry.score)?;
        let ranked_score = entry.status == EntryStatus::Ranked && entry.score.is_some();
        match (ranked_score, entry.position, entry.position_range) {
            (true, Some(position), Some([first, last])) => {
                if first != position || first > last || first < 1 || last > ranked {
                    return Err(format!("{name}: {} has the position range {first}–{last}", entry.slug));
                }
            }
            (true, _, _) => return Err(format!("{name}: {} is ranked without a position range", entry.slug)),
            (false, Some(_), _) => return Err(format!("{name}: {} has a position without a ranked score", entry.slug)),
            (false, None, _) => {}
        }
    }
    Ok(())
}

fn check_site(site: &Site, latest: &Latest) -> Result<(), String> {
    if site.schema != SITE_SCHEMA {
        return Err(format!("schema is not {SITE_SCHEMA}"));
    }
    if site.measured_on != latest.measured_on
        || site.generated_at != latest.generated_at
        || site.rullst_version != latest.rullst_version
        || site.run.id != latest.run.id
    {
        return Err("it does not describe the same run as latest.json".to_string());
    }
    let flags: BTreeMap<String, String> = FLAGS.iter().map(|(k, v)| (k.to_string(), v.to_string())).collect();
    if site.flags != flags {
        return Err("unknown flags".to_string());
    }
    if site.reading.en.trim().is_empty() || site.reading.pt_br.trim().is_empty() {
        return Err("the reading is empty".to_string());
    }
    Ok(())
}

fn check_versions(dir: &Path, versions: &Versions, latest: &Latest) -> Result<Vec<String>, String> {
    if versions.schema != VERSIONS_SCHEMA {
        return Err(format!("schema is not {VERSIONS_SCHEMA}"));
    }
    if versions.latest != latest.rullst_version {
        return Err("its latest version is not the version of latest.json".to_string());
    }
    let newest = versions
        .versions
        .iter()
        .find(|v| v.version == latest.rullst_version)
        .ok_or("the latest version is not listed")?;
    if newest.run_url != latest.run.url {
        return Err("the latest version lists another run".to_string());
    }
    let mut generators = Vec::new();
    for entry in &versions.versions {
        if !is_version(&entry.version) || entry.file != format!("rullst/{}.json", entry.version) {
            return Err(format!("unexpected version entry {:?}", entry.version));
        }
        if Date::parse(&entry.measured_from).is_none() || !entry.run_url.starts_with("https://github.com/") {
            return Err(format!("{}: unexpected date or run", entry.version));
        }
        let file: VersionFile = read(dir, &entry.file)?;
        if file.schema != LATEST_SCHEMA || file.rullst_version != entry.version {
            return Err(format!("{} does not hold the results of {}", entry.file, entry.version));
        }
        generators.push(match file.config.load_generator {
            Some(lg) if lg.version.is_empty() => lg.name,
            Some(lg) => format!("{} {}", lg.name, lg.version),
            None => "unknown".to_string(),
        });
    }
    Ok(generators)
}

#[cfg(test)]
mod tests {
    use super::{is_run_url, is_version};

    #[test]
    fn accepts_only_run_urls_and_versions() {
        assert!(is_run_url("https://github.com/Rullst/Benchmarks/actions/runs/44765309608", "44765309608"));
        assert!(!is_run_url("https://github.com/Rullst/Benchmarks/actions/runs/1", "2"));
        assert!(!is_run_url("javascript:alert(1)", "1"));
        assert!(!is_run_url("https://github.com/a/b/actions/runs/1/x", "1"));
        assert!(is_version("13.0.0-alpha.6"));
        assert!(!is_version("../x"));
        assert!(!is_version("v1"));
    }
}
