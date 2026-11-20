"""Markdown rendering of the combined results (benchmarks_results.md and README table)."""

from __future__ import annotations

from common import ENDPOINT_LABELS, GROUPS, PHASE2_ENDPOINTS, endpoint_label

START = "<!-- results:start -->"
END = "<!-- results:end -->"
HISTORY = "history/2026-06-22-laptop.md"
MEASURED = ("measured", "crashed")


def _stat(row: dict, path: str, kind: str = "metrics") -> dict | None:
    return row.get(kind, {}).get(path)


def _num(value, digits: int = 0) -> str:
    if value is None:
        return "–"
    return f"{value:,.{digits}f}"


def _median(row: dict, path: str, digits: int = 0, kind: str = "metrics") -> str:
    stat = _stat(row, path, kind)
    return _num(stat["median"], digits) if stat and stat.get("median") is not None else "–"


def _range(row: dict, path: str, digits: int = 0) -> str:
    stat = _stat(row, path)
    if not stat:
        return "–"
    text = _num(stat["median"], digits)
    if stat["n"] > 1:
        text += f" ({_num(stat['min'], digits)}–{_num(stat['max'], digits)})"
    return text


def _ratio(row: dict, path: str) -> str:
    if row.get("is_baseline"):
        return "1.00" if _stat(row, path) else "–"
    stat = _stat(row, path, "ratios")
    return f"{stat['median']:.2f}" if stat and stat.get("median") is not None else "–"


ROLE_LABELS = {"diagnostic": "diagnostic, unranked", "control": "A/A control, unranked"}


def _label(row: dict) -> str:
    label = row["name"]
    if row.get("variant"):
        label += f" ({row['variant']})"
    if row.get("is_baseline"):
        label += " – baseline"
    elif row.get("role") in ROLE_LABELS:
        label += f" – {ROLE_LABELS[row['role']]}"
    return label


SHORT_CPU = (("AMD EPYC ", "EPYC "), (" 64-Core Processor", ""), (" 80-Core Processor", ""),
             (" 96-Core Processor", ""), ("Intel(R) Xeon(R) ", "Xeon "), ("INTEL(R) XEON(R) ", "Xeon "))


def short_cpu(model: str | None) -> str:
    text = model or "unknown"
    for old, new in SHORT_CPU:
        text = text.replace(old, new)
    return text.strip()


def _runners(row: dict) -> str:
    """The CPU model of each job the row's numbers come from (A, B: two runners)."""
    models = row.get("runners") or ([row["environment"]["cpu_model"]] if row.get("environment") else [])
    if len(models) > 3:
        counts: dict[str, int] = {}
        for model in models:
            counts[short_cpu(model)] = counts.get(short_cpu(model), 0) + 1
        return ", ".join(f"{m} ×{n}" for m, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))
    return ", ".join(short_cpu(m) for m in models) or "–"


LIMIT_NAMES = {"postgresql": "PostgreSQL-bound", "load-generator": "load-generator-bound"}


def _bound(row: dict, run: str) -> str:
    """What limited a run, in how many rounds: PostgreSQL or the load generator (the client vCPUs)."""
    flags = row.get("flags", {})
    rounds = flags.get("rounds", 0)
    limited = flags.get("limited_rounds", {}).get(run)
    if limited is None:
        count = flags.get("client_bound_rounds", {}).get(run, 0)
        return f"client-bound {count}/{rounds}" if count else ""
    return ", ".join(f"{LIMIT_NAMES[name]} {count}/{rounds}" for name, count in limited.items() if count)


def _flags(row: dict) -> str:
    flags = row.get("flags", {})
    notes = []
    if flags.get("crashed_rounds"):
        notes.append(f"stopped in {flags['crashed_rounds']}/{flags['rounds']} rounds")
    if flags.get("ram_growing_rounds"):
        notes.append(f"RAM still growing in Tier 4 ({flags['ram_growing_rounds']}/{flags['rounds']})")
    if row.get("maturity_note"):
        notes.append(row["maturity_note"])
    return "; ".join(notes)


def _measured(rows: list[dict]) -> list[dict]:
    return [r for r in rows if r["status"] in MEASURED]


TEXT_COLUMNS = {"Implementation", "Version", "Language", "Notes", "Status", "Reason", "Group", "Runtime",
                "Server", "Workers", "Database layer", "Templates", "Overall", "Hello world", "Database",
                "Application", "Memory (high-water mark)", "Startup", "Stability", "CSRF", "Session store",
                "Validation", "Runner CPUs", "Position", "Result", "Limits", "Structure", "Check", "Weighting",
                "Warm-up errors", "Category", "A/A scores", "Job scores", "Spread", "Position check",
                "vs Axum margin"}
# Tier 1 endpoints in the summary table, as ratios to Axum.
SUMMARY_ENDPOINTS = ("json", "html", "db-single", "queries", "updates", "fortunes")
DB_ENDPOINTS = ("db-single", "queries", "updates", "fortunes", "world", "worlds", "world-update", "me")


def _table(header: list[str], lines: list[list[str]]) -> str:
    align = ["---" if name in TEXT_COLUMNS else "---:" for name in header]
    out = ["| " + " | ".join(header) + " |", "| " + " | ".join(align) + " |"]
    out += ["| " + " | ".join(cells) + " |" for cells in lines]
    return "\n".join(out)


def _errors(row: dict, path: str) -> str:
    stat = _stat(row, path)
    if not stat:
        return "–"
    return f"{stat['median'] * 100:.2f}%" if stat["median"] else "0"


def _plural(count, word: str) -> str:
    return f"{count} {word}" + ("" if count == 1 else "s")


