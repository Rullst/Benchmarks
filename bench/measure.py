"""One measurement round (all four tiers) and the per-job summary."""

from __future__ import annotations

import statistics
import time
from pathlib import Path

from common import ENDPOINTS, BenchError, declared_endpoints, endpoint_path, log
from containers import Server, database_handle, reset_tables, start_server
from loadgen import MIB, efficiency, run_load
from stats import get_path, ratio, summary, window_median

# Metrics summarized over rounds. Ratios to the baseline are computed for
# every metric except error counts and rates and the database's CPU use.
# rps_per_cpu is the server efficiency: requests per server CPU-second.
METRICS = [
    *(f"tier1.{ep}.{m}" for ep in ENDPOINTS
      for m in ("rps", "latency_ms.mean", "latency_ms.p50", "latency_ms.p99", "error_rate",
                "server_cpu_cores", "rps_per_cpu", "db_cpu_cores")),
    "tier2.rps", "tier2.latency_ms.p50", "tier2.latency_ms.p99", "tier2.error_rate", "tier2.timeouts",
    "tier2.server_cpu_cores", "tier2.rps_per_cpu",
    "tier3.idle_ram_mib", "tier3.idle_cpu_cores", "tier3.load_ram_peak_mib", "tier3.load_cpu_cores",
    "tier3.rps",
    "tier4.rps", "tier4.latency_ms.p99", "tier4.error_rate", "tier4.transport_errors", "tier4.timeouts",
    "tier4.server_cpu_cores", "tier4.rps_per_cpu",
    "tier4.ram_mid_mib", "tier4.ram_end_mib", "tier4.ram_growth_mib",
    "startup_s", "idle.tasks", "after.ram_mib", "after.memory_peak_mib",
]
NO_RATIO = ("error_rate", "transport_errors", "timeouts", "ram_growth_mib", "tasks", "db_cpu_cores")
LOAD_RUNS = [*(f"tier1.{ep}" for ep in ENDPOINTS), "tier2", "tier3_load", "tier4"]
# Throughput runs whose capacity ratio the rankings use (see capacity_ratio).
CAPACITY_RUNS = [*(f"tier1.{ep}" for ep in ENDPOINTS), "tier2", "tier4"]


class Crashed(Exception):
    def __init__(self, phase: str, state: dict):
        super().__init__(phase)
        self.phase = phase
        self.state = state


def _strip_samples(metrics: dict) -> dict:
    metrics.pop("_ram_samples", None)
    return metrics


def _check_alive(server: Server, phase: str) -> None:
    state = server.state()
    if not state.get("Running"):
        raise Crashed(phase, {k: state.get(k) for k in ("Status", "ExitCode", "OOMKilled", "Error")})


def _idle_window(server: Server, seconds: float, interval: float) -> dict:
    cpu_before = server.cpu_usec()
    started = time.monotonic()
    samples = []
    while time.monotonic() - started < seconds:
        samples.append(server.ram_bytes())
        time.sleep(interval)
    wall = time.monotonic() - started
    return {
        "ram_mib": round(statistics.median(samples) / MIB, 1),
        "cpu_cores": round((server.cpu_usec() - cpu_before) / 1e6 / wall, 4),
        "tasks": server.tasks(),
        "processes": server.processes(),
    }


def ram_trend(samples: list[tuple[float, int]], leak: dict) -> dict:
    """RAM in the middle and at the end of Tier 4, and whether it was still growing."""
    mid = window_median(samples, 0.45, 0.55)
    end = window_median(samples, 0.9, 1.0)
    if mid is None or end is None:
        return {"ram_mid_mib": None, "ram_end_mib": None, "ram_growth_mib": None, "ram_growing": False}
    growth = end - mid
    growing = growth > leak["min_growth_mib"] * MIB and growth > leak["min_growth_ratio"] * mid
    series = []
    next_t = 0.0
    for t, ram in samples:
        if t >= next_t:
            series.append([round(t, 1), round(ram / MIB, 1)])
            next_t = t + 1.0
    return {
        "ram_mid_mib": round(mid / MIB, 1),
        "ram_end_mib": round(end / MIB, 1),
        "ram_growth_mib": round(growth / MIB, 1),
        "ram_growing": growing,
        "ram_series_mib": series,
    }


