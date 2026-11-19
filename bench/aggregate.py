#!/usr/bin/env python3
"""Combine the per-job JSON files of one workflow run into the published results.

  aggregate.py --input DIR [--frameworks LIST] [--write] [--summary FILE]

Reads every *.json written by `harness.py run`. With --write it updates:
  results/latest.json                     the newest published results
  results/rullst/<version>.json           the results for each Rullst version
  results/versions.json                   index of measured Rullst versions
  results/raw/<version>/<framework>.json  each job's full output, rounds included
  benchmarks_results.md                   the full results tables
  README.md                               the table between the results markers
The dashboard and https://rullst.win/Benchmarks/data/ serve the JSON files.
No number in these files is written by hand.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import ENDPOINTS, GROUPS, ROOT, declared_endpoints, framework_slugs, load_manifest, write_json  # noqa: E402
import rankings  # noqa: E402
from measure import summarize  # noqa: E402
from release_check import semver_key  # noqa: E402
from report import render_readme_table, render_results, replace_between_markers  # noqa: E402

SCHEMA = 1
# The published files follow the shape the Rullst site reads
# (Rullst/Rullst docs/src/website-maintenance.md); fields are only added to it.
SITE_SCHEMA = "rullst.benchmarks.latest.v1"
VERSIONS_SCHEMA = "rullst.benchmarks.versions.v1"
SITE_METRICS = {
    "json_rps": "tier1.json.rps",
    "db_single_rps": "tier1.db-single.rps",
    "avg_latency_ms": "tier1.json.latency_ms.mean",
    "peak_ram_mib": "tier3.load_ram_peak_mib",
}
SITE_RUNS = {"json_rps": "tier1.json", "db_single_rps": "tier1.db-single", "avg_latency_ms": "tier1.json",
             "peak_ram_mib": "tier3_load"}
RESULTS = ROOT / "results"
RULLST_SLUGS = ("rullst", "rullst-minimal")
HISTORY_METRICS = ("tier1.json.rps", "tier1.db-single.rps", "tier1.html.rps", "tier1.text.rps",
                   "tier1.queries.rps", "tier1.updates.rps", "tier1.fortunes.rps",
                   "tier2.latency_ms.p99", "tier3.idle_ram_mib", "tier3.load_ram_peak_mib", "tier4.error_rate")
# Absolute numbers shown next to the Axum value measured on the same runner.
PAIRED_METRICS = tuple(f"tier1.{ep}.rps" for ep in ENDPOINTS) + ("tier2.rps", "tier4.rps")


def load_jobs(folder: Path) -> list[dict]:
    jobs = []
    for path in sorted(folder.rglob("*.json")):
        try:
            data = json.loads(path.read_text())
        except ValueError:
            print(f"skipping unreadable {path}", file=sys.stderr)
            continue
        if data.get("schema") == SCHEMA and "framework" in data:
            jobs.append(data)
    return jobs


def parse_versions(text: str) -> dict:
    """Parse the `name version` lines an image writes to /bench/versions.txt."""
    versions = {}
    for line in (text or "").splitlines():
        parts = line.split()
        if len(parts) >= 2:
            versions.setdefault(parts[0], parts[1])
    return versions


def _row(slug: str, manifest: dict, entry: dict | None) -> dict:
    row = {
        "slug": slug,
        "name": manifest.get("name", slug),
        "variant": manifest.get("variant", ""),
        "language": manifest.get("language", ""),
        "group": manifest.get("group", ""),
        "package": manifest.get("framework", ""),
        "default_variant": bool(manifest.get("default_variant")),
        "framework_version": manifest.get("framework_version", ""),
        "runtime": manifest.get("runtime", ""),
        "server": manifest.get("server", ""),
        "workers": manifest.get("workers", ""),
        "database_layer": manifest.get("database_layer", ""),
        "template_engine": manifest.get("template_engine", ""),
        "logging": manifest.get("logging", ""),
        "maturity_note": manifest.get("maturity_note", ""),
        "endpoints": declared_endpoints(manifest),
        "status": "missing" if entry is None else entry.get("status", "unknown"),
        "problem": "",
        "versions": {},
        "metrics": {},
        "ratios": {},
        "flags": {},
        "build": {},
    }
    if entry is None:
        row["problem"] = "no result in this run"
        return row
    build = entry.get("build") or {}
    row["build"] = {k: build.get(k) for k in ("image_size_mib", "build_seconds", "build_args", "base_images")}
    row["versions"] = parse_versions(build.get("versions", ""))
    resolved = row["versions"].get(manifest.get("version_package", ""))
    if resolved:
        row["framework_version"] = resolved
    if entry.get("status") == "build-failed":
        row["problem"] = "image build failed: " + (entry.get("error") or "")[-400:]
    elif entry.get("status") == "failed-conformance":
        failed = [c for c in entry["conformance"]["checks"] if not c["ok"]]
        row["problem"] = "; ".join(f"{c['endpoint']}: {c['problem']}" for c in failed)[:600]
    summary_data = entry.get("summary") or {}
    row["metrics"] = summary_data.get("metrics", {})
    row["flags"] = summary_data.get("flags", {})
    if entry.get("status") == "crashed":
        phases = [r["crashed"]["phase"] for r in entry.get("rounds", []) if r.get("crashed")]
        row["problem"] = "server stopped during: " + ", ".join(sorted(set(phases)))
    rps = row["metrics"].get("tier1.json.rps") or {}
    ram = row["metrics"].get("tier3.load_ram_peak_mib") or {}
    if rps.get("median") and ram.get("median"):
        row["rps_per_mib"] = round(rps["median"] / ram["median"], 1)
    return row


def paired_baseline(job: dict) -> dict:
    """The baseline's medians in this job (same runner), for the metrics shown as absolute numbers."""
    base = job.get("implementations", {}).get(job.get("baseline", "axum")) or {}
    metrics = (base.get("summary") or {}).get("metrics", {})
    return {m: metrics[m]["median"] for m in PAIRED_METRICS if m in metrics}


