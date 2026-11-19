"""Run one load generator process and measure both sides of it.

Client CPUs from /proc/stat, the load generator's own CPU from rusage, the
server's and the database's cgroup CPU and the server's sampled RAM. The
same measurement serves wrk (loadgen_wrk.py, the suite's load generator) and
the documented fallback oha (loadgen_oha.py), so both return the same
metrics dict.
"""

from __future__ import annotations

import resource
import subprocess
import threading
import time
from pathlib import Path
from typing import Callable

from common import BenchError
from system import busy_fraction, read_cpu_times

MIB = 1024 * 1024


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


def measure(cmd: list[str], parse: Callable[[str], dict], *, tool: str, connections: int,
            duration_s: int, config: dict, client_cpus: list[int], saturation_threshold: float,
            server=None, database=None, db_cpus: list[int] | None = None) -> dict:
    db_cpus = db_cpus or client_cpus
    all_client = sorted(set(client_cpus) | set(db_cpus))
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
        raise BenchError(f"{tool} failed ({proc.returncode}): {proc.stderr.strip()[-500:]}")
    try:
        metrics = parse(proc.stdout)
    except (ValueError, KeyError, TypeError) as exc:
        raise BenchError(f"could not parse {tool} output: {exc}: {proc.stdout[-300:]}") from exc

    def busy(cpus: list[int]) -> float:
        return busy_fraction(read_cpu_times(cpus, stat_before), read_cpu_times(cpus, stat_after))

    loadgen_cpu = (usage_after.ru_utime - usage_before.ru_utime) + (usage_after.ru_stime - usage_before.ru_stime)
    client_busy = busy(all_client)
    loadgen_busy = busy(client_cpus)
    db_busy = busy(db_cpus)
    metrics.update({
        "connections": connections,
        "client_cpu_busy": round(client_busy, 3),
        "loadgen_cpu_busy": round(loadgen_busy, 3),
        "db_cpu_busy": round(db_busy, 3),
        "loadgen_cpu_share": round(loadgen_cpu / (wall * len(client_cpus)), 3),
        "loadgen_cpu_cores": round(loadgen_cpu / wall, 3),
        "client_bound": max(client_busy, loadgen_busy, db_busy) >= saturation_threshold,
    })
    if database is not None:
        metrics["db_cpu_cores"] = round((db_cpu_after - db_cpu_before) / 1e6 / wall, 3)
    if server is not None:
        cores = (server_cpu_after - server_cpu_before) / 1e6 / wall
        metrics["server_cpu_cores"] = round(cores, 3)
        metrics["rps_per_cpu"] = round(metrics["rps"] / cores, 1) if cores else None
        values = [ram for _, ram in samples]
        metrics["server_ram_peak_mib"] = round(max(values) / MIB, 1) if values else None
        metrics["_ram_samples"] = samples
    return metrics


def error_metrics(ok: int, non_2xx: int, transport_errors: int, timeouts: int, duration: float,
                  error_kinds: dict, latency_ms: dict) -> dict:
    """The tool-independent part of the metrics dict (loadgen.parse_result's keys)."""
    total = ok + non_2xx + transport_errors
    duration = duration or 1.0
    return {
        "duration_s": round(duration, 3),
        "requests_ok": ok,
        "non_2xx": non_2xx,
        "transport_errors": transport_errors,
        "timeouts": timeouts,
        "error_rate": round((non_2xx + transport_errors) / total, 6) if total else 1.0,
        "error_kinds": error_kinds,
        "rps": round(ok / duration, 2),
        "latency_ms": latency_ms,
    }
