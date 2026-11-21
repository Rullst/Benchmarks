//! The shapes of the results files this generator reads (README, "Machine-readable results").
//!
//! Only the fields the pages show are declared; unknown fields are ignored,
//! because the files only ever gain fields. Every enumerated value (statuses,
//! roles, stability results) is a closed Rust enum, so a value the pages do
//! not know fails deserialisation and the site shows "results pending".

use std::collections::BTreeMap;

use serde::Deserialize;

pub type Map<T> = BTreeMap<String, T>;

/// `results/latest.json` and `results/rullst/<version>.json` (`rullst.benchmarks.latest.v1`).
#[derive(Debug, Deserialize)]
pub struct Latest {
    pub schema: String,
    pub results_schema: u32,
    pub measured_on: String,
    pub measured_from: String,
    #[serde(default)]
    pub measured_to: String,
    pub generated_at: String,
    pub rullst_version: String,
    #[serde(default)]
    pub rullst_source: Option<Source>,
    #[serde(default)]
    pub note: String,
    pub run: Run,
    pub baseline: String,
    pub results: Vec<Row>,
    #[serde(default)]
    pub not_measured: Vec<Row>,
    pub config: Config,
    pub environment: Environment,
    #[serde(default)]
    pub runners: Vec<RunnerCount>,
    #[serde(default)]
    pub server_cores: Option<ServerCores>,
    pub rankings: Rankings,
    #[serde(default)]
    pub publication_gate: Option<Gate>,
    #[serde(default)]
    pub labels: Labels,
}

#[derive(Debug, Deserialize)]
pub struct Source {
    pub kind: String,
    #[serde(default)]
    pub label: String,
}

#[derive(Debug, Deserialize)]
pub struct Run {
    pub id: String,
    pub url: String,
    #[serde(default)]
    pub rounds: Option<u32>,
    #[serde(default)]
    pub jobs_per_framework: Option<u32>,
    #[serde(default)]
    pub jobs: Option<u32>,
}

#[derive(Debug, Deserialize)]
pub struct RunnerCount {
    pub cpu_model: String,
    pub jobs: u32,
}

#[derive(Debug, Deserialize)]
pub struct ServerCores {
    pub jobs: u32,
    pub smt_threads_of_one_core: u32,
}

#[derive(Debug, Deserialize)]
pub struct Gate {
    pub passed: bool,
    #[serde(default)]
    pub problems: Vec<String>,
}

#[derive(Debug, Default, Deserialize)]
pub struct Labels {
    #[serde(default)]
    pub put_world: Option<PutLabel>,
}

/// PUT /world/{id} runs that did not write in most measured requests (‡).
#[derive(Debug, Deserialize)]
pub struct PutLabel {
    #[serde(default)]
    pub flagged: Vec<String>,
    #[serde(default)]
    pub note: String,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum RowStatus {
    Measured,
    Crashed,
    FailedConformance,
    BuildFailed,
    Missing,
}

#[derive(Debug, Default, Clone, Copy, PartialEq, Eq, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Role {
    #[default]
    Ranked,
    Diagnostic,
    Control,
}

