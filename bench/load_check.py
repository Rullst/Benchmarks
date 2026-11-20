"""The concurrent conformance step: every declared endpoint under a short load, with no errors allowed.

The sequential checks (bench/conformance.py, bench/conformance_phase2.py)
send one request at a time. This step sends each endpoint's measurement
workload with config.json `concurrent_check` (125 connections for 3 s) and
wrk's Lua status hook, so any response that is not 2xx, any transport error
and any timeout fails the implementation's conformance check before it is
measured (docs: README "Conformance").
"""

from __future__ import annotations

from pathlib import Path

from common import PHASE2_ENDPOINTS, BenchError, declared_endpoints
from loadgen import run_load
from measure import endpoint_workload, phase2_context


def concurrent_checks(manifest: dict, config: dict, client_cpus: list[int], binary: Path, server) -> list[dict]:
    """One check per declared Tier 1 endpoint: zero errors at the configured connections."""
    options = config.get("concurrent_check", {})
    connections, duration = options.get("connections", 125), options.get("duration_s", 3)
    served = declared_endpoints(manifest)
    endpoints = [ep for ep in config["tiers"]["tier1"]["endpoints"] if ep in served]
    checks: list[dict] = []
    try:
        context = phase2_context(manifest, config, server.port) if any(
            ep in PHASE2_ENDPOINTS for ep in endpoints) else {}
    except (BenchError, OSError) as exc:
        return [{"endpoint": "sessions for the concurrent step", "ok": False, "problem": str(exc)[:500]}]
    for endpoint in endpoints:
        label = f"/{endpoint} with {connections} connections for {duration} s"
        try:
            result = run_load(binary, server.base_url, connections=connections, duration_s=duration, config=config,
                              client_cpus=client_cpus, workload=endpoint_workload(endpoint, config, context),
                              count_statuses=True)
        except (BenchError, OSError) as exc:
            checks.append({"endpoint": label, "ok": False, "problem": str(exc)[:500]})
            continue
        errors = result["non_2xx"] + result["transport_errors"]
        ok = errors == 0 and result["requests_ok"] > 0
        problem = None
        if not ok:
            problem = (f"{errors} errors and {result['requests_ok']} successful responses "
                       f"(error kinds {result.get('error_kinds')}, status classes {result.get('status_classes')}); "
                       "zero errors are required")
        checks.append({"endpoint": label, "ok": ok, "problem": problem, "requests_ok": result["requests_ok"],
                       "errors": errors, "rps": result["rps"]})
    return checks