def paired_baseline_flags(job: dict) -> dict:
    """The baseline's rounds and client-bound rounds per load run in this job."""
    base = job.get("implementations", {}).get(job.get("baseline", "axum")) or {}
    flags = (base.get("summary") or {}).get("flags", {})
    return {"rounds": flags.get("rounds", 0), "client_bound_rounds": dict(flags.get("client_bound_rounds", {}))}


def _manifest(slug: str) -> dict:
    try:
        return load_manifest(slug)
    except Exception:  # noqa: BLE001 - a folder removed since the run
        return {"name": slug}


def _env_brief(job: dict) -> dict:
    env = job.get("environment", {})
    runner = env.get("runner", {})
    return {
        "cpu_model": env.get("cpu_model"),
        "cpu_count": env.get("cpu_count"),
        "cpu_split": {k: env.get("cpu_split", {}).get(k) for k in ("server", "client", "database")},
        "memory_total_mib": env.get("memory_total_mib"),
        "kernel": env.get("kernel"),
        "os": env.get("os"),
        "runner_image": f"{runner.get('image_os', '')} {runner.get('image_version', '')}".strip(),
        "docker": env.get("docker"),
        "load_generator": env.get("load_generator"),
        "postgres": job.get("database", {}).get("version"),
    }


def _run_url() -> str:
    server, repo, run_id = (os.environ.get(k, "") for k in ("GITHUB_SERVER_URL", "GITHUB_REPOSITORY", "GITHUB_RUN_ID"))
    return f"{server}/{repo}/actions/runs/{run_id}" if server and repo and run_id else ""