/// One implementation in `results` or `not_measured`.
#[derive(Debug, Deserialize)]
pub struct Row {
    pub slug: String,
    pub name: String,
    #[serde(default)]
    pub variant: String,
    #[serde(default)]
    pub framework_version: String,
    #[serde(default)]
    pub language: String,
    #[serde(default)]
    pub group: String,
    #[serde(default)]
    pub package: String,
    #[serde(default)]
    pub versions: Map<String>,
    #[serde(default)]
    pub runtime: String,
    #[serde(default)]
    pub server: String,
    #[serde(default)]
    pub workers: String,
    #[serde(default)]
    pub database_layer: String,
    #[serde(default)]
    pub template_engine: String,
    #[serde(default)]
    pub logging: String,
    #[serde(default)]
    pub maturity_note: String,
    pub status: RowStatus,
    #[serde(default)]
    pub problem: String,
    #[serde(default)]
    pub is_baseline: bool,
    #[serde(default)]
    pub role: Role,
    #[serde(default)]
    pub role_note: String,
    #[serde(default)]
    pub structure_note: String,
    #[serde(default)]
    pub database_note: String,
    #[serde(default)]
    pub listing_note: String,
    #[serde(default)]
    pub dependency_source: Option<Source>,
    #[serde(default)]
    pub jobs: Vec<Job>,
    #[serde(default)]
    pub runners: Vec<String>,
    #[serde(default)]
    pub endpoints: Option<Vec<String>>,
    #[serde(default)]
    pub metrics: Map<Stat>,
    #[serde(default)]
    pub ratios: Map<Stat>,
    #[serde(default)]
    pub flags: Flags,
    #[serde(default)]
    pub paired_baseline: Option<Map<Option<f64>>>,
    #[serde(default)]
    pub rps_per_mib: Option<f64>,
    #[serde(default)]
    pub phase2: Option<Phase2>,
    #[serde(default)]
    pub excluded: Vec<serde_json::Value>,
}

#[derive(Debug, Deserialize)]
pub struct Job {
    pub job: u32,
    #[serde(default)]
    pub status: String,
    #[serde(default)]
    pub rounds: Option<u32>,
    #[serde(default)]
    pub cpu_model: Option<String>,
}

/// A median over rounds with its range (`metrics`, `ratios`).
#[derive(Debug, Deserialize)]
pub struct Stat {
    #[serde(default)]
    pub median: Option<f64>,
    #[serde(default)]
    pub min: Option<f64>,
    #[serde(default)]
    pub max: Option<f64>,
    #[serde(default)]
    pub n: Option<u32>,
}

#[derive(Debug, Default, Deserialize)]
pub struct Flags {
    #[serde(default)]
    pub rounds: u32,
    #[serde(default)]
    pub crashed_rounds: u32,
    #[serde(default)]
    pub ram_growing_rounds: u32,
    #[serde(default)]
    pub client_bound_rounds: Map<u32>,
    #[serde(default)]
    pub limited_rounds: Map<Map<u32>>,
    #[serde(default)]
    pub warmup_errors: Map<u64>,
}

#[derive(Debug, Deserialize)]
pub struct Phase2 {
    #[serde(default)]
    pub validation: String,
    #[serde(default)]
    pub csrf: Option<Mechanism>,
    #[serde(default)]
    pub session: Option<Mechanism>,
}

#[derive(Debug, Deserialize)]
pub struct Mechanism {
    #[serde(default)]
    pub design: String,
    #[serde(default)]
    pub store: String,
    #[serde(default)]
    pub mechanism: String,
    #[serde(default)]
    pub source: String,
}

#[derive(Debug, Deserialize)]
pub struct Config {
    #[serde(default)]
    pub server: Option<ServerConfig>,
    pub tiers: Tiers,
    #[serde(default)]
    pub endpoint_paths: Map<String>,
    #[serde(default)]
    pub phase2: Option<Phase2Config>,
    #[serde(default)]
    pub hot_rows: Option<HotRows>,
    #[serde(default)]
    pub database: Option<DatabaseConfig>,
    #[serde(default)]
    pub warmup: Option<Warmup>,
}

#[derive(Debug, Deserialize)]
pub struct ServerConfig {
    pub cpus: f64,
    #[serde(default)]
    pub memory: String,
    #[serde(default)]
    pub pool_size: Option<u32>,
}

#[derive(Debug, Deserialize)]
pub struct Tiers {
    pub tier1: Tier1,
    pub tier2: LoadTier,
    pub tier3: LoadTier,
    pub tier4: LoadTier,
}

#[derive(Debug, Deserialize)]
pub struct Tier1 {
    pub connections: u32,
    pub duration_s: f64,
    pub endpoints: Vec<String>,
}

