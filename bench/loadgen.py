"""The load generator (bombardier), pinned to the client CPUs, plus resource sampling."""

from __future__ import annotations

import hashlib
import json
import resource
import subprocess
import threading
import time
from pathlib import Path

from common import BenchError
from system import busy_fraction, format_cpu_list, read_cpu_times

MIB = 1024 * 1024


def verify_binary(path: Path, expected_sha256: str) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != expected_sha256:
        raise BenchError(f"{path} has sha256 {digest}, expected {expected_sha256}")
    return digest


class RamSampler(threading.Thread):
    """Samples the server's RAM at a fixed interval while a load test runs."""

    def __init__(self, server, interval_s: float):
        super().__init__(daemon=True)
        self.server = server
        self.interval_s = interval_s
        self.samples: list[tuple[float, int]] = []
        self._halt = threading.Event()
        self._t0 = time.monotonic()

    def run(self) -> None:
        while not self._halt.is_set():
            try:
                self.samples.append((time.monotonic() - self._t0, self.server.ram_bytes()))
            except (OSError, ValueError, BenchError):
                pass  # the container may have exited; the caller checks
            self._halt.wait(self.interval_s)

    def stop(self) -> list[tuple[float, int]]:
        self._halt.set()
        self.join(timeout=5)
        return self.samples


def parse_result(raw: dict) -> dict:
    """Turn bombardier's JSON result into the suite's metrics."""
    result = raw["result"]
    duration = float(result["timeTakenSeconds"]) or 1.0
    ok = int(result["req2xx"])
    non_2xx = sum(int(result[k]) for k in ("req1xx", "req3xx", "req4xx", "req5xx", "others"))
    errors = result.get("errors") or []
    transport_errors = sum(int(e["count"]) for e in errors)
    timeouts = sum(int(e["count"]) for e in errors if "timeout" in e["description"].lower())
    total = ok + non_2xx + transport_errors
    latency = result.get("latency") or {}
    percentiles = latency.get("percentiles") or {}

    def ms(value) -> float | None:
        return None if value is None else round(float(value) / 1000.0, 3)

    return {
        "duration_s": round(duration, 3),
        "requests_ok": ok,
        "non_2xx": non_2xx,
        "transport_errors": transport_errors,
        "timeouts": timeouts,
        "error_rate": round((non_2xx + transport_errors) / total, 6) if total else 1.0,
        "error_kinds": {e["description"][:120]: int(e["count"]) for e in errors[:10]},
        "rps": round(ok / duration, 2),
        "latency_ms": {
            "mean": ms(latency.get("mean")),
            "p50": ms(percentiles.get("50")),
            "p99": ms(percentiles.get("99")),
            "max": ms(latency.get("max")),
        },
    }


def efficiency(run: dict | None) -> float | None:
    """Requests per server CPU-second of one load run (rps / server_cpu_cores)."""
    if not run:
        return None
    if run.get("rps_per_cpu") is not None:
        return run["rps_per_cpu"]
    cores = run.get("server_cpu_cores")
    return round(run["rps"] / cores, 1) if cores and run.get("rps") is not None else None


def run_load(binary: Path, url: str, *, connections: int, duration_s: int, config: dict,
             client_cpus: list[int], server=None, database=None, db_cpus: list[int] | None = None) -> dict:
    """Run one bombardier test and measure both sides of it.

    client_cpus run the load generator; db_cpus run PostgreSQL (the same CPUs
    unless the database has its own). The run is client-bound when the
    load generator's or the database's CPUs were at least
    `saturation_threshold` busy.
    """
    db_cpus = db_cpus or client_cpus
    all_client = sorted(set(client_cpus) | set(db_cpus))
    lg = config["load_generator"]
    cmd = ["taskset", "-c", format_cpu_list(client_cpus), str(binary), f"--{lg['client']}",
           "-c", str(connections), "-d", f"{duration_s}s", "-t", f"{lg['timeout_s']}s",
           "-l", "-p", "r", "-o", "j", url]
    sampler = None
    server_cpu_before = db_cpu_before = 0
    if server is not None:
        sampler = RamSampler(server, config["sampling_interval_s"])
        server_cpu_before = server.cpu_usec()
        sampler.start()
    if database is not None:
        db_cpu_before = database.cpu_usec()
    stat_before = Path("/proc/stat").read_text()
    usage_before = resource.getrusage(resource.RUSAGE_CHILDREN)
    started = time.monotonic()
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=duration_s + 120, check=False)
    wall = time.monotonic() - started
    usage_after = resource.getrusage(resource.RUSAGE_CHILDREN)
    stat_after = Path("/proc/stat").read_text()
    samples = sampler.stop() if sampler else []
    server_cpu_after = server.cpu_usec() if server is not None else 0
    db_cpu_after = database.cpu_usec() if database is not None else 0

    if proc.returncode != 0:
        raise BenchError(f"bombardier failed ({proc.returncode}): {proc.stderr.strip()[-500:]}")
    try:
        metrics = parse_result(json.loads(proc.stdout))
    except (ValueError, KeyError) as exc:
        raise BenchError(f"could not parse bombardier output: {exc}: {proc.stdout[:300]}") from exc

    loadgen_cpu = (usage_after.ru_utime - usage_before.ru_utime) + (usage_after.ru_stime - usage_before.ru_stime)

    def busy(cpus: list[int]) -> float:
        return busy_fraction(read_cpu_times(cpus, stat_before), read_cpu_times(cpus, stat_after))

    client_busy = busy(all_client)
    loadgen_busy = busy(client_cpus)
    db_busy = busy(db_cpus)
    threshold = lg["saturation_threshold"]
    metrics.update({
        "connections": connections,
        "client_cpu_busy": round(client_busy, 3),
        "loadgen_cpu_busy": round(loadgen_busy, 3),
        "db_cpu_busy": round(db_busy, 3),
        "loadgen_cpu_share": round(loadgen_cpu / (wall * len(client_cpus)), 3),
        "loadgen_cpu_cores": round(loadgen_cpu / wall, 3),
        "client_bound": max(client_busy, loadgen_busy, db_busy) >= threshold,
    })
    if database is not None:
        metrics["db_cpu_cores"] = round((db_cpu_after - db_cpu_before) / 1e6 / wall, 3)
    if server is not None:
        metrics["server_cpu_cores"] = round((server_cpu_after - server_cpu_before) / 1e6 / wall, 3)
        metrics["rps_per_cpu"] = efficiency(metrics)
        values = [ram for _, ram in samples]
        metrics["server_ram_peak_mib"] = round(max(values) / MIB, 1) if values else None
        metrics["_ram_samples"] = samples
    return metrics