def _source_text(data: dict) -> str:
    source = data.get("rullst_source") or {}
    if source.get("kind") == "git":
        return f" (built from {source['label']}, a git revision, not the crates.io release)"
    if source.get("kind") == "crates.io":
        return " (from crates.io)"
    return ""


def notice(data: dict) -> str:
    """The context every results surface shows above the numbers."""
    run = data.get("run", {})
    measured = (data.get("measured_from") or data["generated_at"])[:10]
    runners = data.get("runners") or ([{"cpu_model": data.get("environment", {}).get("cpu_model"), "jobs": 1}]
                                      if data.get("environment") else [])
    cpus = ", ".join(f"{short_cpu(r['cpu_model'])} ×{r['jobs']}" for r in runners) or "CPU unknown"
    env = data.get("environment", {})
    jobs = run.get("jobs_per_framework") or 1
    rounds = run.get("rounds")
    return (f"> Measured on {measured} with **Rullst {data.get('rullst_version') or 'unknown'}**{_source_text(data)} "
            f"on GitHub-hosted runners ({env.get('cpu_count')} vCPUs; each server limited to 2 vCPUs and 2 GiB). "
            f"Each implementation ran {_plural(rounds, 'round')} on each of {_plural(jobs, 'runner')} (jobs), "
            "alternating which side goes first with the Axum baseline measured on the same runner (ABBA); values "
            "are medians over every round pair. Runner CPUs per job: "
            f"{cpus}; each row names its own. Ratios to Axum (1.00 = Axum) cancel most of the difference between "
            "runners, so the tables lead with them. These results update automatically when a new Rullst version "
            f"is published on crates.io. Last update: {data['generated_at'][:10]}."
            + (f"\n>\n> **Note:** {data['note']}" if data.get("note") else ""))


def _paired(row: dict, path: str) -> str:
    """An absolute median with, in brackets, the baseline's median from the same runners."""
    text = _median(row, path)
    base = (row.get("paired_baseline") or {}).get(path)
    if text != "–" and base is not None and not row.get("is_baseline"):
        text += f" ({_num(base)})"
    return text


def _served(row: dict, endpoint: str) -> bool:
    return endpoint in row.get("endpoints", (endpoint,))


def _phase2_label(row: dict, kind: str) -> str:
    """The CSRF design or session store a folder declares, with the mechanism's source."""
    value = (row.get("phase2") or {}).get(kind) or {}
    main = value.get("design" if kind == "csrf" else "store")
    return f"{main} ({value.get('source')})" if main else "–"


def _endpoint_notes(row: dict, endpoint: str, run: str) -> str:
    if not _served(row, endpoint):
        return "not implemented yet"
    notes = [n for n in (_bound(row, run),) if n]
    if endpoint in DB_ENDPOINTS and row.get("database_note"):
        notes.insert(0, f"**{row['database_note']}**")
    warm = row.get("flags", {}).get("warmup_errors", {}).get(endpoint)
    if warm:
        notes.append(f"{warm} warm-up errors")
    if endpoint == "form":
        notes.append(f"CSRF: {_phase2_label(row, 'csrf')}")
    if endpoint == "me":
        notes.append(f"session: {_phase2_label(row, 'session')}")
    return "; ".join(notes)


def summary_table(rows: list[dict]) -> str:
    header = ["Implementation", "Version", "Language", *(f"/{ep} vs Axum" for ep in SUMMARY_ENDPOINTS),
              "/json req/s (Axum)", "Idle RAM (MiB)", "Peak RAM (MiB)", "Runner CPUs"]
    lines = []
    for row in _measured(rows):
        lines.append([
            _label(row), row["framework_version"], row["language"],
            *(_ratio(row, f"tier1.{ep}.rps") if _served(row, ep) else "n/i" for ep in SUMMARY_ENDPOINTS),
            _paired(row, "tier1.json.rps"),
            _median(row, "tier3.idle_ram_mib", 1), _median(row, "tier3.load_ram_peak_mib", 1), _runners(row),
        ])
    return _table(header, lines)


SUMMARY_NOTE = ("Ratios are requests/s divided by Axum's on the same runners (higher is better); the scores in the "
                "rankings use capacity ratios instead (see below). \"/json req/s (Axum)\" is the absolute number, "
                "with Axum's on the same runners in brackets: compare absolute numbers only within a row. Peak RAM "
                "is the Memory category's high-water mark. \"n/i\": not implemented yet. /queries and /updates use "
                "queries=20. Runner CPUs: the CPU model of each job (runner) the row was measured on.")


def _rank_text(entry: dict) -> str:
    if entry["status"] == "reference":
        return "reference"
    if entry["status"] == "diagnostic":
        return "diagnostic"
    if entry["status"] == "A/A control":
        return "A/A"
    if entry["position"] is None:
        return entry["status"]
    return f"{entry['position']}" + (" (tie)" if entry["tie"] else "")


def _times(value: float) -> str:
    """Two decimals, three below 0.1 so that small ratios still differ."""
    return f"{value:.2f}" if value >= 0.1 else f"{value:.3f}"


THROUGHPUT = ("hello", "database", "application")