#[derive(Debug, Deserialize)]
pub struct LoadTier {
    pub connections: u32,
    pub duration_s: f64,
    pub endpoint: String,
}

#[derive(Debug, Deserialize)]
pub struct Phase2Config {
    #[serde(default)]
    pub sessions: Option<u32>,
}

#[derive(Debug, Deserialize)]
pub struct HotRows {
    #[serde(default)]
    pub endpoint: String,
    #[serde(default)]
    pub ids: Option<u32>,
}

#[derive(Debug, Deserialize)]
pub struct DatabaseConfig {
    #[serde(default)]
    pub image: String,
    #[serde(default)]
    pub rows: Option<u32>,
    #[serde(default)]
    pub max_connections: Option<u32>,
}

#[derive(Debug, Deserialize)]
pub struct Warmup {
    #[serde(default)]
    pub duration_s: Option<f64>,
    #[serde(default)]
    pub jit_duration_s: Option<f64>,
}

#[derive(Debug, Deserialize)]
pub struct LoadGenerator {
    pub name: String,
    #[serde(default)]
    pub version: String,
}

#[derive(Debug, Deserialize)]
pub struct Environment {
    #[serde(default)]
    pub cpu_count: Option<u32>,
    #[serde(default)]
    pub memory_total_mib: Option<f64>,
    #[serde(default)]
    pub kernel: String,
    #[serde(default)]
    pub os: String,
    #[serde(default)]
    pub runner_image: String,
    #[serde(default)]
    pub docker: String,
    #[serde(default)]
    pub postgres: String,
    #[serde(default)]
    pub load_generator: Option<EnvLoadGenerator>,
}

#[derive(Debug, Deserialize)]
pub struct EnvLoadGenerator {
    pub name: String,
    #[serde(default)]
    pub version: String,
    #[serde(default)]
    pub build: String,
}

#[derive(Debug, Deserialize)]
pub struct Rankings {
    pub reference: String,
    #[serde(default)]
    pub tie_margins: Map<TieMargin>,
    #[serde(default)]
    pub method: Map<String>,
    pub categories: Vec<Category>,
    #[serde(default)]
    pub stability: Option<Stability>,
    #[serde(default)]
    pub publish_overall: bool,
    #[serde(default)]
    pub overall: Option<Overall>,
    #[serde(default)]
    pub sensitivity: Vec<Weighting>,
}

#[derive(Debug, Deserialize)]
pub struct TieMargin {
    #[serde(default)]
    pub percent: Option<f64>,
    #[serde(default)]
    pub scores: Vec<f64>,
}

#[derive(Debug, Deserialize)]
pub struct TieRule {
    #[serde(default)]
    pub aa_percent: Option<f64>,
    #[serde(default)]
    pub floor_percent: Option<f64>,
    #[serde(default)]
    pub floor_from: Option<u32>,
    #[serde(default)]
    pub ranked: Option<u32>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum CategoryKey {
    Hello,
    Database,
    Application,
    Memory,
    Startup,
}

impl CategoryKey {
    pub const ALL: [CategoryKey; 5] = [
        CategoryKey::Hello,
        CategoryKey::Database,
        CategoryKey::Application,
        CategoryKey::Memory,
        CategoryKey::Startup,
    ];

    pub fn slug(self) -> &'static str {
        match self {
            CategoryKey::Hello => "hello",
            CategoryKey::Database => "database",
            CategoryKey::Application => "application",
            CategoryKey::Memory => "memory",
            CategoryKey::Startup => "startup",
        }
    }

    pub fn is_throughput(self) -> bool {
        matches!(self, CategoryKey::Hello | CategoryKey::Database | CategoryKey::Application)
    }
}

