//! Number formatting and lookups, written as bench/report.py writes them so that the pages and the
//! Markdown results print the same values.

use crate::data::{Config, Entry, EntryStatus, Role, Row, RowStatus};

pub const DASH: &str = "–";

/// `1,234.5` with `digits` decimals, or "–".
pub fn num(value: Option<f64>, digits: usize) -> String {
    let Some(value) = value else { return DASH.to_string() };
    let text = format!("{:.*}", digits, value.abs());
    let (int, frac) = match text.split_once('.') {
        Some((int, frac)) => (int, Some(frac)),
        None => (text.as_str(), None),
    };
    let mut grouped = String::with_capacity(int.len() + int.len() / 3);
    for (i, ch) in int.chars().enumerate() {
        if i > 0 && (int.len() - i) % 3 == 0 {
            grouped.push(',');
        }
        grouped.push(ch);
    }
    let sign = if value < 0.0 && text.bytes().any(|b| b.is_ascii_digit() && b != b'0') { "-" } else { "" };
    match frac {
        Some(frac) => format!("{sign}{grouped}.{frac}"),
        None => format!("{sign}{grouped}"),
    }
}

/// A score or ratio: two decimals, three below 0.1 so that small ratios still differ.
pub fn times(value: f64) -> String {
    if value >= 0.1 { format!("{value:.2}") } else { format!("{value:.3}") }
}

pub fn times_or_dash(value: Option<f64>) -> String {
    value.map(times).unwrap_or_else(|| DASH.to_string())
}

/// `±5.5%`, or "–".
pub fn pct(value: Option<f64>) -> String {
    value.map(|v| format!("±{v:.1}%")).unwrap_or_else(|| DASH.to_string())
}

/// An error rate (a fraction) as `0` or `1.23%`.
pub fn error_rate(value: Option<f64>) -> String {
    match value {
        None => DASH.to_string(),
        Some(0.0) => "0".to_string(),
        Some(v) => format!("{:.2}%", v * 100.0),
    }
}

const SHORT_CPU: [(&str, &str); 6] = [
    ("AMD EPYC ", "EPYC "),
    (" 64-Core Processor", ""),
    (" 80-Core Processor", ""),
    (" 96-Core Processor", ""),
    ("Intel(R) Xeon(R) ", "Xeon "),
    ("INTEL(R) XEON(R) ", "Xeon "),
];

pub fn short_cpu(model: &str) -> String {
    let mut text = if model.is_empty() { "unknown".to_string() } else { model.to_string() };
    for (old, new) in SHORT_CPU {
        text = text.replace(old, new);
    }
    text.trim().to_string()
}

/// The CPU model of each job a row was measured on; counted when there are more than three.
pub fn runners(row: &Row) -> String {
    if row.runners.len() > 3 {
        let mut counts: Vec<(String, usize)> = Vec::new();
        for model in &row.runners {
            let short = short_cpu(model);
            match counts.iter_mut().find(|(m, _)| *m == short) {
                Some((_, n)) => *n += 1,
                None => counts.push((short, 1)),
            }
        }
        counts.sort_by(|a, b| b.1.cmp(&a.1).then_with(|| a.0.cmp(&b.0)));
        return counts.iter().map(|(m, n)| format!("{m} ×{n}")).collect::<Vec<_>>().join(", ");
    }
    let text = row.runners.iter().map(|m| short_cpu(m)).collect::<Vec<_>>().join(", ");
    if text.is_empty() { DASH.to_string() } else { text }
}

/// "Rullst (as generated)": the name with its variant.
pub fn label(row: &Row) -> String {
    if row.variant.is_empty() { row.name.clone() } else { format!("{} ({})", row.name, row.variant) }
}