def _category_cell(key: str, entry: dict) -> str:
    """Position and score (a ratio to Axum, higher is better); "*": a CPU-efficiency basis; "≈": within the A/A
    margin of Axum."""
    if entry["score"] is None and entry["status"] == "errors":
        rates = ", ".join(f"{ENDPOINT_LABELS.get(ep, '/' + ep)} {rate:.1%}"
                          for ep, rate in entry.get("error_runs", {}).items())
        return f"errors ({rates})"
    if entry["score"] is None:
        return entry["status"]
    value = f"{_times(entry['score'])}×"
    if key in THROUGHPUT and entry.get("efficiency_runs"):
        value += "*"
    if entry.get("database_note"):
        value += " †"
    if entry.get("within_reference_margin"):
        value += " ≈"
    if key == "startup" and entry["detail"].get("startup_s") is not None:
        value += f" ({entry['detail']['startup_s']:.2f} s)"
    if key == "memory" and entry["detail"].get("peak_ram_mib") is not None:
        value += f" ({entry['detail']['peak_ram_mib']:.0f} MiB)"
    return f"{_rank_text(entry)}: {value}{_check_suffix(entry)}"


def _pct(percent: float | None) -> str:
    return "–" if percent is None else f"±{percent:.1f}%"


def _check_suffix(entry: dict) -> str:
    """The margin of the check that set a ranked entry's position (none for the first position)."""
    check = entry.get("tie_check") or {}
    return f" {_pct(check['percent'])}" if check.get("percent") is not None else ""


def _overall_cell(entry: dict) -> str:
    if entry["score"] is None:
        return entry["status"]
    return f"{_rank_text(entry)}: {_times(entry['score'])}{_check_suffix(entry)}"


def _stability_cell(entry: dict | None) -> str:
    if not entry:
        return "–"
    result = entry["result"]
    return result + (f" ({'; '.join(entry['reasons'])})" if entry["reasons"] and result != "pass" else "")


TIE_RULE = ("Tie margins: each implementation has one score per job (runner) in each category; its between-job "
            "spread is the half-range of their logarithms. Two scores tie when their gap is at most the largest of "
            "(a) the A/A margin (the largest deviation from 1.00 of the A/A control, an identical copy of Axum, "
            "per job and pooled), (b) the root of the sum of squares of their two spreads and (c) the pooled "
            "floor (the median spread of the ranked implementations measured on at least two jobs). An "
            "implementation whose jobs all ran on one CPU model counts with at least the floor as its spread, one "
            "measured on a single job with the floor. A score is compared with the best score of the group above "
            "it, counting with the widest spread of that group's other members when it is wider than its own, so "
            "that equal scores share a position. \"±\" after a score: the margin of that comparison (the first "
            "position has none).")


def _rule_text(rule: dict | None, margin: dict | None = None) -> str:
    """A category's A/A margin and pooled floor, for example "A/A ±0.3%, floor ±8.2% (14 implementations)"."""
    rule = rule or {}
    aa = rule.get("aa_percent", (margin or {}).get("percent"))
    text = f"A/A {_pct(aa)}" if aa is not None else "no A/A data"
    if rule.get("floor") is None:
        return text + ", no floor (no implementation measured on two jobs)"
    return text + f", floor {_pct(rule.get('floor_percent'))} ({_plural(rule.get('floor_from'), 'implementation')})"


def _margins_line(rankings: dict) -> str:
    margins = rankings.get("tie_margins") or {}
    parts = [f"{c['title']}: {_rule_text(c.get('tie_rule'), margins.get(c['key']))}" for c in rankings["categories"]]
    return TIE_RULE + " A/A margin and pooled floor per category: " + "; ".join(parts) + "."


POOL_NOTE = ("**Connection-pool defaults.** The Database and Application rankings partly measure connection-pool "
             "defaults. SQLx, used by the Axum, Actix Web, Loco and Rullst implementations, tests each connection "
             "with a round trip before handing it out (`test_before_acquire`, on by default). The unranked "
             "`axum-no-ping` diagnostic shows the size of that cost: {measured}. Every implementation runs its "
             "framework's documented defaults.")


def pool_note(data: dict) -> str:
    """The connection-pool note, with the no-ping diagnostic's scores from these results."""
    scores = {}
    for category in (data.get("rankings") or {}).get("categories", []):
        entry = next((e for e in category["entries"] if e["slug"] == "axum-no-ping"), None)
        if category["key"] in ("database", "application") and entry and entry.get("score"):
            scores[category["key"]] = entry["score"]
    if len(scores) == 2:
        measured = (f"in these results Axum scored {scores['database']:.2f} in Database and "
                    f"{scores['application']:.2f} in Application with it switched off")
    else:
        measured = "it has no Database and Application scores in these results"
    return POOL_NOTE.format(measured=measured)