#[derive(Debug, Deserialize)]
pub struct Category {
    pub key: CategoryKey,
    pub title: String,
    #[serde(default)]
    pub tier: String,
    #[serde(default)]
    pub description: String,
    #[serde(default)]
    pub runs: Vec<String>,
    #[serde(default)]
    pub tie_rule: Option<TieRule>,
    pub entries: Vec<Entry>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Deserialize)]
pub enum EntryStatus {
    #[serde(rename = "ranked")]
    Ranked,
    #[serde(rename = "reference")]
    Reference,
    #[serde(rename = "diagnostic")]
    Diagnostic,
    #[serde(rename = "A/A control")]
    Control,
    #[serde(rename = "incomplete")]
    Incomplete,
    #[serde(rename = "not comparable")]
    NotComparable,
    #[serde(rename = "errors")]
    Errors,
    #[serde(rename = "not measured")]
    NotMeasured,
    #[serde(rename = "unstable")]
    Unstable,
}

impl EntryStatus {
    pub fn text(self) -> &'static str {
        match self {
            EntryStatus::Ranked => "ranked",
            EntryStatus::Reference => "reference",
            EntryStatus::Diagnostic => "diagnostic",
            EntryStatus::Control => "A/A control",
            EntryStatus::Incomplete => "incomplete",
            EntryStatus::NotComparable => "not comparable",
            EntryStatus::Errors => "errors",
            EntryStatus::NotMeasured => "not measured",
            EntryStatus::Unstable => "unstable",
        }
    }

    /// Diagnostics and the A/A control: listed with a score, never with a position.
    pub fn is_unranked_role(self) -> bool {
        matches!(self, EntryStatus::Diagnostic | EntryStatus::Control)
    }
}

/// One row of a category, the overall score or a sensitivity weighting.
#[derive(Debug, Deserialize)]
pub struct Entry {
    pub slug: String,
    #[serde(default)]
    pub position: Option<u32>,
    #[serde(default)]
    pub position_range: Option<[u32; 2]>,
    #[serde(default)]
    pub position_label: Option<String>,
    pub status: EntryStatus,
    #[serde(default)]
    pub score: Option<f64>,
    #[serde(default)]
    pub within_reference_margin: Option<bool>,
    #[serde(default)]
    pub reference_margin: Option<Percent>,
    #[serde(default)]
    pub spread: Option<Spread>,
    #[serde(default)]
    pub mixed_limit_runs: Vec<String>,
    #[serde(default)]
    pub tie_check: Option<TieCheck>,
    #[serde(default)]
    pub efficiency_runs: Vec<String>,
    #[serde(default)]
    pub detail: Detail,
    #[serde(default)]
    pub error_runs: Map<f64>,
    #[serde(default)]
    pub reason: String,
    #[serde(default)]
    pub database_note: String,
    #[serde(default)]
    pub stability: Option<String>,
}

#[derive(Debug, Deserialize)]
pub struct Percent {
    #[serde(default)]
    pub percent: Option<f64>,
}

#[derive(Debug, Deserialize)]
pub struct Spread {
    #[serde(default)]
    pub scores: Vec<f64>,
    #[serde(default)]
    pub cpu_models: Vec<String>,
    #[serde(default)]
    pub own_percent: Option<f64>,
    #[serde(default)]
    pub effective_percent: Option<f64>,
    #[serde(default)]
    pub basis: String,
}

#[derive(Debug, Deserialize)]
pub struct TieCheck {
    pub against: String,
    #[serde(default)]
    pub percent: Option<f64>,
    #[serde(default)]
    pub gap_percent: Option<f64>,
    pub tied: bool,
}

