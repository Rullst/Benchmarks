"""Markdown rendering of the combined results (benchmarks_results.md and README table)."""

from __future__ import annotations

from common import GROUPS

START = "<!-- results:start -->"
END = "<!-- results:end -->"
HISTORY = "history/2026-06-22-laptop.md"


def _stat(row: dict, path: str, kind: str = "metrics") -> dict | None:
    return row.get(kind, {}).get(path)


def _num(value, digits: int = 0) -> str:
    if value is None:
        return "–"
    return f"{value:,.{digits}f}"


def _median(row: dict, path: str, digits: int = 0, kind: str = "metrics") -> str:
    stat = _stat(row, path, kind)
    return _num(stat["median"], digits) if stat else "–"


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
    return f"{stat['median']:.2f}" if stat else "–"


def _label(row: dict) -> str:
    label = row["name"]
    if row.get("variant"):
        label += f" ({row['variant']})"
    if row.get("is_baseline"):
        label += " – baseline"
    return label


def _bound(row: dict, run: str) -> str:
    rounds = row.get("flags", {}).get("rounds", 0)
    count = row.get("flags", {}).get("client_bound_rounds", {}).get(run, 0)
    return f"client-bound {count}/{rounds}" if count else ""


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
    return [r for r in rows if r["status"] in ("measured", "crashed")]


TEXT_COLUMNS = {"Implementation", "Version", "Language", "Notes", "Status", "Reason", "Group", "Runtime",
                "Server", "Workers", "Database layer", "Templates", "Overall", "Speed", "Database",
                "Under pressure", "Memory (RAM)", "Endurance", "Startup"}
# Tier 1 endpoints in the summary table, as ratios to Axum.
SUMMARY_ENDPOINTS = ("json", "html", "db-single", "queries", "updates", "fortunes")


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


def notice(data: dict) -> str:
    """The context every results surface shows above the numbers."""
    env = data.get("environment", {})
    run = data.get("run", {})
    measured = (data.get("measured_from") or data["generated_at"])[:10]
    hardware = (f"GitHub-hosted runners ({env.get('cpu_model') or 'CPU unknown'}, {env.get('cpu_count')} vCPUs, "
                f"{_num((env.get('memory_total_mib') or 0) / 1024, 0)} GiB RAM; each server limited to 2 vCPUs "
                "and 2 GiB)")
    return (f"> Measured on {measured} with **Rullst {data.get('rullst_version') or 'unknown'}** on {hardware}. "
            f"Values are medians of {run.get('rounds')} rounds. Each implementation ran on its own runner, "
            "alternating rounds with the Axum baseline; the ratios to Axum (1.00 = Axum) cancel most of the "
            "difference between runners, so the table leads with them. Absolute requests per second differ "
            "between runners: each one is shown with, in brackets, Axum's value on the same runner. These results "
            "update automatically when a new Rullst version is published on crates.io. "
            f"Last update: {data['generated_at'][:10]}."
            + (f"\n>\n> **Note:** {data['note']}" if data.get("note") else ""))


def _paired(row: dict, path: str) -> str:
    """An absolute median with, in brackets, the baseline's median from the same runner."""
    text = _median(row, path)
    base = (row.get("paired_baseline") or {}).get(path)
    if text != "–" and base is not None and not row.get("is_baseline"):
        text += f" ({_num(base)})"
    return text


def _served(row: dict, endpoint: str) -> bool:
    return endpoint in row.get("endpoints", (endpoint,))


def summary_table(rows: list[dict]) -> str:
    header = ["Implementation", "Version", "Language", *(f"/{ep} vs Axum" for ep in SUMMARY_ENDPOINTS),
              "/json req/s (Axum)", "Idle RAM (MiB)", "Peak RAM (MiB)", "Tier 4 errors"]
    lines = []
    for row in _measured(rows):
        lines.append([
            _label(row), row["framework_version"], row["language"],
            *(_ratio(row, f"tier1.{ep}.rps") if _served(row, ep) else "n/i" for ep in SUMMARY_ENDPOINTS),
            _paired(row, "tier1.json.rps"),
            _median(row, "tier3.idle_ram_mib", 1), _median(row, "tier3.load_ram_peak_mib", 1),
            _errors(row, "tier4.error_rate"),
        ])
    return _table(header, lines)


SUMMARY_NOTE = ("Ratios are requests/s divided by Axum's on the same runner (higher is better). \"/json req/s "
                "(Axum)\" is the absolute number, with Axum's on the same runner in brackets: compare absolute "
                "numbers only within a row. \"n/i\": not implemented yet (the folder's bench.json does not list "
                "the endpoint). /queries and /updates use queries=20.")


def _rank_text(entry: dict) -> str:
    if entry["status"] == "reference":
        return "reference"
    if entry["position"] is None:
        return entry["status"]
    return f"{entry['position']}" + (" (tie)" if entry["tie"] else "")