def rankings_section(data: dict, level: str = "###", review: bool = False) -> list[str]:
    """The per-category positions (and the overall ranking when it is published or for review)."""
    rankings = data.get("rankings")
    if not rankings:
        return []
    show_overall = bool(rankings.get("overall")) and (rankings.get("publish_overall") or review)
    tiers = data.get("config", {}).get("tiers", {})
    t1, t2, t3, t4 = (tiers.get(k, {}) for k in ("tier1", "tier2", "tier3", "tier4"))
    labels = {r["slug"]: _label(r) for r in data["implementations"]}
    by_slug = {r["slug"]: r for r in data["implementations"]}
    cells = {c["key"]: {e["slug"]: e for e in c["entries"]} for c in rankings["categories"]}
    stability = {e["slug"]: e for e in rankings.get("stability", {}).get("entries", [])}
    keys = [c["key"] for c in rankings["categories"]]
    titles = [c["title"] for c in rankings["categories"]]
    header = ["Implementation", *(["Overall"] if show_overall else []), *titles, "Stability", "Runner CPUs"]
    # Without a published overall ranking, rows keep the neutral order of the
    # implementations (reference, groups, names), so that no overall order is implied.
    if show_overall:
        order = rankings["overall"]["entries"]
    else:
        first = {e["slug"]: e for e in rankings["categories"][0]["entries"]}
        order = [first[r["slug"]] for r in data["implementations"] if r["slug"] in first]
    lines = []
    for entry in order:
        slug = entry["slug"]
        lines.append([labels.get(slug, entry["framework"]), *([_overall_cell(entry)] if show_overall else []),
                      *(_category_cell(key, cells[key][slug]) for key in keys),
                      _stability_cell(stability.get(slug)), _runners(by_slug.get(slug, {}))])
    noted = [(labels.get(e["slug"], e["framework"]), e["database_note"])
             for e in cells.get("database", {}).values() if e.get("database_note")]
    out = [
        f"{level} Rankings", "",
        f"- **Hello world (Tier 1):** /text, /json and /html with {t1.get('connections')} connections for "
        f"{t1.get('duration_s')} s each; the score is the geometric mean of the three capacity ratios to Axum.",
        f"- **Database (Tier 1):** /db-single, /queries and /updates (20 random rows per request) and /fortunes, "
        f"with the same {t1.get('connections')} connections; the geometric mean of the four capacity ratios.",
        "- **Application (Tier 1):** GET /world/{id}, GET /worlds, PUT /world/{id}, POST /form (CSRF verified) and "
        "GET /me (a signed-in session); the geometric mean of the five capacity ratios. /form and /me compare "
        "each framework's own default CSRF design and session store (cookie or PostgreSQL), not one mechanism.",
        f"- **Memory (Tier 3):** the RAM high-water mark while answering /{t3.get('endpoint')} with "
        f"{t3.get('connections')} connections for {t3.get('duration_s')} s, measured after the phase-1 Tier 1 "
        "runs, Tiers 2 and 4 and an idle period, so it includes memory the server kept from that load; the score "
        "is Axum's high-water mark / the implementation's, both counted as at least 64 MiB.",
        "- **Startup:** time from starting the container to its first answer; the score is Axum's time / the "
        "implementation's, both counted as at least 1 s.",
        f"- **Stability (Tiers 2 and 4, not a score):** /{t2.get('endpoint')} with {t2.get('connections')} "
        f"connections for {t2.get('duration_s')} s and {t4.get('connections')} connections for "
        f"{_num((t4.get('duration_s') or 0) / 60)} minutes: fail when the server stopped or a round had more "
        "than 1% errors (timeouts included); warn when RAM was still growing at the end of Tier 4 (for a "
        "garbage-collected runtime that can be heap growth rather than a leak).",
        "",
        "Every score is an efficiency-aware ratio to Axum (1.00), higher is better. In the throughput categories "
        "each run counts with its requests/s ratio when neither server was client-bound, and otherwise with the "
        "ratio of requests per CPU-second of the server and PostgreSQL together (\"*\"), so a framework is "
        "charged for the PostgreSQL work its queries cause. A run limited by the load generator while a server "
        "used less than 75% of its vCPUs is not comparable. A run with more than 1% errors has no score "
        "(\"errors\"). \"≈\": within the tie margin of Axum's 1.00 (the largest of the A/A margin, the score's "
        "own spread and the pooled floor), so not distinguishable from Axum. \"(tie)\": within the tie margin of "
        "the best score of its group. Axum, diagnostics and the A/A control have no position. \"incomplete\": a "
        "result is missing or left out.",
        "",
        _margins_line(rankings),
        "",
        _table(header, lines),
        *(["", "† Database: " + "; ".join(f"{name}: {note}" for name, note in noted) + "."] if noted else []),
    ]
    if show_overall:
        note = ("published" if rankings.get("publish_overall")
                else "**computed for review, not published** (config.json scoring.publish_overall is false)")
        out += ["", f"Overall: the geometric mean of the {len(keys)} category scores with equal weights, {note}. "
                "Stability is not a score; an implementation that fails it has no overall position. The weighting "
                "is a choice; the table below shows the positions under other weightings.", "",
                *sensitivity_table(rankings, labels)]
    return out


def sensitivity_table(rankings: dict, labels: dict) -> list[str]:
    weightings = rankings.get("sensitivity") or []
    if not weightings:
        return []
    positions = {w["key"]: {e["slug"]: e for e in w["entries"]} for w in weightings}
    header = ["Implementation", *(w["title"] for w in weightings)]
    lines = []
    for entry in rankings["overall"]["entries"]:
        slug = entry["slug"]
        cells = []
        for w in weightings:
            item = positions[w["key"]].get(slug)
            cells.append("–" if not item or item["score"] is None else f"{_rank_text(item)}: {_times(item['score'])}")
        lines.append([labels.get(slug, entry["framework"]), *cells])
    legend = "; ".join(f"{w['title']}: " + ", ".join(f"{k} ×{v}" for k, v in w["weights"].items())
                       for w in weightings)
    return ["Positions under other weightings (" + legend + "):", "", _table(header, lines)]


def application_table(rows: list[dict]) -> str:
    """The phase-2 endpoints as ratios to Axum, with each implementation's CSRF design and session store."""
    header = ["Implementation", *(f"{ENDPOINT_LABELS[ep]} vs Axum" for ep in PHASE2_ENDPOINTS), "CSRF",
              "Session store", "Hot rows p99 (ms)", "Hot rows errors"]
    lines = []
    for row in _measured(rows):
        lines.append([
            _label(row),
            *(_ratio(row, f"tier1.{ep}.rps") if _served(row, ep) else "n/i" for ep in PHASE2_ENDPOINTS),
            _phase2_label(row, "csrf") if _served(row, "form") else "n/i",
            _phase2_label(row, "session") if _served(row, "me") else "n/i",
            _median(row, "hot_rows.latency_ms.p99", 2), _errors(row, "hot_rows.error_rate"),
        ])
    return _table(header, lines)