/// Whether `version` is a Rullst release before 13.0.0-rc.1, whose ORM pool still pinged every
/// PostgreSQL connection it handed out.
pub fn rullst_pings_every_connection(version: &str) -> bool {
    let major = version.split('.').next().and_then(|m| m.parse::<u64>().ok());
    version.starts_with("13.0.0-alpha.") || major.is_some_and(|m| m < 13)
}

/// A correction to a role note stored with the results: until the 13.0.0-rc.1 run, the
/// `axum-no-ping` note said that it bounds the ping of every other SQLx implementation, which stopped
/// being true for Rullst in 13.0.0-rc.1.
pub fn role_note_correction(row: &Row, rullst_version: &str) -> Option<&'static str> {
    (row.role_note.contains("every other SQLx implementation") && !rullst_pings_every_connection(rullst_version))
        .then_some(
            "Since Rullst 13.0.0-rc.1, the other SQLx implementations that keep this ping are Actix Web and Loco: \
             both Rullst folders ping only connections idle for at least 500 ms.",
        )
}

/// What a row is when it is not a ranked implementation.
pub fn role_text(row: &Row) -> Option<&'static str> {
    if row.is_baseline {
        Some("reference")
    } else {
        match row.role {
            Role::Ranked => None,
            Role::Diagnostic => Some("diagnostic, unranked"),
            Role::Control => Some("A/A control, unranked"),
        }
    }
}

pub fn is_measured(row: &Row) -> bool {
    matches!(row.status, RowStatus::Measured | RowStatus::Crashed)
}

pub fn status_text(row: &Row) -> &'static str {
    match row.status {
        RowStatus::Measured => "measured",
        RowStatus::Crashed => "crashed",
        RowStatus::FailedConformance => "failed conformance",
        RowStatus::BuildFailed => "build failed",
        RowStatus::Missing => "missing",
    }
}

/// Phase-2 endpoints as the results name them (bench/common.py ENDPOINT_LABELS).
pub fn endpoint_label(config: &Config, endpoint: &str) -> String {
    match endpoint {
        "world" => "GET /world/{id}".to_string(),
        "worlds" => "GET /worlds".to_string(),
        "world-update" => "PUT /world/{id}".to_string(),
        "form" => "POST /form".to_string(),
        "me" => "GET /me".to_string(),
        _ => config.endpoint_paths.get(endpoint).cloned().unwrap_or_else(|| format!("/{endpoint}")),
    }
}

/// The endpoints that touch PostgreSQL, whose PostgreSQL CPU per request is shown.
pub const DB_ENDPOINTS: [&str; 8] =
    ["db-single", "queries", "updates", "fortunes", "world", "worlds", "world-update", "me"];

pub fn serves(row: &Row, endpoint: &str) -> bool {
    row.endpoints.as_ref().is_none_or(|eps| eps.iter().any(|e| e == endpoint))
}

pub fn median(row: &Row, path: &str) -> Option<f64> {
    row.metrics.get(path).and_then(|s| s.median)
}

/// A median with its lowest and highest round: `59,870 (56,925–74,844)`.
pub fn range(row: &Row, path: &str, digits: usize) -> String {
    let Some(stat) = row.metrics.get(path) else { return DASH.to_string() };
    let mut text = num(stat.median, digits);
    if stat.n.unwrap_or(0) > 1 && stat.min.is_some() && stat.max.is_some() {
        text += &format!(" ({}–{})", num(stat.min, digits), num(stat.max, digits));
    }
    text
}

/// The median ratio to Axum on the same runners; Axum's own is 1.00.
pub fn ratio(row: &Row, path: &str) -> String {
    if row.is_baseline {
        return if row.metrics.contains_key(path) { "1.00".to_string() } else { DASH.to_string() };
    }
    row.ratios.get(path).and_then(|s| s.median).map(|v| format!("{v:.2}")).unwrap_or_else(|| DASH.to_string())
}