/// `detail` of an entry: throughput, memory, startup and stability fields together.
#[derive(Debug, Default, Deserialize)]
pub struct Detail {
    #[serde(default)]
    pub capacity: Map<Option<f64>>,
    #[serde(default)]
    pub rps_ratio: Map<Option<f64>>,
    #[serde(default)]
    pub basis: Map<String>,
    #[serde(default)]
    pub error_rates: Map<Option<f64>>,
    #[serde(default)]
    pub db_us_per_request: Map<Option<f64>>,
    #[serde(default)]
    pub db_us_ratio: Map<Option<f64>>,
    #[serde(default)]
    pub csrf: Option<String>,
    #[serde(default)]
    pub session_store: Option<String>,
    #[serde(default)]
    pub value: Option<f64>,
    #[serde(default)]
    pub reference: Option<f64>,
    #[serde(default)]
    pub tier2: Option<StabilityTier>,
    #[serde(default)]
    pub tier4: Option<StabilityTier>,
}

#[derive(Debug, Deserialize)]
pub struct StabilityTier {
    #[serde(default)]
    pub rps: Option<f64>,
    #[serde(default)]
    pub p99_ms: Option<f64>,
    #[serde(default)]
    pub error_rate_max: Option<f64>,
    #[serde(default)]
    pub timeouts: Option<f64>,
}

#[derive(Debug, Deserialize)]
pub struct Stability {
    pub title: String,
    #[serde(default)]
    pub tier: String,
    #[serde(default)]
    pub description: String,
    pub entries: Vec<StabilityEntry>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum StabilityResult {
    Pass,
    Warn,
    Fail,
}

impl StabilityResult {
    pub fn text(self) -> &'static str {
        match self {
            StabilityResult::Pass => "pass",
            StabilityResult::Warn => "warn",
            StabilityResult::Fail => "fail",
        }
    }
}

#[derive(Debug, Deserialize)]
pub struct StabilityEntry {
    pub slug: String,
    pub status: EntryStatus,
    #[serde(default)]
    pub result: Option<StabilityResult>,
    #[serde(default)]
    pub reasons: Vec<String>,
    #[serde(default)]
    pub detail: Detail,
}

#[derive(Debug, Deserialize)]
pub struct Overall {
    #[serde(default)]
    pub weight_ratio: BTreeMap<String, f64>,
    pub entries: Vec<Entry>,
}

#[derive(Debug, Deserialize)]
pub struct Weighting {
    pub title: String,
    #[serde(default)]
    pub weights: BTreeMap<String, f64>,
    pub entries: Vec<Entry>,
}

/// `results/site.json` (`rullst.benchmarks.site.v2`): the fields cross-checked against latest.json and the
/// Brazilian Portuguese reading.
#[derive(Debug, Deserialize)]
pub struct Site {
    pub schema: String,
    pub measured_on: String,
    pub generated_at: String,
    pub rullst_version: String,
    pub run: SiteRun,
    pub flags: BTreeMap<String, String>,
    pub reading: Reading,
}

#[derive(Debug, Deserialize)]
pub struct SiteRun {
    pub id: String,
}

#[derive(Debug, Deserialize)]
pub struct Reading {
    pub en: String,
    pub pt_br: String,
}

/// `results/versions.json` (`rullst.benchmarks.versions.v1`).
#[derive(Debug, Deserialize)]
pub struct Versions {
    pub schema: String,
    pub latest: String,
    pub versions: Vec<VersionEntry>,
}

#[derive(Debug, Deserialize)]
pub struct VersionEntry {
    pub version: String,
    pub measured_from: String,
    pub run_url: String,
    pub file: String,
    #[serde(default)]
    pub note: String,
    #[serde(default)]
    pub implementations: Map<VersionImplementation>,
}

#[derive(Debug, Deserialize)]
pub struct VersionImplementation {
    pub status: RowStatus,
    #[serde(default)]
    pub ratios: Map<Option<f64>>,
}

/// The part of a per-version file the history page shows: how it was measured.
#[derive(Debug, Deserialize)]
pub struct VersionFile {
    pub schema: String,
    pub rullst_version: String,
    pub config: VersionConfig,
}

#[derive(Debug, Deserialize)]
pub struct VersionConfig {
    #[serde(default)]
    pub load_generator: Option<LoadGenerator>,
}