APPLICATION_NOTE = ("Application endpoints (phase 2). CSRF is the design of the form protection (`token`: a secret "
                    "the form echoes; `fetch-metadata`: `Sec-Fetch-Site`/`Origin` checks) and the session store is "
                    "each framework's default for a signed-in user, with where the mechanism comes from (built-in, "
                    "generator, stdlib, documented, library): /form and /me compare those defaults, not one common "
                    "mechanism. A cookie store reads no database row for /me; a PostgreSQL store (Axum's "
                    "tower-sessions store included) reads one, which shows in the PostgreSQL CPU per request. Hot "
                    "rows: PUT /world/{id} on ids 1-10 only, so requests wait for each other's row locks; reported, "
                    "not ranked.")


def _capacity_cell(entry: dict, endpoint: str) -> str:
    detail = entry.get("detail", {})
    value = (detail.get("capacity") or {}).get(endpoint)
    if value is None:
        rps = (detail.get("rps_ratio") or {}).get(endpoint)
        return "–" if rps is None else f"({rps:.2f})"
    return f"{value:.2f}" + ("*" if (detail.get("basis") or {}).get(endpoint) == "cpu" else "")


def _db_cell(entry: dict, endpoint: str) -> str:
    detail = entry.get("detail", {})
    own = (detail.get("db_us_per_request") or {}).get(endpoint)
    rel = (detail.get("db_us_ratio") or {}).get(endpoint)
    if own is None:
        return "–"
    return f"{own:,.0f}" + (f" ({rel:.2f}×)" if rel is not None else "")


def _job_scores_cell(entry: dict) -> str:
    spread = entry.get("spread") or {}
    pairs = zip(spread.get("scores") or [], spread.get("cpu_models") or [])
    return "; ".join(f"{_times(score)} ({short_cpu(model)})" for score, model in pairs) or "–"


def _spread_cell(entry: dict) -> str:
    spread = entry.get("spread") or {}
    if not spread or entry.get("status") == "reference":
        return "–"
    text = _pct(spread.get("effective_percent"))
    if spread.get("basis", "own") != "own":
        own = f", own {_pct(spread['own_percent'])}" if spread.get("own_percent") is not None else ""
        text += f" ({spread['basis']}{own})"
    return text


def _check_cell(entry: dict, labels: dict) -> str:
    check = entry.get("tie_check")
    if not check:
        return "–"
    verdict = "tie" if check["tied"] else "separate"
    widest = check.get("group_spread_of")
    using = f" (with the spread of {labels.get(widest, widest)}, in its group)" if widest else ""
    return (f"{_pct(check['percent'])} vs {labels.get(check['against'], check['against'])}{using}, gap "
            f"{_pct(check['gap_percent']).lstrip('±')}: {verdict}")


def _reference_cell(entry: dict) -> str:
    margin = (entry.get("reference_margin") or {}).get("percent")
    if margin is None:
        return "–"
    return _pct(margin) + (" ≈" if entry.get("within_reference_margin") else "")


def category_tables(data: dict) -> list[str]:
    """One detail table per scored category and one for the stability check (benchmarks_results.md)."""
    rankings = data.get("rankings")
    if not rankings:
        return []
    by_slug = {r["slug"]: r for r in data["implementations"]}
    margins = rankings.get("tie_margins") or {}
    out = ["## Rankings in detail", "",
           "Per category: the position, the score, each run's capacity ratio (\"*\": scored by requests per "
           "CPU-second of the server and PostgreSQL together because a side was client-bound; in brackets: the "
           "requests/s ratio of a run with no score), what limited the runs, and the CPU model of each runner. "
           "In the database tables, \"PG µs/req\" is PostgreSQL's CPU time per request in microseconds, with its "
           "ratio to Axum's on the same runners in brackets: how much database work each request causes. "
           "\"Job scores\" is the score of each job (runner) with its CPU model, \"Spread\" the between-job "
           "spread the tie margins use (its own, or the pooled floor), \"Position check\" the comparison that set "
           "the position (a score counts with the widest spread of the group it is compared with, so that equal "
           "scores share a position) and \"vs Axum margin\" the margin of the \"≈\" check against 1.00.", ""]
    labels = {r["slug"]: _label(r) for r in data["implementations"]}
    tie_columns = ["Job scores", "Spread", "Position check", "vs Axum margin"]
    for category in rankings["categories"]:
        key = category["key"]
        out += [f"### {category['title']}", "",
                f"{category['description'][0].upper()}{category['description'][1:]}. Tie margins: "
                f"{_rule_text(category.get('tie_rule'), margins.get(key))}.", ""]

        def tie_cells(entry: dict) -> list[str]:
            return [_job_scores_cell(entry), _spread_cell(entry), _check_cell(entry, labels), _reference_cell(entry)]
        lines = []
        if category["kind"] == "throughput":
            endpoints = [run.split(".", 1)[1] for run in category["runs"]]
            database = [ep for ep in endpoints if ep in DB_ENDPOINTS]
            header = ["Implementation", "Position", "Score", *(endpoint_label(data.get("config", {}), ep)
                                                               for ep in endpoints),
                      *(f"PG µs/req {endpoint_label(data.get('config', {}), ep)}" for ep in database),
                      "Limits", *tie_columns, "Runner CPUs"]
            for entry in category["entries"]:
                row = by_slug.get(entry["slug"], {})
                limits = "; ".join(f"/{run.split('.', 1)[1]}: {_bound(row, run)}" for run in category["runs"]
                                   if _bound(row, run))
                if key == "database" and row.get("database_note"):
                    limits = f"**{row['database_note']}**" + (f"; {limits}" if limits else "")
                lines.append([_label(row) if row else entry["framework"], _rank_text(entry),
                              _times(entry["score"]) + ("≈" if entry.get("within_reference_margin") else "")
                              if entry["score"] is not None else (entry.get("reason") or entry["status"]),
                              *(_capacity_cell(entry, ep) for ep in endpoints),
                              *(_db_cell(entry, ep) for ep in database), limits or "–", *tie_cells(entry),
                              _runners(row)])
        else:
            unit = "MiB" if key == "memory" else "s"
            header = ["Implementation", "Position", "Score", f"Value ({unit})", f"Axum, same runners ({unit})",
                      *tie_columns, "Runner CPUs"]
            for entry in category["entries"]:
                row = by_slug.get(entry["slug"], {})
                detail = entry.get("detail", {})
                digits = 1 if key == "memory" else 2
                lines.append([_label(row) if row else entry["framework"], _rank_text(entry),
                              _times(entry["score"]) if entry["score"] is not None else entry["status"],
                              _num(detail.get("value"), digits), _num(detail.get("reference"), digits),
                              *tie_cells(entry), _runners(row)])
        out += [_table(header, lines), ""]
    stability = rankings.get("stability")
    if stability:
        out += [f"### {stability['title']} ({stability['tier']})", "", stability["description"][0].upper()
                + stability["description"][1:] + ".", ""]
        lines = []
        for entry in stability["entries"]:
            row = by_slug.get(entry["slug"], {})
            d = entry.get("detail", {})
            t2, t4 = d.get("tier2", {}), d.get("tier4", {})

            def worst(tier: dict) -> str:
                rate = tier.get("error_rate_max")
                return "–" if rate is None else (f"{rate * 100:.2f}%" if rate else "0")
            lines.append([_label(row) if row else entry["framework"], entry["result"] or "–",
                          _num(t2.get("rps")), _num(t2.get("p99_ms"), 1), worst(t2),
                          _num(t4.get("rps")), _num(t4.get("p99_ms"), 1), worst(t4), _num(t4.get("timeouts")),
                          "; ".join(entry["reasons"]) or "–", _runners(row)])
        out += [_table(["Implementation", "Result", "Tier 2 req/s", "Tier 2 p99 (ms)", "Tier 2 worst errors",
                        "Tier 4 req/s", "Tier 4 p99 (ms)", "Tier 4 worst errors", "Tier 4 timeouts", "Notes",
                        "Runner CPUs"], lines), ""]
    return out