/// An absolute median with, in brackets, Axum's from the same runners.
pub fn paired(row: &Row, path: &str, digits: usize) -> String {
    let text = num(median(row, path), digits);
    let base = row.paired_baseline.as_ref().and_then(|p| p.get(path).copied().flatten());
    match base {
        Some(base) if text != DASH && !row.is_baseline => format!("{text} ({})", num(Some(base), digits)),
        _ => text,
    }
}

/// What limited a run in how many rounds: PostgreSQL or the load generator.
pub fn bound(row: &Row, run: &str) -> String {
    let rounds = row.flags.rounds;
    match row.flags.limited_rounds.get(run) {
        Some(limited) => limited
            .iter()
            .filter(|(_, n)| **n > 0)
            .map(|(name, n)| format!("{} {n}/{rounds}", limit_name(name)))
            .collect::<Vec<_>>()
            .join(", "),
        None => match row.flags.client_bound_rounds.get(run) {
            Some(n) if *n > 0 => format!("client-bound {n}/{rounds}"),
            _ => String::new(),
        },
    }
}

pub fn limit_name(name: &str) -> String {
    match name {
        "postgresql" => "PostgreSQL-bound".to_string(),
        "load-generator" => "load-generator-bound".to_string(),
        other => other.to_string(),
    }
}

/// The CSRF design or session store with the mechanism's source: `token (built-in)`.
pub fn mechanism(row: &Row, csrf: bool) -> String {
    let Some(phase2) = &row.phase2 else { return DASH.to_string() };
    let value = if csrf { phase2.csrf.as_ref() } else { phase2.session.as_ref() };
    match value {
        Some(m) => {
            let main = if csrf { &m.design } else { &m.store };
            if main.is_empty() { DASH.to_string() } else { format!("{main} ({})", m.source) }
        }
        None => DASH.to_string(),
    }
}

/// The position column: a range for a tie group, or the role of an unranked row.
pub fn position_text(entry: &Entry) -> String {
    match entry.status {
        EntryStatus::Reference => "ref.".to_string(),
        EntryStatus::Diagnostic => "diag.".to_string(),
        EntryStatus::Control => "A/A".to_string(),
        _ => match (&entry.position_label, entry.position) {
            (Some(label), _) => label.clone(),
            (None, Some(p)) => p.to_string(),
            (None, None) => entry.status.text().to_string(),
        },
    }
}

/// "positions 3–6" or "position 1".
pub fn position_words(entry: &Entry) -> Option<String> {
    let [first, last] = entry.position_range.or(entry.position.map(|p| [p, p]))?;
    Some(if first == last { format!("position {first}") } else { format!("positions {first}–{last}") })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn rullst_pinged_every_connection_before_rc1() {
        for version in ["13.0.0-alpha.6", "13.0.0-alpha.1", "12.3.0"] {
            assert!(rullst_pings_every_connection(version), "{version}");
        }
        for version in ["13.0.0-rc.1", "13.0.0", "13.1.0"] {
            assert!(!rullst_pings_every_connection(version), "{version}");
        }
    }

    #[test]
    fn formats_like_the_markdown_results() {
        assert_eq!(num(Some(126538.4), 0), "126,538");
        assert_eq!(num(Some(1045.26), 1), "1,045.3");
        assert_eq!(num(Some(999.0), 0), "999");
        assert_eq!(num(Some(-12.34), 1), "-12.3");
        assert_eq!(num(None, 1), DASH);
        assert_eq!(times(0.497), "0.50");
        assert_eq!(times(0.0047), "0.005");
        assert_eq!(pct(Some(5.48)), "±5.5%");
        assert_eq!(error_rate(Some(0.0)), "0");
        assert_eq!(error_rate(Some(0.0123)), "1.23%");
        assert_eq!(short_cpu("AMD EPYC 7763 64-Core Processor"), "EPYC 7763");
        assert_eq!(short_cpu("INTEL(R) XEON(R) PLATINUM 8573C"), "Xeon PLATINUM 8573C");
    }
}
