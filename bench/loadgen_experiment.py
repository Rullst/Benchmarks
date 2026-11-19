#!/usr/bin/env python3
"""Temporary experiment: bombardier, wrk and oha against the same Axum server.

One runner, one Axum container (the server's 2 vCPUs), PostgreSQL idle on the
client vCPUs. For each round, each client CPU count (2, then 1) and each
tool (in a rotated order), one 10 s run of GET /json with 125 connections:
- bombardier 2.0.2 (fasthttp), the current load generator;
- wrk 4.2.0 static (one request, built once) and dynamic (`/json?id=N`,
  10,000 prebuilt requests cycled by the Lua `request` function);
- oha 1.16.0 static and dynamic (the same 10,000 URLs via --urls-from-file);
- wrk2 static at -R 1,000,000 when its binary is available.
Usage: loadgen_experiment.py --out DIR [--rounds 3] (binaries in BOMBARDIER, WRK, OHA, WRK2)
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import loadgen  # noqa: E402
import loadgen_oha  # noqa: E402
import loadgen_wrk  # noqa: E402
from common import load_config, load_manifest, log, write_json  # noqa: E402
from containers import DB_CONTAINER, build_image, remove, start_database, start_server  # noqa: E402
from loadgen_process import measure  # noqa: E402
from system import cpu_split, environment, format_cpu_list  # noqa: E402
from workload import query_variants, static  # noqa: E402

BENCH = Path(__file__).resolve().parent
CONNECTIONS = 125
DURATION_S = 10
FIELDS = ["rps", "loadgen_cpu_cores", "loadgen_cpu_busy", "client_cpu_busy", "server_cpu_cores",
          "rps_per_loadgen_cpu", "latency_ms.p50", "latency_ms.p99", "error_rate"]


def get(d: dict, path: str):
    for part in path.split("."):
        d = d.get(part) if isinstance(d, dict) else None
    return d


def run_wrk2(binary: Path, url: str, cpus: list[int], config: dict, server, workdir: Path) -> dict:
    script, requests = loadgen_wrk.write_files(static("/json"), workdir)
    cmd = ["taskset", "-c", format_cpu_list(cpus), str(binary), "-t", str(len(cpus)), "-c", str(CONNECTIONS),
           "-d", f"{DURATION_S}s", "-R", "1000000", "--timeout", "5s", "-s", str(script), url, "--",
           str(requests)]
    return measure(cmd, loadgen_wrk.parse_output, tool="wrk2", connections=CONNECTIONS, duration_s=DURATION_S,
                   config=config, client_cpus=cpus, saturation_threshold=0.9, server=server)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--rounds", type=int, default=3)
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    config = load_config()
    pins = json.loads((BENCH / "loadgens.json").read_text())
    split = cpu_split(config["server"]["cpus"], config["min_runner_cpus"])
    os.sched_setaffinity(0, split["client"])
    binaries = {name: Path(os.environ[var]) for name, var in
                (("bombardier", "BOMBARDIER"), ("wrk", "WRK"), ("oha", "OHA"), ("wrk2", "WRK2"))
                if os.environ.get(var) and Path(os.environ[var]).is_file()}
    loadgen.verify_binary(binaries["bombardier"], config["load_generator"]["sha256"])
    loadgen.verify_binary(binaries["oha"], pins["oha"]["sha256"])
    log(f"CPU split {split}; tools {sorted(binaries)}")

    database = start_database(config, split["client"])
    manifest = load_manifest("axum")
    build = build_image(manifest)
    server = start_server(manifest, config, split["server"], keep_logs=False)
    variants = query_variants("/json")
    runs: list[dict] = []
    try:
        server.wait_ready(120)
        time.sleep(config["server"]["settle_s"])
        url = server.base_url + "/json"
        base = server.base_url
        loadgen.run_load(binaries["bombardier"], url, connections=CONNECTIONS, duration_s=5, config=config,
                         client_cpus=split["client"], server=server)  # warm-up

        def tools(cpus: list[int], workdir: Path) -> dict:
            wrk_cfg = {**pins["wrk"]}
            oha_cfg = {**pins["oha"]}
            common = dict(connections=CONNECTIONS, duration_s=DURATION_S, config=config, client_cpus=cpus,
                          server=server)
            table = {
                "bombardier": lambda: loadgen.run_load(binaries["bombardier"], url, **common),
                "wrk static": lambda: loadgen_wrk.run_load(binaries["wrk"], url, tool_config=wrk_cfg,
                                                           workdir=workdir / "wrk-static", **common),
                "wrk dynamic": lambda: loadgen_wrk.run_load(binaries["wrk"], base, workload=variants,
                                                            tool_config=wrk_cfg, workdir=workdir / "wrk-dyn",
                                                            **common),
                "oha static": lambda: loadgen_oha.run_load(binaries["oha"], url, tool_config=oha_cfg,
                                                           workdir=workdir / "oha-static", **common),
                "oha dynamic": lambda: loadgen_oha.run_load(binaries["oha"], base, workload=variants,
                                                            tool_config=oha_cfg, workdir=workdir / "oha-dyn",
                                                            **common),
            }
            if "wrk2" in binaries:
                table["wrk2 static"] = lambda: run_wrk2(binaries["wrk2"], base, cpus, config, server,
                                                        workdir / "wrk2")
            return table

        for number in range(1, args.rounds + 1):
            for cpus in (split["client"], split["client"][:1]):
                table = tools(cpus, out / "work")
                names = list(table)
                shift = (number - 1) % len(names)
                for name in names[shift:] + names[:shift]:
                    log(f"round {number}, client CPUs {cpus}: {name}")
                    try:
                        metrics = table[name]()
                    except Exception as exc:  # noqa: BLE001 - record and continue the experiment
                        metrics = {"error": f"{type(exc).__name__}: {exc}"[:500]}
                    metrics.pop("_ram_samples", None)
                    if metrics.get("loadgen_cpu_cores"):
                        metrics["rps_per_loadgen_cpu"] = round(metrics["rps"] / metrics["loadgen_cpu_cores"], 1)
                    runs.append({"round": number, "client_cpus": cpus, "tool": name, **metrics})
                    write_json(out / "runs.json", {"runs": runs})
                    time.sleep(config["server"]["cooldown_s"])
    finally:
        server.stop()
        remove(DB_CONTAINER)

    result = {"environment": environment(split, {"bombardier": config["load_generator"], **pins}),
              "database": database, "build": build, "connections": CONNECTIONS, "duration_s": DURATION_S,
              "runs": runs}
    write_json(out / "runs.json", result)
    lines = [f"Axum GET /json, {CONNECTIONS} connections, {DURATION_S} s, medians of {args.rounds} rounds "
             f"(server CPUs {split['server']}, client CPUs {split['client']}).", "",
             "| Tool | Client CPUs | " + " | ".join(FIELDS) + " | runs |",
             "| --- | ---: |" + " ---: |" * (len(FIELDS) + 1)]
    for count in (len(split["client"]), 1):
        for name in dict.fromkeys(r["tool"] for r in runs):
            rows = [r for r in runs if r["tool"] == name and len(r["client_cpus"]) == count and "error" not in r]
            cells = []
            for field in FIELDS:
                values = [v for v in (get(r, field) for r in rows) if v is not None]
                cells.append(f"{statistics.median(values):,.3f}" if values else "–")
            lines.append(f"| {name} | {count} | " + " | ".join(cells) + f" | {len(rows)} |")
    errors = [f"- {r['tool']} ({len(r['client_cpus'])} CPUs, round {r['round']}): {r['error']}"
              for r in runs if "error" in r]
    if errors:
        lines += ["", "Errors:", *errors]
    (out / "summary.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