def _corrections(rows: list[dict]) -> str:
    fixed = [r for r in rows if r.get("excluded")]
    return "\n".join(f"- **{_label(r)}**: {r['problem']}" for r in fixed)


def _structure(rows: list[dict]) -> str:
    noted = [r for r in rows if r.get("structure_note")]
    return "\n".join(f"- **{_label(r)}**: {r['structure_note']}" for r in noted)


def _warmup_errors(rows: list[dict]) -> str:
    lines = []
    for row in _measured(rows):
        errors = {ep: n for ep, n in row.get("flags", {}).get("warmup_errors", {}).items() if n}
        if errors:
            lines.append([_label(row), ", ".join(f"/{ep}: {n:,}" for ep, n in errors.items())])
    if not lines:
        return ""
    return _table(["Implementation", "Warm-up errors"], lines)


def _not_measured(rows: list[dict]) -> str:
    failed = [r for r in rows if r["status"] not in MEASURED]
    if not failed:
        return ""
    lines = [[_label(r), r["status"], (r.get("problem") or "").replace("|", "\\|").replace("\n", " ")]
             for r in failed]
    return "\n## Not measured\n\nThese implementations were not measured in this run. A failed conformance " \
           "check means at least one endpoint did not return the expected response, sequentially or under the " \
           "short concurrent step (125 connections for 3 s, no error allowed).\n\n" + \
        _table(["Implementation", "Status", "Reason"], lines) + "\n"


def gate_section(data: dict) -> list[str]:
    gate = data.get("publication_gate")
    if not gate:
        return []
    if gate["passed"]:
        return ["## Publication gate", "", "Passed: these results may be published automatically.", ""]
    return ["## Publication gate", "", "**Failed**: an automatic run would not publish these results:", "",
            *(f"- {p}" for p in gate["problems"]), ""]