def measure_round(manifest: dict, config: dict, split: dict, binary: Path, number: int) -> dict:
    tiers = config["tiers"]
    srv = config["server"]
    record: dict = {"round": number, "implementation": manifest["slug"], "crashed": None}
    # Every round starts from the same `world` table (/updates rewrites rows).
    reset_tables(config)
    server = start_server(manifest, config, split["server"], keep_logs=False)
    client = split["client"]
    database = database_handle(config)
    served = declared_endpoints(manifest)
    endpoints = [ep for ep in tiers["tier1"]["endpoints"] if ep in served]

    def load(path: str, connections: int, duration_s: int) -> dict:
        return run_load(binary, server.base_url + path, connections=connections,
                        duration_s=duration_s, config=config, client_cpus=client, server=server,
                        database=database, db_cpus=split.get("database", client))

    try:
        record["startup_s"] = server.wait_ready(manifest.get("startup_timeout_s", 120))
        time.sleep(srv["settle_s"])
        idle = _idle_window(server, tiers["tier3"]["idle_s"], config["sampling_interval_s"])
        record["idle"] = idle

        warm = config["warmup"]
        warmup_errors = 0
        for endpoint in endpoints:
            result = load(endpoint_path(config, endpoint), warm["connections"], warm["duration_s"])
            warmup_errors += result["non_2xx"] + result["transport_errors"]
            _check_alive(server, f"warm-up /{endpoint}")
        record["warmup_errors"] = warmup_errors

        t1 = tiers["tier1"]
        record["tier1"] = {}
        for endpoint in endpoints:
            record["tier1"][endpoint] = _strip_samples(
                load(endpoint_path(config, endpoint), t1["connections"], t1["duration_s"]))
            _check_alive(server, f"tier 1 /{endpoint}")
            time.sleep(srv["cooldown_s"])

        t2 = tiers["tier2"]
        record["tier2"] = _strip_samples(load(f"/{t2['endpoint']}", t2["connections"], t2["duration_s"]))
        _check_alive(server, "tier 2")
        time.sleep(srv["cooldown_s"])

        t3 = tiers["tier3"]
        loaded = _strip_samples(load(f"/{t3['endpoint']}", t3["connections"], t3["duration_s"]))
        record["tier3"] = {
            "idle_ram_mib": idle["ram_mib"],
            "idle_cpu_cores": idle["cpu_cores"],
            "load_ram_peak_mib": loaded.get("server_ram_peak_mib"),
            "load_cpu_cores": loaded.get("server_cpu_cores"),
            "rps": loaded["rps"],
            "error_rate": loaded["error_rate"],
            "client_bound": loaded["client_bound"],
            "client_cpu_busy": loaded["client_cpu_busy"],
        }
        _check_alive(server, "tier 3")
        time.sleep(srv["cooldown_s"])

        t4 = tiers["tier4"]
        stress = load(f"/{t4['endpoint']}", t4["connections"], t4["duration_s"])
        samples = stress.pop("_ram_samples", [])
        stress.update(ram_trend(samples, config["leak"]))
        record["tier4"] = stress
        _check_alive(server, "tier 4")

        time.sleep(srv["recovery_s"])
        peak = server.memory_peak_bytes()
        record["after"] = {
            "ram_mib": round(server.ram_bytes() / MIB, 1),
            "memory_peak_mib": round(peak / MIB, 1) if peak else None,
        }
        server.wait_ready(10)
    except Crashed as crash:
        log(f"{manifest['slug']} round {number}: server stopped during {crash.phase}: {crash.state}")
        record["crashed"] = {"phase": crash.phase, "state": crash.state}
    except (BenchError, OSError) as exc:
        state = server.state()
        if not state.get("Running"):
            record["crashed"] = {"phase": "during a load test",
                                 "state": {k: state.get(k) for k in ("Status", "ExitCode", "OOMKilled", "Error")}}
        else:
            record["crashed"] = {"phase": "harness", "state": {"Error": str(exc)[:500]}}
        log(f"{manifest['slug']} round {number}: {exc}")
    finally:
        server.stop()
        time.sleep(srv["cooldown_s"])
    return record