def combine(jobs: list[dict], requested: list[str] | None = None) -> dict:
    by_framework = {job["framework"]: job for job in jobs}
    baseline = jobs[0]["baseline"] if jobs else "axum"
    slugs = requested or sorted(set(framework_slugs()) | set(by_framework))
    rows = []
    for slug in slugs:
        if slug == baseline:
            continue
        job = by_framework.get(slug)
        entry = job["implementations"].get(slug) if job else None
        manifest = (entry or {}).get("manifest") or _manifest(slug)
        row = _row(slug, manifest, entry)
        if job and row["status"] in ("measured", "crashed"):
            row["ratios"] = job.get("ratios", {})
            row["environment"] = _env_brief(job)
            row["paired_baseline"] = paired_baseline(job)
            row["paired_baseline_flags"] = paired_baseline_flags(job)
        rows.append(row)

    # The baseline row pools the baseline rounds of every job (each job
    # measured it on its own runner), which also shows runner-to-runner spread.
    base_rounds, base_entry, base_manifest = [], None, _manifest(baseline)
    for job in jobs:
        entry = job["implementations"].get(baseline)
        if entry:
            base_manifest = entry.get("manifest", base_manifest)
            base_entry = base_entry or entry
            if entry.get("rounds"):
                base_rounds += entry["rounds"]
    if base_rounds:
        pooled = dict(base_entry, summary=summarize(base_rounds), rounds=base_rounds,
                      status="crashed" if any(r.get("crashed") for r in base_rounds) else "measured")
        base_row = _row(baseline, base_manifest, pooled)
        base_row["pooled_jobs"] = sum(1 for j in jobs if j["implementations"].get(baseline, {}).get("rounds"))
    else:
        base_row = _row(baseline, base_manifest, base_entry)
    base_row["is_baseline"] = True
    rows.append(base_row)

    group_order = list(GROUPS)
    rows.sort(key=lambda r: (group_order.index(r["group"]) if r["group"] in group_order else 99,
                             not r.get("is_baseline", False), r["name"].lower(), r["variant"]))
    first = jobs[0] if jobs else {}
    rullst_version = os.environ.get("RULLST_VERSION", "").strip()
    for row in rows:
        if row["slug"] in RULLST_SLUGS and row["versions"].get("rullst"):
            rullst_version = row["versions"]["rullst"]
            break
    apply_corrections(rullst_version, rows)
    note = version_note(rullst_version, rows)
    note_pt_br = version_note(rullst_version, rows, lang="pt_br")
    started = sorted(j.get("started_at", "") for j in jobs if j.get("started_at"))
    finished = sorted(j.get("finished_at", "") for j in jobs if j.get("finished_at"))
    return {
        "schema": SCHEMA,
        "rullst_version": rullst_version,
        "note": note,
        "note_pt_br": note_pt_br,
        "measured_from": started[0] if started else "",
        "measured_to": finished[-1] if finished else "",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "run": {
            "id": os.environ.get("GITHUB_RUN_ID", ""),
            "url": _run_url(),
            "sha": os.environ.get("GITHUB_SHA", ""),
            "event": os.environ.get("GITHUB_EVENT_NAME", ""),
            "rounds": first.get("rounds_requested"),
        },
        "baseline": baseline,
        "config": first.get("config", {}),
        "environment": _env_brief(first) if first else {},
        "implementations": rows,
        "rankings": rankings.compute(rows, baseline, display_name),
    }


NOTES = Path(__file__).resolve().parent / "notes.json"
CORRECTIONS = Path(__file__).resolve().parent / "corrections.json"


def apply_corrections(version: str, rows: list[dict], path: Path = CORRECTIONS) -> None:
    """Leave out metrics that bench/corrections.json marks as invalid for this version."""
    corrections = json.loads(path.read_text()).get(version, {}) if path.is_file() else {}
    for row in rows:
        fix = corrections.get(row["slug"])
        if not fix:
            continue
        prefixes = fix.get("exclude", [])

        def kept(key: str) -> bool:
            return not any(key == p or key.startswith(p + ".") for p in prefixes)

        row["metrics"] = {k: v for k, v in row["metrics"].items() if kept(k)}
        row["ratios"] = {k: v for k, v in row["ratios"].items() if kept(k)}
        bound = row.get("flags", {}).get("client_bound_rounds")
        if bound:
            # A copy: row["flags"] is the job's own summary, written back to results/raw.
            row["flags"] = dict(row["flags"], client_bound_rounds={k: v for k, v in bound.items() if kept(k)})
        row["excluded"] = prefixes
        row["problem"] = fix.get("problem", "")