def render_results(data: dict, review: bool = False) -> str:
    """benchmarks_results.md; review=True (the workflow summary) adds the gate and the unpublished overall."""
    rows = data["implementations"]
    tiers = data.get("config", {}).get("tiers", {})
    run = data.get("run", {})
    env = data.get("environment", {})
    parts = ["# Benchmark results", ""]
    run_ref = f"[workflow run {run['id']}]({run['url']})" if run.get("url") else "a local run"
    parts.append(notice(data))
    parts += ["", f"Generated by `bench/aggregate.py` from {run_ref}. Do not edit this file by hand. "
              "Machine-readable data: <https://rullst.win/Benchmarks/data/latest.json>."]
    if review:
        parts += ["", *gate_section(data)]
    parts += ["", "## How to read these numbers", "",
              "- Each implementation ran on its own GitHub-hosted runners (one per job), alternating rounds with "
              "the Axum baseline on the same machine. The \"vs Axum\" columns are the median of the per-round "
              "ratios over every job; they are more stable than absolute numbers, which vary between runners. "
              "Each row names the CPU model of its runners.",
              "- Values are medians over rounds; the range in brackets is the lowest and highest round.",
              "- The server had 2 vCPUs and 2 GiB of RAM. The load generator and PostgreSQL shared the other "
              "vCPUs. A run is client-bound when those vCPUs were at least 90% busy: PostgreSQL-bound when "
              "PostgreSQL used more of them than the load generator, load-generator-bound otherwise. The server "
              "might then have answered more requests, so the rankings compare requests per CPU-second of the "
              "server and PostgreSQL together instead of requests/s.",
              "- RAM is the container's memory use without inactive file cache, sampled every 100 ms.",
              "- Methodology and limitations: [README](README.md).", ""]
    if env:
        parts += [f"Software: {env.get('os')}, kernel {env.get('kernel')}, runner image "
                  f"{env.get('runner_image') or 'unknown'}, PostgreSQL {env.get('postgres')}, "
                  f"{(env.get('load_generator') or {}).get('name')} {(env.get('load_generator') or {}).get('version')}"
                  ". Full details per job are in `results/raw/`.", ""]
    parts += [pool_note(data), ""]
    parts += ["## Summary", "", summary_table(rows), "", SUMMARY_NOTE, ""]
    if any(_served(r, ep) for r in _measured(rows) for ep in PHASE2_ENDPOINTS):
        parts += ["### Application endpoints", "", application_table(rows), "", APPLICATION_NOTE, ""]
    if _corrections(rows):
        parts += ["Corrections (left-out results are shown as –):", "", _corrections(rows), ""]
    if _structure(rows):
        parts += ["Structural differences (what else runs inside the server's 2 vCPUs, runtime versions):", "",
                  _structure(rows), ""]
    if data.get("rankings"):
        parts += [*rankings_section(data, "##", review=review), "", *category_tables(data)]

    t1 = tiers.get("tier1", {})
    paths = data.get("config", {}).get("endpoint_paths", {})
    parts += [f"## Tier 1: {t1.get('connections')} connections, {t1.get('duration_s')} s per endpoint", "",
              "Each endpoint is warmed up immediately before its run (5 s, 15 s for runtimes with a JIT that "
              "compiles while running), then left idle for 2 s. Efficiency is requests per server CPU-second; "
              "\"CPU µs/req\" is the server's and PostgreSQL's CPU time per request together, and \"PG µs/req\" "
              "PostgreSQL's alone (its ratio to Axum's on the same runners in the next column).", ""]
    config = data.get("config", {})
    for endpoint in t1.get("endpoints", []):
        base = f"tier1.{endpoint}"
        database = endpoint in DB_ENDPOINTS
        lines = [[_label(r), _range(r, f"{base}.rps"), _ratio(r, f"{base}.rps"),
                  _median(r, f"{base}.rps_per_cpu"), _ratio(r, f"{base}.rps_per_cpu"),
                  _median(r, f"{base}.cpu_us_per_request", 1),
                  *([_median(r, f"{base}.db_us_per_request", 1), _ratio(r, f"{base}.db_us_per_request")]
                    if database else []),
                  _median(r, f"{base}.latency_ms.p50", 2), _median(r, f"{base}.latency_ms.p99", 2),
                  _errors(r, f"{base}.error_rate"), _median(r, f"{base}.server_cpu_cores", 2),
                  _median(r, f"{base}.db_cpu_cores", 2),
                  _endpoint_notes(r, endpoint, base)] for r in _measured(rows)]
        heading = endpoint_label(config, endpoint) if config else paths.get(endpoint, "/" + endpoint)
        parts += [f"### {heading}", "", _table(
            ["Implementation", "req/s", "vs Axum", "Efficiency (req/CPU-s)", "vs Axum", "CPU µs/req",
             *(["PG µs/req", "vs Axum"] if database else []), "p50 (ms)", "p99 (ms)",
             "Errors", "Server CPU (cores)", "DB CPU (cores)", "Notes"], lines), ""]

    warm = _warmup_errors(rows)
    if warm:
        parts += ["### Warm-up errors", "", "Responses that were not 2xx (3xx included) or failed during the "
                  "warm-ups, summed over the rounds; the warm-ups are not scored.", "", warm, ""]

    hot = config.get("hot_rows") or {}
    if any(_stat(r, "hot_rows.rps") for r in _measured(rows)):
        parts += [f"### Write contention: PUT /world/{{id}} on ids 1-{hot.get('ids', 10)} (hot rows)", "",
                  f"{t1.get('connections')} connections for {t1.get('duration_s')} s write the same "
                  f"{hot.get('ids', 10)} rows, so requests wait for each other's row locks. Reported, not ranked: "
                  "compare the errors, timeouts and p99 latency.", ""]
        lines = [[_label(r), _range(r, "hot_rows.rps"), _ratio(r, "hot_rows.rps"),
                  _median(r, "hot_rows.latency_ms.p50", 2), _median(r, "hot_rows.latency_ms.p99", 2),
                  _ratio(r, "hot_rows.latency_ms.p99"), _errors(r, "hot_rows.error_rate"),
                  _median(r, "hot_rows.timeouts"), _median(r, "hot_rows.db_us_per_request", 1),
                  _median(r, "hot_rows.db_cpu_cores", 2)]
                 for r in _measured(rows) if _served(r, hot.get("endpoint", "world-update"))]
        parts += [_table(["Implementation", "req/s", "vs Axum", "p50 (ms)", "p99 (ms)", "p99 vs Axum", "Errors",
                          "Timeouts", "PG µs/req", "DB CPU (cores)"], lines), ""]

    t2 = tiers.get("tier2", {})
    parts += [f"## Tier 2 (stability check): /{t2.get('endpoint')}, {t2.get('connections')} connections, "
              f"{t2.get('duration_s')} s", ""]
    lines = [[_label(r), _range(r, "tier2.rps"), _ratio(r, "tier2.rps"), _median(r, "tier2.rps_per_cpu"),
              _ratio(r, "tier2.rps_per_cpu"), _median(r, "tier2.latency_ms.p50", 2),
              _range(r, "tier2.latency_ms.p99", 2), _ratio(r, "tier2.latency_ms.p99"),
              _errors(r, "tier2.error_rate"), _median(r, "tier2.timeouts"), _bound(r, "tier2")]
             for r in _measured(rows)]
    parts += [_table(["Implementation", "req/s", "vs Axum", "Efficiency (req/CPU-s)", "vs Axum", "p50 (ms)",
                      "p99 (ms)", "p99 vs Axum", "Errors", "Timeouts", "Notes"], lines), ""]

    t3 = tiers.get("tier3", {})
    parts += [f"## Tier 3: idle, then /{t3.get('endpoint')} with {t3.get('connections')} connections for "
              f"{t3.get('duration_s')} s after the load tiers", "",
              "Idle is measured after start-up, before any load. The peak (the Memory category's high-water mark) "
              "is measured after the phase-1 Tier 1 runs, Tiers 2 and 4 and an idle period. CPU is in cores "
              "(2.00 = both server vCPUs busy).", ""]
    lines = [[_label(r), _range(r, "tier3.idle_ram_mib", 1), _ratio(r, "tier3.idle_ram_mib"),
              _median(r, "tier3.idle_cpu_cores", 3), _range(r, "tier3.load_ram_peak_mib", 1),
              _ratio(r, "tier3.load_ram_peak_mib"), _median(r, "tier3.load_cpu_cores", 2),
              _median(r, "tier3.rps"), _num(r.get("rps_per_mib"), 1), _median(r, "idle.tasks"),
              _bound(r, "tier3_load")] for r in _measured(rows)]
    parts += [_table(["Implementation", "Idle RAM (MiB)", "vs Axum", "Idle CPU", "Peak RAM (MiB)", "vs Axum",
                      "Load CPU", "req/s", "Tier 1 /json req/s per MiB", "Threads", "Notes"], lines), ""]

    t4 = tiers.get("tier4", {})
    parts += [f"## Tier 4 (stability check): /{t4.get('endpoint')}, {t4.get('connections')} connections for "
              f"{t4.get('duration_s')} s", "",
              "RAM growth compares the middle and the last tenth of the test. \"Still growing\" means it rose by "
              "more than 10% and 8 MiB; for garbage-collected runtimes this can be heap growth rather than a leak.", ""]
    lines = [[_label(r), _range(r, "tier4.rps"), _ratio(r, "tier4.rps"), _median(r, "tier4.rps_per_cpu"),
              _median(r, "tier4.latency_ms.p99", 2),
              _errors(r, "tier4.error_rate"), _median(r, "tier4.timeouts"), _median(r, "tier4.ram_end_mib", 1),
              _median(r, "tier4.ram_growth_mib", 1), _median(r, "after.memory_peak_mib", 1), _flags(r)]
             for r in _measured(rows)]
    parts += [_table(["Implementation", "req/s", "vs Axum", "Efficiency (req/CPU-s)", "p99 (ms)", "Errors",
                      "Timeouts", "RAM at end (MiB)",
                      "RAM growth (MiB)", "memory.peak (MiB)", "Notes"], lines), ""]

    nm = _not_measured(rows)
    if nm:
        parts.append(nm)

    parts += ["## Implementations", ""]
    lines = [[_label(r), GROUPS.get(r["group"], r["group"]), r["framework_version"], r["runtime"], r["server"],
              r["workers"], r["database_layer"], r["template_engine"], r.get("structure_note") or "–"] for r in rows]
    parts += [_table(["Implementation", "Group", "Version", "Runtime", "Server", "Workers", "Database layer",
                      "Templates", "Structure"], lines), "",
              "Each folder under `frameworks/` has a README with its configuration, its production settings and "
              "their sources.", ""]
    parts += ["## Historical note", "",
              f"These are v3 results (wrk 4.2.0). The v1 results (22 June 2026, measured by hand on a laptop, not "
              f"reproducible) are kept in [{HISTORY}]({HISTORY}); they used different hardware and code and are not "
              "comparable. The v2 results (up to Rullst 13.0.0-alpha.5) were measured with bombardier 2.0.2: "
              "compare them with these only as ratios to Axum.", ""]
    return "\n".join(parts)


