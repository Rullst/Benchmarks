"""Prototype: oha as the load generator, returning loadgen.run_load's metrics dict.

oha (Rust, Tokio, Hyper) varies the URL per request with --urls-from-file
(a uniform random choice among the file's lines) and the body with -Z (a
uniform random choice among the file's lines), independently of each other.
Method and headers are fixed for a run, so a workload whose requests carry
different cookies with matching CSRF tokens ("joint" pairing) cannot be
replayed: run_load raises ValueError, and the caller uses one session.

Differences from bombardier that the results must state:
- with -z, requests still in flight at the deadline are cancelled and
  reported as "aborted due to deadline"; they are not errors here;
- statusCodeDistribution counts every status, so non_2xx includes 3xx;
- oha's Tokio runtime gets one worker thread per client CPU (its default
  is the number of physical cores, which ignores the CPU affinity).
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlsplit

from loadgen_process import error_metrics, measure
from system import format_cpu_list
from workload import Workload, static

DEADLINE = "aborted due to deadline"


def parse_output(stdout: str) -> dict:
    raw = json.loads(stdout)
    statuses = {int(k): int(v) for k, v in (raw.get("statusCodeDistribution") or {}).items()}
    errors = {k: int(v) for k, v in (raw.get("errorDistribution") or {}).items()}
    ok = sum(v for k, v in statuses.items() if 200 <= k < 300)
    non_2xx = sum(v for k, v in statuses.items() if not 200 <= k < 300)
    transport = sum(v for k, v in errors.items() if k != DEADLINE)
    timeouts = sum(v for k, v in errors.items() if "timeout" in k.lower() or "timed out" in k.lower())
    percentiles = raw.get("latencyPercentiles") or {}
    summary = raw["summary"]

    def ms(seconds) -> float | None:
        return None if seconds is None else round(float(seconds) * 1000.0, 3)

    metrics = error_metrics(
        ok=ok, non_2xx=non_2xx, transport_errors=transport, timeouts=timeouts,
        duration=float(summary["total"]),
        error_kinds={k[:120]: v for k, v in list(errors.items())[:10]},
        latency_ms={"mean": ms(summary.get("average")), "p50": ms(percentiles.get("p50")),
                    "p90": ms(percentiles.get("p90")), "p99": ms(percentiles.get("p99")),
                    "max": ms(summary.get("slowest"))})
    metrics["aborted_at_deadline"] = errors.get(DEADLINE, 0)
    metrics["status_codes"] = {str(k): v for k, v in sorted(statuses.items())}
    return metrics


def build_command(binary: Path, base: str, workload: Workload, workdir: Path, *, connections: int,
                  duration_s: int, threads: int, timeout_s: int, client_cpus: list[int]) -> list[str]:
    if workload.pairing == "joint":
        raise ValueError("oha cannot pair per-request headers with bodies; use one session")
    if len(workload.methods()) != 1 or len(workload.header_sets()) != 1:
        raise ValueError("oha sends one method and one header set per run")
    first = workload.requests[0]
    cmd = ["taskset", "-c", format_cpu_list(client_cpus), str(binary), "--no-tui", "--output-format", "json",
           "-z", f"{duration_s}s", "-c", str(connections), "-t", f"{timeout_s}s", "-r", "0",
           "--worker-threads", str(threads), "-m", first.method]
    for name, value in first.headers:
        if name.lower() == "content-type":
            cmd += ["-T", value]
        else:
            cmd += ["-H", f"{name}: {value}"]
    bodies = workload.bodies()
    if len(bodies) > 1:
        if any(b"\n" in b or b"\r" in b for b in bodies):
            raise ValueError("oha -Z reads one body per line; a body contains a newline")
        body_file = workdir / "bodies.txt"
        body_file.write_bytes(b"\n".join(bodies) + b"\n")
        cmd += ["-Z", str(body_file)]
    elif bodies[0]:
        body_file = workdir / "body.bin"
        body_file.write_bytes(bodies[0])
        cmd += ["-D", str(body_file)]
    paths = workload.paths()
    if len(paths) > 1:
        url_file = workdir / "urls.txt"
        url_file.write_text("".join(f"{base}{p.lstrip('/')}\n" for p in paths), encoding="utf-8")
        cmd += ["--urls-from-file", str(url_file)]
    else:
        cmd.append(f"{base}{paths[0].lstrip('/')}")
    return cmd


def run_load(binary: Path, url: str, *, connections: int, duration_s: int, config: dict,
             client_cpus: list[int], server=None, database=None, db_cpus: list[int] | None = None,
             workload: Workload | None = None, tool_config: dict | None = None,
             workdir: Path | None = None) -> dict:
    """loadgen.run_load with oha. Without a workload, `url` is fetched with GET.

    With a workload, `url` is the server's base URL and the workload supplies the paths.
    """
    tool_config = tool_config or {"timeout_s": 5, "saturation_threshold": 0.9, "version": "?"}
    parts = urlsplit(url)
    base = f"{parts.scheme}://{parts.netloc}/"
    if workload is None:
        workload = static(parts.path + (f"?{parts.query}" if parts.query else "") or "/")
    workdir = workdir or Path(config.get("workdir", "out")) / "oha"
    workdir.mkdir(parents=True, exist_ok=True)
    threads = max(1, len(client_cpus))
    cmd = build_command(binary, base, workload, workdir, connections=connections, duration_s=duration_s,
                        threads=threads, timeout_s=tool_config["timeout_s"], client_cpus=client_cpus)
    metrics = measure(cmd, parse_output, tool="oha", connections=connections, duration_s=duration_s,
                      config=config, client_cpus=client_cpus,
                      saturation_threshold=tool_config["saturation_threshold"], server=server,
                      database=database, db_cpus=db_cpus)
    metrics["connections_open"] = connections
    metrics["load_generator"] = f"oha {tool_config['version']}"
    metrics["workload"] = {"label": workload.label, "requests": len(workload.requests),
                           "mode": "static" if workload.static else "dynamic"}
    return metrics
