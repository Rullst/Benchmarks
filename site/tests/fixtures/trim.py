"""Writes tests/fixtures/results/ from a results directory: the files the site reads, trimmed to the
fields it shows, with markup injected into a few text fields so that the tests can check the escaping.

    python3 tests/fixtures/trim.py ../results tests/fixtures/results
"""

import json
import sys
from pathlib import Path

KEEP_METRIC_SUFFIXES = (".rps", ".rps_per_cpu", ".cpu_us_per_request", ".db_us_per_request", ".latency_ms.p50",
                        ".latency_ms.p99", ".error_rate", ".server_cpu_cores", ".db_cpu_cores", ".timeouts",
                        ".rows_updated_per_request", "ram_mib", "_cpu_cores", "ram_peak_mib", ".ram_end_mib",
                        ".ram_growth_mib", ".tasks", ".memory_peak_mib", "startup_s")
DROP_ROW = ("build", "environment", "ratios_by_cpu_model", "paired_baseline_flags", "pooled_jobs", "vs_axum",
            "load_generator_bound_rounds")
STAT = ("median", "min", "max", "n")


def stat(value: dict) -> dict:
    return {k: value[k] for k in STAT if k in value}


def rounded(value):
    """Floats to 4 decimals, to keep the fixture small."""
    if isinstance(value, float):
        return round(value, 4)
    if isinstance(value, dict):
        return {k: rounded(v) for k, v in value.items()}
    if isinstance(value, list):
        return [rounded(v) for v in value]
    return value


def trim_row(row: dict) -> dict:
    row = {k: v for k, v in row.items() if k not in DROP_ROW}
    row["metrics"] = {k: stat(v) for k, v in row.get("metrics", {}).items() if k.endswith(KEEP_METRIC_SUFFIXES)}
    row["ratios"] = {k: stat(v) for k, v in row.get("ratios", {}).items() if k.endswith(KEEP_METRIC_SUFFIXES)}
    for job in row.get("jobs", []):
        job.pop("round_orders", None)
    return row


def main(source: Path, target: Path) -> None:
    latest = json.loads((source / "latest.json").read_text())
    latest["results"] = [trim_row(r) for r in latest["results"]]
    latest["not_measured"] = [trim_row(r) for r in latest["not_measured"]]
    latest.pop("metrics", None)
    for row in latest["results"]:
        if row["slug"] == "rails":
            row["structure_note"] += ' <script>alert("structure_note")</script>'
        if row["slug"] == "laravel":
            row["maturity_note"] = '<img src=x onerror=alert(1)> & "quotes"'
    latest["labels"]["put_world"]["note"] += " <b>not bold</b>"
    site = json.loads((source / "site.json").read_text())
    versions = json.loads((source / "versions.json").read_text())
    target.mkdir(parents=True, exist_ok=True)
    (target / "rullst").mkdir(exist_ok=True)
    latest = rounded(latest)
    for name, data in (("latest.json", latest), ("site.json", site), ("versions.json", versions)):
        (target / name).write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n")
    for entry in versions["versions"]:
        full = json.loads((source / entry["file"]).read_text())
        small = {"schema": full["schema"], "rullst_version": full["rullst_version"],
                 "config": {"load_generator": full["config"]["load_generator"]}}
        (target / entry["file"]).write_text(json.dumps(small, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