def render_readme_table(data: dict) -> str:
    run = data.get("run", {})
    ref = f"[workflow run {run['id']}]({run['url']})" if run.get("url") else "the latest run"
    lines = [notice(data), "",
             f"Source: {ref}. Full tables, ranges and flags: [benchmarks_results.md](benchmarks_results.md); "
             "dashboard: <https://rullst.win/Benchmarks/>.", "", pool_note(data), "",
             summary_table(data["implementations"]), "", SUMMARY_NOTE]
    if _corrections(data["implementations"]):
        lines += ["", "Corrections (left-out results are shown as –):", "", _corrections(data["implementations"])]
    failed = [r for r in data["implementations"] if r["status"] not in MEASURED]
    if failed:
        lines += ["", "Not measured in this run: " + ", ".join(f"{_label(r)} ({r['status']})" for r in failed) + "."]
    if any(_served(r, ep) for r in _measured(data["implementations"]) for ep in PHASE2_ENDPOINTS):
        lines += ["", application_table(data["implementations"]), "", APPLICATION_NOTE]
    if data.get("rankings"):
        lines += ["", *rankings_section(data)]
    return "\n".join(lines)


def replace_between_markers(text: str, content: str) -> str:
    if START not in text or END not in text:
        raise ValueError("README.md has no results markers")
    head, rest = text.split(START, 1)
    _, tail = rest.split(END, 1)
    return f"{head}{START}\n{content}\n{END}{tail}"