def version_note(version: str, rows: list[dict], notes_path: Path = NOTES, lang: str = "en") -> str:
    """The note for a Rullst version from bench/notes.json, with {slug:metric} ratios filled in.

    A note is a string (English) or {"en": ..., "pt_br": ...}; pt_br numbers use a decimal comma.
    """
    notes = json.loads(notes_path.read_text()) if notes_path.is_file() else {}
    entry = notes.get(version, "")
    template = entry.get(lang, "") if isinstance(entry, dict) else (entry if lang == "en" else "")
    by_slug = {r["slug"]: r for r in rows}

    def ratio(match: re.Match) -> str:
        stat = by_slug.get(match.group(1), {}).get("ratios", {}).get(match.group(2))
        if not stat:
            return "–"
        text = f"{stat['median']:.2f}"
        return text.replace(".", ",") if lang == "pt_br" else text

    return re.sub(r"\{([a-z0-9-]+):([a-z0-9._-]+)\}", ratio, template)


def history_entry(combined: dict) -> dict:
    """The few numbers per Rullst version that the dashboard plots over time."""
    rows = {r["slug"]: r for r in combined["implementations"]}
    entry = {
        "version": combined["rullst_version"],
        "measured_from": combined["measured_from"],
        "generated_at": combined["generated_at"],
        "run_url": combined["run"]["url"],
        "file": f"rullst/{combined['rullst_version']}.json",
        "note": combined.get("note", ""),
        "note_pt_br": combined.get("note_pt_br", ""),
        "implementations": {},
    }
    for slug in (*RULLST_SLUGS, combined["baseline"]):
        row = rows.get(slug)
        if not row:
            continue
        entry["implementations"][slug] = {
            "status": row["status"],
            "metrics": {m: row["metrics"][m]["median"] for m in HISTORY_METRICS if m in row["metrics"]},
            "ratios": {m: row["ratios"][m]["median"] for m in HISTORY_METRICS if m in row["ratios"]},
        }
    return entry


def display_name(row: dict) -> str:
    """The `framework` name the site matches: the variant is added unless it is the default one."""
    if row.get("variant") and not row.get("default_variant"):
        return f"{row['name']} ({row['variant']})"
    return row["name"]


def site_document(combined: dict) -> dict:
    """The published JSON: the site's `rullst.benchmarks.latest.v1` fields plus the full details."""
    measured, not_measured = [], []
    for row in combined["implementations"]:
        entry = {"framework": display_name(row), "version": row["framework_version"]}
        for key, path in SITE_METRICS.items():
            stat = row["metrics"].get(path)
            if stat:
                entry[key] = stat["median"]
        ratios = {key: row["ratios"][path]["median"] for key, path in SITE_METRICS.items() if path in row["ratios"]}
        if row.get("is_baseline"):
            ratios = {key: 1.0 for key in SITE_METRICS if key in entry}
        entry["vs_axum"] = ratios
        bound = row.get("flags", {}).get("client_bound_rounds", {})
        entry["load_generator_bound_rounds"] = {key: bound.get(run, 0) for key, run in SITE_RUNS.items()}
        entry.update(row)
        has_metric = any(key in entry for key in SITE_METRICS)
        (measured if row["status"] in ("measured", "crashed") and has_metric else not_measured).append(entry)
    document = {
        "schema": SITE_SCHEMA,
        "measured_on": (combined["measured_from"] or combined["generated_at"])[:10],
        "results": measured,
        "not_measured": not_measured,
        "metrics": {
            "json_rps": "Tier 1 /json, 125 connections: successful responses per second (median of rounds)",
            "db_single_rps": "Tier 1 /db-single, 125 connections: successful responses per second",
            "avg_latency_ms": "Tier 1 /json, 125 connections: mean latency in milliseconds",
            "peak_ram_mib": "Tier 3, 200 connections on /json: peak RAM of the server container in MiB",
            "vs_axum": "median of per-round ratios to Axum measured on the same runner (1.0 = Axum)",
            "load_generator_bound_rounds": "rounds in which the load generator's CPUs were at least 90% busy",
        },
        "auto_update": "updated automatically when a new rullst version is published on crates.io",
    }
    document.update({k: v for k, v in combined.items() if k not in ("schema", "implementations")})
    document["results_schema"] = SCHEMA
    return document


