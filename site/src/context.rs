//! Lookups shared by the pages, built once from the checked results.

use std::collections::{BTreeMap, BTreeSet};

use crate::check::Results;
use crate::data::{Category, CategoryKey, Entry, EntryStatus, Row};
use crate::format;

pub struct Ctx<'a> {
    pub results: &'a Results,
    pub rows: BTreeMap<&'a str, &'a Row>,
    pub put_flagged: BTreeSet<&'a str>,
    pub ranked: u32,
}

impl<'a> Ctx<'a> {
    pub fn new(results: &'a Results) -> Ctx<'a> {
        let data = &results.latest;
        let rows = data.results.iter().chain(&data.not_measured).map(|r| (r.slug.as_str(), r)).collect();
        let put_flagged =
            data.labels.put_world.as_ref().map(|l| l.flagged.iter().map(String::as_str).collect()).unwrap_or_default();
        let ranked = data.rankings.categories[0].tie_rule.as_ref().and_then(|r| r.ranked).unwrap_or(0);
        Ctx { results, rows, put_flagged, ranked }
    }

    pub fn data(&self) -> &'a crate::data::Latest {
        &self.results.latest
    }

    pub fn row(&self, slug: &str) -> Option<&'a Row> {
        self.rows.get(slug).copied()
    }

    /// "Rullst (as generated)", or the name the ranking entry carries.
    pub fn name(&self, slug: &str) -> String {
        self.row(slug).map(format::label).unwrap_or_else(|| slug.to_string())
    }

    pub fn category(&self, key: CategoryKey) -> &'a Category {
        // check::load guarantees the five categories in this order.
        &self.data().rankings.categories[CategoryKey::ALL.iter().position(|k| *k == key).unwrap_or(0)]
    }

    pub fn entry(&self, key: CategoryKey, slug: &str) -> Option<&'a Entry> {
        self.category(key).entries.iter().find(|e| e.slug == slug)
    }

    pub fn put_note(&self) -> Option<&'a str> {
        let label = self.data().labels.put_world.as_ref()?;
        (!label.flagged.is_empty() && !label.note.is_empty()).then_some(label.note.as_str())
    }

    pub fn logins(&self) -> u32 {
        self.data().config.phase2.as_ref().and_then(|p| p.sessions).unwrap_or(125)
    }

    pub fn measured(&self) -> Vec<&'a Row> {
        self.data().results.iter().filter(|r| format::is_measured(r)).collect()
    }

    /// Measured rows split into the ranked implementations with the reference, and the diagnostics and the
    /// A/A control, so that tables can show the second group apart.
    pub fn measured_split(&self) -> (Vec<&'a Row>, Vec<&'a Row>) {
        self.measured().into_iter().partition(|r| r.is_baseline || r.role == crate::data::Role::Ranked)
    }

    pub fn is_rullst(&self, slug: &str) -> bool {
        self.row(slug).is_some_and(|r| r.package == "rullst" || r.name == "Rullst")
    }
}

/// Entries split for a ranking table: the reference, the ranked rows (by position) grouped into tie
/// groups, the rows of a ranked implementation without a position, and the unranked roles.
pub struct Split<'a> {
    pub reference: Option<&'a Entry>,
    pub groups: Vec<Vec<&'a Entry>>,
    pub unplaced: Vec<&'a Entry>,
    pub unranked: Vec<&'a Entry>,
}

pub fn split(entries: &[Entry]) -> Split<'_> {
    let mut out = Split { reference: None, groups: Vec::new(), unplaced: Vec::new(), unranked: Vec::new() };
    let mut placed: Vec<&Entry> = Vec::new();
    for entry in entries {
        match entry.status {
            EntryStatus::Reference => out.reference = Some(entry),
            s if s.is_unranked_role() => out.unranked.push(entry),
            _ if entry.position.is_some() => placed.push(entry),
            _ => out.unplaced.push(entry),
        }
    }
    placed.sort_by(|a, b| {
        a.position.cmp(&b.position).then(b.score.partial_cmp(&a.score).unwrap_or(std::cmp::Ordering::Equal))
    });
    for entry in placed {
        let range = entry.position_range;
        match out.groups.last_mut() {
            Some(group) if group[0].position_range == range && range.is_some_and(|[a, b]| a != b) => group.push(entry),
            _ => out.groups.push(vec![entry]),
        }
    }
    out
}