def _endurance_flags(detail: dict) -> str:
    notes = []
    if detail.get("error_rate"):
        notes.append(f"errors {detail['error_rate'] * 100:.2f}%")
    if detail.get("timeouts"):
        notes.append(f"{_num(detail['timeouts'])} timeouts")
    if detail.get("ram_growing_rounds"):
        notes.append(f"RAM growing {detail['ram_growing_rounds']}/{detail['rounds']}")
    if detail.get("crashed_rounds"):
        notes.append(f"stopped {detail['crashed_rounds']}/{detail['rounds']}")
    return ", ".join(notes)


def _times(value: float) -> str:
    """Two decimals, three below 0.1 so that small ratios still differ."""
    return f"{value:.2f}" if value >= 0.1 else f"{value:.3f}"


THROUGHPUT = ("speed", "database", "pressure", "endurance")
CATEGORY_COLUMNS = (("speed", "Speed"), ("database", "Database"), ("pressure", "Under pressure"),
                    ("memory", "Memory (RAM)"), ("endurance", "Endurance"), ("startup", "Startup"))


def _category_cell(key: str, entry: dict) -> str:
    """Position and the measured value: a score or ratio to Axum, or seconds for start-up."""
    if entry["score"] is None:
        return entry["status"]
    if key == "startup":
        value = f"{entry['detail']['startup_s']:.2f} s"
    elif key in THROUGHPUT:
        value = f"{_times(entry['score'])}×" + ("*" if entry.get("efficiency_runs") else "")
    else:
        value = f"{_times(entry['ratio'])}×"
    if key == "endurance" and _endurance_flags(entry["detail"]):
        value += f" ({_endurance_flags(entry['detail'])})"
    return f"{_rank_text(entry)}: {value}"


def _overall_cell(entry: dict) -> str:
    if entry["score"] is None:
        return entry["status"]
    return f"{_rank_text(entry)}: {_times(entry['score'])}"


def rankings_section(data: dict, level: str = "###") -> list[str]:
    """The overall and per-category positions, with one sentence per tier."""
    rankings = data.get("rankings")
    if not rankings:
        return []
    tiers = data.get("config", {}).get("tiers", {})
    t1, t2, t3, t4 = (tiers.get(k, {}) for k in ("tier1", "tier2", "tier3", "tier4"))
    poll = rankings.get("startup_resolution_s")
    labels = {r["slug"]: _label(r) for r in data["implementations"]}
    cells = {c["key"]: {e["slug"]: e for e in c["entries"]} for c in rankings["categories"]}
    keys = [key for key, _ in CATEGORY_COLUMNS if key in cells]
    header = ["Implementation", "Overall", *(title for key, title in CATEGORY_COLUMNS if key in cells)]
    lines = []
    for entry in rankings["overall"]["entries"]:
        slug = entry["slug"]
        lines.append([labels.get(slug, entry["framework"]), _overall_cell(entry),
                      *(_category_cell(key, cells[key][slug]) for key in keys)])
    return [
        f"{level} Rankings", "",
        f"- **Speed (Tier 1):** /text, /json, /db-single and /html with {t1.get('connections')} "
        f"connections for {t1.get('duration_s')} s each; the score is the geometric mean of the four ratios to "
        "Axum.",
        f"- **Database (Tier 1):** /queries and /updates (20 random rows per request) and /fortunes, with the "
        f"same {t1.get('connections')} connections for {t1.get('duration_s')} s each; the score is the geometric "
        "mean of the three ratios to Axum.",
        f"- **Under pressure (Tier 2):** requests per second on /{t2.get('endpoint')} with "
        f"{t2.get('connections')} connections for {t2.get('duration_s')} s.",
        f"- **Memory (Tier 3):** the most RAM the server used while answering /{t3.get('endpoint')} with "
        f"{t3.get('connections')} connections; lower is better, so the table shows the RAM ratio and the score "
        "is its inverse.",
        f"- **Endurance (Tier 4):** requests per second on /{t4.get('endpoint')} with {t4.get('connections')} "
        f"connections for {_num((t4.get('duration_s') or 0) / 60)} minutes; errors, timeouts, RAM still "
        "growing and stops are listed with it.",
        f"- **Startup:** time from starting the container to its first answer; lower is better. The harness "
        f"checks every {poll} s, so times below {poll} s count as equal.",
        f"- **Overall:** the geometric mean of the {len(keys)} category scores, each weighted equally "
        f"(1/{len(keys)}), with every score oriented so that higher is better and Axum at 1.00. The weighting "
        "is a choice; the per-category positions are the detail.",
        "",
        "Each cell is the position and the score: a ratio to Axum (the RAM ratio for Memory, seconds for "
        "Startup). In the throughput categories each run counts with its requests/s ratio, except that a run "
        "where either server was client-bound (the load generator or the database was the limit) counts with "
        "its server efficiency ratio (requests per server CPU-second) instead; \"*\" marks a score where that "
        f"happened. \"(tie)\": equal scores, or start-up times within {poll} s. Axum is the reference and has "
        "no position. \"incomplete\": a result is missing, left out, or the endpoint is not implemented yet, so "
        "there is no position rather than one computed from fewer metrics. \"not comparable\": a run was "
        "client-bound in most rounds for both the implementation and Axum and server efficiency could not "
        "score it, so its requests/s ratio would compare two load generators; there is no position.",
        "",
        _table(header, lines),
    ]


