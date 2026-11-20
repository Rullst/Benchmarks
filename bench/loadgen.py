"""The load generator: wrk 4.2.0, built from its pinned source, run on the client CPUs.

`run_load` measures one load test (bench/loadgen_wrk.py runs wrk,
bench/loadgen_process.py measures both sides). A test sends either one fixed
request (the phase-1 endpoints and Tiers 2-4) or a workload of prebuilt
requests that wrk cycles through (bench/workload.py: the phase-2 endpoints).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import loadgen_wrk
from common import BenchError, run
from loadgen_process import MIB, RamSampler  # noqa: F401 - re-exported for measure.py and the tests
from workload import Workload


def describe_binary(path: Path, load_generator: dict) -> dict:
    """What the results record about the wrk binary: version, SHA-256 and the compiler that built it.

    wrk publishes no binaries; bench/install-loadgen.sh checks the source
    tarball's SHA-256 (config.json) and builds it on the runner.
    """
    if not path.is_file():
        raise BenchError(f"set WRK to the wrk {load_generator['version']} binary that bench/install-loadgen.sh "
                         "builds")
    banner = run([str(path), "-v"], check=False, timeout=30)
    version_line = ((banner.stdout or "") + (banner.stderr or "")).strip().splitlines()[:1]
    if not version_line or f"wrk {load_generator['version']}" not in version_line[0]:
        raise BenchError(f"{path} is not wrk {load_generator['version']}: {version_line}")
    compiler = run(["cc", "--version"], check=False, timeout=30)
    return {
        "name": load_generator["name"],
        "version": load_generator["version"],
        "banner": version_line[0],
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "source_sha256": load_generator["source_sha256"],
        "build": load_generator.get("build", ""),
        "compiler": (compiler.stdout or "").strip().splitlines()[0] if compiler.returncode == 0 else "unknown",
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
             client_cpus: list[int], server=None, database=None, db_cpus: list[int] | None = None,
             workload: Workload | None = None, count_statuses: bool = False,
             workdir: Path | None = None) -> dict:
    """Run one wrk test and measure both sides of it.

    Without a workload, `url` is requested with GET (one fixed request). With
    one, `url` is the server's base URL and the workload supplies the
    requests. count_statuses adds wrk's Lua response hook, which counts every
    status that is not 2xx (3xx included) as a failure; without it wrk counts
    only statuses of 400 and above.

    client_cpus run the load generator; db_cpus run PostgreSQL (the same CPUs
    unless the database has its own). The run is client-bound when the
    load generator's or the database's CPUs were at least
    `saturation_threshold` busy.
    """
    return loadgen_wrk.run_load(binary, url, connections=connections, duration_s=duration_s, config=config,
                                client_cpus=client_cpus, server=server, database=database, db_cpus=db_cpus,
                                workload=workload, tool_config=config["load_generator"], workdir=workdir,
                                count_statuses=count_statuses)