def _safe_version(version: str) -> str:
    if not re.fullmatch(r"[0-9A-Za-z.+-]+", version or ""):
        raise ValueError(f"unexpected Rullst version '{version}'")
    return version


def write_outputs(combined: dict, jobs: list[dict]) -> None:
    version = _safe_version(combined["rullst_version"])
    document = site_document(combined)
    write_json(RESULTS / "latest.json", document)
    write_json(RESULTS / "rullst" / f"{version}.json", document)
    raw = RESULTS / "raw" / version
    if raw.exists():
        shutil.rmtree(raw)
    for job in jobs:
        write_json(raw / f"{job['framework']}.json", job)

    index_path = RESULTS / "versions.json"
    index = json.loads(index_path.read_text()) if index_path.is_file() else {"versions": []}
    entries = [e for e in index["versions"] if e["version"] != version] + [history_entry(combined)]
    entries.sort(key=lambda e: semver_key(e["version"]))
    write_json(index_path, {"schema": VERSIONS_SCHEMA, "latest": version, "updated_at": combined["generated_at"],
                            "versions": entries})

    (ROOT / "benchmarks_results.md").write_text(render_results(combined))
    readme = ROOT / "README.md"
    readme.write_text(replace_between_markers(readme.read_text(), render_readme_table(combined)))


def record_attempt(version: str, reason: str) -> None:
    """Remember a release whose Rullst build failed, so the daily check skips it."""
    path = RESULTS / "attempts.json"
    data = json.loads(path.read_text()) if path.is_file() else {"schema": SCHEMA, "versions": []}
    data["versions"] = [e for e in data["versions"] if e["version"] != version]
    data["versions"].append({"version": _safe_version(version), "reason": reason[:500], "run_url": _run_url(),
                             "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
    write_json(path, data)


def rullst_usable(combined: dict) -> tuple[bool, str]:
    rows = [r for r in combined["implementations"] if r["slug"] in RULLST_SLUGS]
    bad = [f"{r['slug']}: {r['status']} {r.get('problem', '')}".strip() for r in rows
           if r["status"] not in ("measured", "crashed")]
    return (not bad and bool(rows)), "; ".join(bad)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--frameworks", default="", help="comma-separated list that was requested")
    parser.add_argument("--write", action="store_true", help="update the files in the repository")
    parser.add_argument("--require-rullst", action="store_true",
                        help="refuse to write (and record a failed attempt) when Rullst was not measured")
    parser.add_argument("--summary", type=Path, help="also write the Markdown report here")
    args = parser.parse_args(argv)
    jobs = load_jobs(args.input)
    if not jobs:
        print(f"no results found in {args.input}", file=sys.stderr)
        return 1
    requested = None
    if args.frameworks and args.frameworks.lower() != "all":
        requested = [s.strip() for s in args.frameworks.split(",") if s.strip()]
    combined = combine(jobs, requested)
    if args.summary:
        args.summary.write_text(render_results(combined))
    if args.write:
        usable, reason = rullst_usable(combined)
        if args.require_rullst and not usable:
            record_attempt(combined["rullst_version"] or os.environ.get("RULLST_VERSION", "unknown"), reason)
            print(f"Rullst was not measured ({reason}); recorded a failed attempt", file=sys.stderr)
            return 2
        write_outputs(combined, jobs)
    return 0


if __name__ == "__main__":
    sys.exit(main())