def _corrections(rows: list[dict]) -> str:
    fixed = [r for r in rows if r.get("excluded")]
    return "\n".join(f"- **{_label(r)}**: {r['problem']}" for r in fixed)


def _not_measured(rows: list[dict]) -> str:
    failed = [r for r in rows if r["status"] not in ("measured", "crashed")]
    if not failed:
        return ""
    lines = [[_label(r), r["status"], (r.get("problem") or "").replace("|", "\\|").replace("\n", " ")]
             for r in failed]
    return "\n## Not measured\n\nThese implementations were not measured in this run. A failed conformance " \
           "check means at least one endpoint did not return the expected response.\n\n" + \
        _table(["Implementation", "Status", "Reason"], lines) + "\n"


def render_results(data: dict) -> str:
    rows = data["implementations"]
    tiers = data.get("config", {}).get("tiers", {})
    run = data.get("run", {})
    env = data.get("environment", {})
    parts = ["# Benchmark results", ""]
    run_ref = f"[workflow run {run['id']}]({run['url']})" if run.get("url") else "a local run"
    parts.append(notice(data))
    parts += ["", f"Generated by `bench/aggregate.py` from {run_ref}. Do not edit this file by hand. "
              "Machine-readable data: <https://rullst.win/Benchmarks/data/latest.json>."]
    parts += ["", "## How to read these numbers", "",
              "- Each implementation ran on its own GitHub-hosted runner, alternating rounds with the Axum "
              "baseline on the same machine. The \"vs Axum\" columns are the median of the per-round ratios; "
              "they are more stable than absolute numbers, which vary between runners. The summary shows Axum's "
              "value from the same runner next to each absolute number.",
              "- Values are medians over rounds; the range in brackets is the lowest and highest round.",
              "- The server had 2 vCPUs and 2 GiB of RAM. The load generator and PostgreSQL shared the other "
              "vCPUs. \"client-bound\" means those vCPUs were at least 90% busy during the test: the server "
              "might have answered more requests, so its requests/s understate it; compare the efficiency "
              "(requests per server CPU-second) instead, as the rankings do.",
              "- RAM is the container's memory use without inactive file cache, sampled every 100 ms.",
              "- Methodology and limitations: [README](README.md).", ""]
    if env:
        parts += [f"Runner: {env.get('cpu_model')} ({env.get('cpu_count')} vCPUs), "
                  f"{_num((env.get('memory_total_mib') or 0) / 1024, 1)} GiB RAM, {env.get('os')}, "
                  f"kernel {env.get('kernel')}, runner image {env.get('runner_image') or 'unknown'}, "
                  f"PostgreSQL {env.get('postgres')}, {(env.get('load_generator') or {}).get('name')} "
                  f"{(env.get('load_generator') or {}).get('version')}. Full details per job are in "
                  "`results/raw/`.", ""]
    parts += ["## Summary", "", summary_table(rows), "", SUMMARY_NOTE, ""]
    if _corrections(rows):
        parts += ["Corrections (left-out results are shown as –):", "", _corrections(rows), ""]
    if data.get("rankings"):
        parts += [*rankings_section(data, "##"), ""]

    t1 = tiers.get("tier1", {})
    paths = data.get("config", {}).get("endpoint_paths", {})
    parts += [f"## Tier 1: {t1.get('connections')} connections, {t1.get('duration_s')} s per endpoint", "",
              "Efficiency is requests per server CPU-second (req/s divided by the server's CPU use in cores): what "
              "a request costs the server, which stays comparable when the load generator or the database was "
              "the limit (client-bound). DB CPU is PostgreSQL's CPU use, on the client vCPUs.", ""]
    for endpoint in t1.get("endpoints", []):
        base = f"tier1.{endpoint}"
        lines = [[_label(r), _range(r, f"{base}.rps"), _ratio(r, f"{base}.rps"),
                  _median(r, f"{base}.rps_per_cpu"), _ratio(r, f"{base}.rps_per_cpu"),
                  _median(r, f"{base}.latency_ms.p50", 2), _median(r, f"{base}.latency_ms.p99", 2),
                  _errors(r, f"{base}.error_rate"), _median(r, f"{base}.server_cpu_cores", 2),
                  _median(r, f"{base}.db_cpu_cores", 2),
                  _bound(r, base) if _served(r, endpoint) else "not implemented yet"] for r in _measured(rows)]
        parts += [f"### {paths.get(endpoint, '/' + endpoint)}", "", _table(
            ["Implementation", "req/s", "vs Axum", "Efficiency (req/CPU-s)", "vs Axum", "p50 (ms)", "p99 (ms)",
             "Errors", "Server CPU (cores)", "DB CPU (cores)", "Notes"], lines), ""]

    t2 = tiers.get("tier2", {})
    parts += [f"## Tier 2: /{t2.get('endpoint')}, {t2.get('connections')} connections, {t2.get('duration_s')} s", ""]
    lines = [[_label(r), _range(r, "tier2.rps"), _ratio(r, "tier2.rps"), _median(r, "tier2.rps_per_cpu"),
              _ratio(r, "tier2.rps_per_cpu"), _median(r, "tier2.latency_ms.p50", 2),
              _range(r, "tier2.latency_ms.p99", 2), _ratio(r, "tier2.latency_ms.p99"),
              _errors(r, "tier2.error_rate"), _median(r, "tier2.timeouts"), _bound(r, "tier2")]
             for r in _measured(rows)]
    parts += [_table(["Implementation", "req/s", "vs Axum", "Efficiency (req/CPU-s)", "vs Axum", "p50 (ms)",
                      "p99 (ms)", "p99 vs Axum", "Errors", "Timeouts", "Notes"], lines), ""]

    t3 = tiers.get("tier3", {})
    parts += [f"## Tier 3: idle, then /{t3.get('endpoint')} with {t3.get('connections')} connections for "
              f"{t3.get('duration_s')} s", "",
              "Idle is measured after start-up, before any load. CPU is in cores (2.00 = both server vCPUs busy).", ""]
    lines = [[_label(r), _range(r, "tier3.idle_ram_mib", 1), _ratio(r, "tier3.idle_ram_mib"),
              _median(r, "tier3.idle_cpu_cores", 3), _range(r, "tier3.load_ram_peak_mib", 1),
              _ratio(r, "tier3.load_ram_peak_mib"), _median(r, "tier3.load_cpu_cores", 2),
              _median(r, "tier3.rps"), _num(r.get("rps_per_mib"), 1), _median(r, "idle.tasks"),
              _bound(r, "tier3_load")] for r in _measured(rows)]
    parts += [_table(["Implementation", "Idle RAM (MiB)", "vs Axum", "Idle CPU", "Peak RAM (MiB)", "vs Axum",
                      "Load CPU", "req/s", "Tier 1 /json req/s per MiB", "Threads", "Notes"], lines), ""]

    t4 = tiers.get("tier4", {})
    parts += [f"## Tier 4: /{t4.get('endpoint')}, {t4.get('connections')} connections for "
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
              r["workers"], r["database_layer"], r["template_engine"]] for r in rows]
    parts += [_table(["Implementation", "Group", "Version", "Runtime", "Server", "Workers", "Database layer",
                      "Templates"], lines), "",
              "Each folder under `frameworks/` has a README with its configuration and the reasons for it.", ""]
    parts += ["## Historical note", "",
              f"Results published before the rebuild (22 June 2026, a laptop, not reproducible) are kept in "
              f"[{HISTORY}]({HISTORY}). They used different hardware and code and are not comparable.", ""]
    return "\n".join(parts)


def render_readme_table(data: dict) -> str:
    run = data.get("run", {})
    ref = f"[workflow run {run['id']}]({run['url']})" if run.get("url") else "the latest run"
    lines = [notice(data), "",
             f"Source: {ref}. Full tables, ranges and flags: [benchmarks_results.md](benchmarks_results.md); "
             "dashboard: <https://rullst.win/Benchmarks/>.", "",
             summary_table(data["implementations"]), "", SUMMARY_NOTE]
    if _corrections(data["implementations"]):
        lines += ["", "Corrections (left-out results are shown as –):", "", _corrections(data["implementations"])]
    failed = [r for r in data["implementations"] if r["status"] not in ("measured", "crashed")]
    if failed:
        lines += ["", "Not measured in this run: " + ", ".join(f"{_label(r)} ({r['status']})" for r in failed) + "."]
    if data.get("rankings"):
        lines += ["", *rankings_section(data)]
    return "\n".join(lines)


def replace_between_markers(text: str, content: str) -> str:
    if START not in text or END not in text:
        raise ValueError("README.md has no results markers")
    head, rest = text.split(START, 1)
    _, tail = rest.split(END, 1)
    return f"{head}{START}\n{content}\n{END}{tail}"