def summarize(rounds: list[dict]) -> dict:
    metrics = {}
    for path in METRICS:
        values = [get_path(r, path) for r in rounds]
        stat = summary(values)
        if stat:
            metrics[path] = stat
    flags = {
        "rounds": len(rounds),
        "crashed_rounds": sum(1 for r in rounds if r.get("crashed")),
        "ram_growing_rounds": sum(1 for r in rounds if get_path(r, "tier4.ram_growing")),
        "client_bound_rounds": {},
    }
    for run in LOAD_RUNS:
        path = "tier3.client_bound" if run == "tier3_load" else f"{run}.client_bound"
        run_path = "tier3" if run == "tier3_load" else run
        if run in BASE_RUNS or any(get_path(r, run_path) is not None for r in rounds):
            flags["client_bound_rounds"][run] = sum(1 for r in rounds if get_path(r, path))
    return {"metrics": metrics, "flags": flags}


BASE_RUNS = ("tier1.text", "tier1.json", "tier1.db-single", "tier1.html", "tier2", "tier3_load", "tier4")


def capacity_ratio(run: dict | None, base: dict | None) -> tuple[float | None, bool]:
    """One round pair's capacity ratio for a load run, and whether efficiency decided it.

    When neither side was client-bound, both servers were the limit and the
    requests/s ratio measures their capacity. When either side was
    client-bound, that server had idle CPU, so its requests/s says less than
    its cost per request: the ratio of requests per server CPU-second
    (efficiency) is used instead.
    """
    if not run or not base:
        return None, False
    if run.get("client_bound") or base.get("client_bound"):
        value = ratio(efficiency(run), efficiency(base))
        if value is not None:
            return value, True
    return ratio(run.get("rps"), base.get("rps")), False


def ratios(framework_rounds: list[dict], baseline_rounds: list[dict]) -> dict:
    """Per-round ratio framework / baseline, summarized over the rounds.

    `<run>.capacity` (for example tier1.json.capacity) is the capacity ratio
    of capacity_ratio(); its `efficiency_rounds` counts the round pairs in
    which efficiency was used.
    """
    out = {}
    pairs = list(zip(framework_rounds, baseline_rounds))
    for path in METRICS:
        if path.rsplit(".", 1)[-1] in NO_RATIO or any(part in path for part in NO_RATIO):
            continue
        values = [ratio(get_path(f, path), get_path(b, path)) for f, b in pairs]
        stat = summary(values)
        if stat:
            out[path] = stat
    for run in CAPACITY_RUNS:
        results = [capacity_ratio(get_path(f, run), get_path(b, run)) for f, b in pairs]
        stat = summary([value for value, _ in results])
        if stat:
            stat["efficiency_rounds"] = sum(1 for value, used in results if used and value is not None)
            # Both servers client-bound and no efficiency to compare: the
            # requests/s ratio then compares two load generators, not servers.
            stat["not_comparable_rounds"] = sum(
                1 for (value, used), (f, b) in zip(results, pairs)
                if value is not None and not used
                and get_path(f, f"{run}.client_bound") and get_path(b, f"{run}.client_bound"))
            out[f"{run}.capacity"] = stat
    return out


def require_measurable(conformance: dict, slug: str) -> None:
    if not conformance.get("passed"):
        failed = [c for c in conformance.get("checks", []) if not c["ok"]]
        detail = "; ".join(f"{c['endpoint']}: {c['problem']}" for c in failed) or "no checks ran"
        raise BenchError(f"{slug} failed conformance: {detail}")
