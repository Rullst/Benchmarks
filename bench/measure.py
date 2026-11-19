"""One measurement round (all four tiers) and the per-job summary."""

from __future__ import annotations

import statistics
import time
from pathlib import Path

import sessions
import workload as W
from common import ENDPOINTS, PHASE2_ENDPOINTS, BenchError, declared_endpoints, endpoint_path, log, phase2
from containers import Server, database_handle, reset_tables, start_server
from loadgen import MIB, run_load
from loadgen_process import per_request_cpu
from stats import get_path, ratio, summary, window_median

# Metrics summarized over rounds. Ratios to the baseline are computed for
# every metric except error counts and rates and the database's CPU use.
# rps_per_cpu is the server efficiency (requests per server CPU-second);
# total_rps_per_cpu counts PostgreSQL's CPU too; db_us_per_request is
# PostgreSQL's CPU time per request in microseconds.
RUN_METRICS = ("rps", "latency_ms.mean", "latency_ms.p50", "latency_ms.p99", "error_rate", "server_cpu_cores",
               "rps_per_cpu", "db_cpu_cores", "db_us_per_request", "cpu_us_per_request", "total_rps_per_cpu")
METRICS = [
    *(f"tier1.{ep}.{m}" for ep in ENDPOINTS for m in RUN_METRICS),
    # Write contention (config "hot_rows"): PUT /world/{id} on a few rows; reported, not ranked.
    *(f"hot_rows.{m}" for m in ("rps", "latency_ms.p50", "latency_ms.p99", "error_rate", "timeouts",
                                "transport_errors", "server_cpu_cores", "rps_per_cpu", "db_cpu_cores",
                                "db_us_per_request")),
    "tier2.rps", "tier2.latency_ms.p50", "tier2.latency_ms.p99", "tier2.error_rate", "tier2.timeouts",
    "tier2.server_cpu_cores", "tier2.rps_per_cpu",
    "tier3.idle_ram_mib", "tier3.idle_cpu_cores", "tier3.load_ram_peak_mib", "tier3.load_cpu_cores",
    "tier3.rps", "tier3.error_rate",
    "tier4.rps", "tier4.latency_ms.p99", "tier4.error_rate", "tier4.transport_errors", "tier4.timeouts",
    "tier4.server_cpu_cores", "tier4.rps_per_cpu",
    "tier4.ram_mid_mib", "tier4.ram_end_mib", "tier4.ram_growth_mib",
    "startup_s", "idle.tasks", "after.ram_mib", "after.memory_peak_mib",
]
NO_RATIO = ("error_rate", "transport_errors", "timeouts", "ram_growth_mib", "tasks", "db_cpu_cores")
LOAD_RUNS = [*(f"tier1.{ep}" for ep in ENDPOINTS), "hot_rows", "tier2", "tier3_load", "tier4"]
# Runs whose capacity ratio the rankings use (see capacity_ratio). Tiers 2
# and 4 are stability checks (pass or fail), not scores.
CAPACITY_RUNS = [f"tier1.{ep}" for ep in ENDPOINTS]
# A run limited by the load generator is scored by efficiency only when the
# server used at least this share of its vCPUs: below it, its requests per
# CPU-second were measured far from the load it could take, and the run is
# not comparable (README "How the scores are computed").
MIN_SERVER_SHARE = 0.75
LIMITERS = ("postgresql", "load-generator")


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


# The phase-2 workload builders that config.json "endpoint_workloads" names
# (bench/workload.py); each takes the round's sessions (phase2_context).
BUILDERS = {
    "world_by_id": lambda context: W.world_by_id(),
    "worlds_pages": lambda context: W.worlds_pages(),
    "put_world": lambda context: W.put_world(write_csrf=context.get("write_csrf")),
    "form_posts": lambda context: W.form_posts(context["form_sessions"]),
    "me": lambda context: W.me(context["login_sessions"]),
}


def phase2_context(manifest: dict, config: dict, port: int) -> dict:
    """What the phase-2 workloads need, obtained in every round (servers start empty) before the
    application endpoints' warm-up.

    One GET /form per future connection (its cookies and hidden fields), one
    login per connection (user1..userN), and for phase2.write_csrf the CSRF
    cookie the PUT requests carry.
    """
    served = declared_endpoints(manifest)
    settings = phase2(manifest)
    options = config.get("phase2", {})
    count, parallel = options.get("sessions", 125), options.get("session_fetch_parallel", 8)
    context: dict = {}
    if "form" in served:
        context["form_sessions"] = sessions.form_sessions(port, count, parallel)
    if "me" in served:
        context["login_sessions"] = sessions.login_sessions(port, count, parallel)
    write_csrf = settings.get("write_csrf")
    if write_csrf and "world-update" in served:
        context["write_csrf"] = (write_csrf["cookie"], write_csrf["header"],
                                 sessions.cookie_value(port, write_csrf["cookie"]))
    return context


def endpoint_workload(endpoint: str, config: dict, context: dict) -> W.Workload:
    """The requests a load test of an endpoint sends: one fixed request, or a phase-2 workload."""
    name = config.get("endpoint_workloads", {}).get(endpoint)
    if name is None:
        return W.static(endpoint_path(config, endpoint))
    if name not in BUILDERS:
        raise BenchError(f"config.json endpoint_workloads: unknown workload '{name}' for /{endpoint}")
    return BUILDERS[name](context)


def warmup_seconds(manifest: dict, config: dict) -> int:
    """How long each endpoint is warmed up: longer for runtimes that compile hot code while running.

    bench.json `"jit": true` marks a runtime whose JIT compiles code after
    profiling it at run time (HotSpot JVM, .NET tiered compilation, V8 for
    Node.js, Ruby with YJIT, PHP with the OPcache JIT on): it gets
    config.json warmup.jit_duration_s instead of warmup.duration_s.
    """
    warm = config["warmup"]
    return int(warm.get("jit_duration_s", warm["duration_s"]) if manifest.get("jit") else warm["duration_s"])


def measure_round(manifest: dict, config: dict, split: dict, binary: Path, number: int,
                  framework_tables: list[str] | tuple = ()) -> dict:
    """One round of one implementation: a fresh server, every tier, then the application endpoints.

    Order: start-up; idle (Tier 3 idle RAM); each phase-1 endpoint warmed up
    immediately before its Tier 1 run (warm-up, idle settle, measurement);
    Tier 2; Tier 4; an idle recovery; Tier 3 under load (the Memory score:
    the RAM high-water mark after the load tiers); the application
    endpoints (sessions, then warm-up and measurement per endpoint, then hot
    rows).
    """
    tiers = config["tiers"]
    srv = config["server"]
    warm = config["warmup"]
    record: dict = {"round": number, "implementation": manifest["slug"], "crashed": None}
    # Every round starts from the same `world` table (/updates rewrites rows)
    # and empty session tables.
    reset_tables(config, framework_tables)
    server = start_server(manifest, config, split["server"], keep_logs=False)
    client = split["client"]
    database = database_handle(config)
    served = declared_endpoints(manifest)
    endpoints = [ep for ep in tiers["tier1"]["endpoints"] if ep in served]
    warm_s = warmup_seconds(manifest, config)
    record["warmup_s"] = warm_s
    record["warmup"] = {}

    def load(workload: W.Workload, connections: int, duration_s: int, count_statuses: bool = False) -> dict:
        return run_load(binary, server.base_url, connections=connections, duration_s=duration_s, config=config,
                        client_cpus=client, server=server, database=database,
                        db_cpus=split.get("database", client), workload=workload,
                        count_statuses=count_statuses)

    def tier1(endpoint: str, workload: W.Workload, count_statuses: bool) -> None:
        """Warm one endpoint up, let it settle, then measure it.

        The warm-up counts every status class (a 3xx is a failure), so a
        server that redirects or fails is visible even on the static runs,
        which are measured without wrk's Lua response hook.
        """
        t1 = tiers["tier1"]
        warmed = load(workload, warm["connections"], warm_s, True)
        record["warmup"][endpoint] = {
            "errors": warmed["non_2xx"] + warmed["transport_errors"],
            "requests": warmed["requests_ok"] + warmed["non_2xx"] + warmed["transport_errors"],
            "error_rate": warmed["error_rate"]}
        _check_alive(server, f"warm-up /{endpoint}")
        time.sleep(warm.get("settle_s", 0))
        record["tier1"][endpoint] = _strip_samples(load(workload, t1["connections"], t1["duration_s"],
                                                        count_statuses))
        _check_alive(server, f"tier 1 /{endpoint}")
        time.sleep(srv["cooldown_s"])

    def application_phase(names: list[str]) -> None:
        """The phase-2 endpoints, at the end of the round: sessions, then each endpoint, then hot rows.

        Logging in hashes 125 passwords; a memory-hard hash (Argon2id, 19 MiB
        per verification) can leave hundreds of MiB in the allocator (Axum:
        from 1 MiB to about 1 GiB in the first trial), which would distort
        the RAM of Tiers 3 and 4 if it ran before them.
        """
        t1 = tiers["tier1"]
        context = phase2_context(manifest, config, server.port)
        record["sessions"] = {key: len(value) for key, value in context.items() if key.endswith("_sessions")}
        if context.get("login_sessions"):
            record["sessions"]["bearer"] = any(s.bearer for s in context["login_sessions"])
        for endpoint in names:
            # Every phase-2 response that is not 2xx counts as a failure (wrk's Lua status hook).
            tier1(endpoint, endpoint_workload(endpoint, config, context), True)
        record["application_warmup_errors"] = sum(record["warmup"][ep]["errors"] for ep in names)
        hot = config.get("hot_rows")
        if hot and hot.get("endpoint") in names:
            hot_workload = W.hot_rows(hot.get("ids", 10), hot.get("requests", 2000),
                                      write_csrf=context.get("write_csrf"))
            record["hot_rows"] = _strip_samples(load(hot_workload, t1["connections"], t1["duration_s"], True))
            record["hot_rows"]["ids"] = hot.get("ids", 10)
            _check_alive(server, "hot rows")

    try:
        record["startup_s"] = server.wait_ready(manifest.get("startup_timeout_s", 120))
        time.sleep(srv["settle_s"])
        idle = _idle_window(server, tiers["tier3"]["idle_s"], config["sampling_interval_s"])
        record["idle"] = idle

        # The endpoints up to /fortunes first; the application endpoints (phase 2)
        # at the end, so that no login has run before the RAM of Tiers 3 and 4
        # is measured (see application_phase).
        basic = [ep for ep in endpoints if ep not in PHASE2_ENDPOINTS]
        application = [ep for ep in endpoints if ep in PHASE2_ENDPOINTS]
        record["tier1"] = {}
        for endpoint in basic:
            tier1(endpoint, endpoint_workload(endpoint, config, {}), False)
        record["warmup_errors"] = sum(record["warmup"][ep]["errors"] for ep in basic)

        t2 = tiers["tier2"]
        record["tier2"] = _strip_samples(load(W.static(f"/{t2['endpoint']}"), t2["connections"], t2["duration_s"]))
        _check_alive(server, "tier 2")
        time.sleep(srv["cooldown_s"])

        t4 = tiers["tier4"]
        stress = load(W.static(f"/{t4['endpoint']}"), t4["connections"], t4["duration_s"])
        samples = stress.pop("_ram_samples", [])
        stress.update(ram_trend(samples, config["leak"]))
        record["tier4"] = stress
        _check_alive(server, "tier 4")
        time.sleep(srv["recovery_s"])

        # Memory: the high-water mark while serving /json after the load tiers
        # above and an idle period, so it includes what the server kept.
        t3 = tiers["tier3"]
        loaded = _strip_samples(load(W.static(f"/{t3['endpoint']}"), t3["connections"], t3["duration_s"]))
        record["tier3"] = {
            "idle_ram_mib": idle["ram_mib"],
            "idle_cpu_cores": idle["cpu_cores"],
            "load_ram_peak_mib": loaded.get("server_ram_peak_mib"),
            "load_cpu_cores": loaded.get("server_cpu_cores"),
            "rps": loaded["rps"],
            "error_rate": loaded["error_rate"],
            "client_bound": loaded["client_bound"],
            "limited_by": loaded.get("limited_by"),
            "client_cpu_busy": loaded["client_cpu_busy"],
            "after": "tier 1 (phase 1), tier 2, tier 4 and an idle period",
        }
        _check_alive(server, "tier 3")
        time.sleep(srv["cooldown_s"])
        peak = server.memory_peak_bytes()
        record["after"] = {
            "ram_mib": round(server.ram_bytes() / MIB, 1),
            "memory_peak_mib": round(peak / MIB, 1) if peak else None,
        }
        server.wait_ready(10)

        if application:
            application_phase(application)
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


def run_limiter(run: dict | None) -> str | None:
    """"postgresql", "load-generator" or None for one load run (older results: derived from CPU use)."""
    if not run or not run.get("client_bound"):
        return None
    if run.get("limited_by") in LIMITERS:
        return run["limited_by"]
    return "postgresql" if (run.get("db_cpu_cores") or 0) >= (run.get("loadgen_cpu_cores") or 0) else "load-generator"


def enrich(rounds: list[dict]) -> list[dict]:
    """Add the per-request CPU fields to load runs recorded before they existed (in place)."""
    for r in rounds:
        runs = [*(r.get("tier1") or {}).values(), *(r[k] for k in ("hot_rows", "tier2", "tier4") if r.get(k))]
        for run in runs:
            if isinstance(run, dict) and "rps" in run and "cpu_us_per_request" not in run:
                run.update(per_request_cpu(run))
    return rounds


def summarize(rounds: list[dict]) -> dict:
    enrich(rounds)
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
        "limited_rounds": {},
        "warmup_errors": {},
    }
    for run in LOAD_RUNS:
        path = "tier3" if run == "tier3_load" else run
        if run in BASE_RUNS or any(get_path(r, path) is not None for r in rounds):
            flags["client_bound_rounds"][run] = sum(1 for r in rounds if get_path(r, f"{path}.client_bound"))
            counts = {name: sum(1 for r in rounds if run_limiter(get_path(r, path)) == name) for name in LIMITERS}
            flags["limited_rounds"][run] = {name: n for name, n in counts.items() if n}
    for r in rounds:
        for endpoint, warmed in (r.get("warmup") or {}).items():
            flags["warmup_errors"][endpoint] = flags["warmup_errors"].get(endpoint, 0) + warmed.get("errors", 0)
    return {"metrics": metrics, "flags": flags}


BASE_RUNS = ("tier1.text", "tier1.json", "tier1.db-single", "tier1.html", "tier2", "tier3_load", "tier4")


def total_efficiency(run: dict | None) -> float | None:
    """Requests per CPU-second of the server and PostgreSQL together."""
    if not run or run.get("rps") is None:
        return None
    if run.get("total_rps_per_cpu") is not None:
        return run["total_rps_per_cpu"]
    server = run.get("server_cpu_cores")
    if not server:
        return None
    return run["rps"] / (server + (run.get("db_cpu_cores") or 0.0))


def server_share(run: dict) -> float | None:
    cores, cpus = run.get("server_cpu_cores"), run.get("server_cpus") or 2
    return cores / cpus if cores is not None else None


def capacity_ratio(run: dict | None, base: dict | None) -> tuple[float | None, str]:
    """One round pair's capacity ratio for a load run, and its basis.

    Bases: "rps" when neither server's run was client-bound: both servers
    were the limit, so the requests/s ratio measures their capacity. "cpu"
    when either was client-bound: the ratio of requests per CPU-second of
    the server and PostgreSQL together, so a framework is charged for the
    PostgreSQL work its queries cause (a run limited by PostgreSQL is mostly
    PostgreSQL's CPU). "not comparable" when a side was limited by the load
    generator while its server used less than MIN_SERVER_SHARE of its vCPUs:
    its efficiency was measured far from the load it could take, so it is
    not used as its capacity. "missing" when a side has no run.
    """
    if not run or not base:
        return None, "missing"
    limits = (run_limiter(run), run_limiter(base))
    if limits == (None, None):
        return ratio(run.get("rps"), base.get("rps")), "rps"
    for side, limit in ((run, limits[0]), (base, limits[1])):
        share = server_share(side)
        if limit == "load-generator" and (share is None or share < MIN_SERVER_SHARE):
            return None, "not comparable"
    value = ratio(total_efficiency(run), total_efficiency(base))
    return (value, "cpu") if value is not None else (None, "not comparable")


def ratios(framework_rounds: list[dict], baseline_rounds: list[dict]) -> dict:
    """Per-round ratio framework / baseline, summarized over the round pairs.

    `<run>.capacity` (for example tier1.json.capacity) summarizes the
    comparable pairs' capacity ratios (capacity_ratio); `pairs` counts every
    pair with both runs, `cpu_rounds` the pairs scored by CPU efficiency,
    `not_comparable_rounds` the pairs left out, and `postgresql_rounds` /
    `load_generator_rounds` the pairs in which either side was limited by
    PostgreSQL or by the load generator.
    """
    out = {}
    pairs = list(zip(enrich(framework_rounds), enrich(baseline_rounds)))
    for path in METRICS:
        if path.rsplit(".", 1)[-1] in NO_RATIO or any(part in path for part in NO_RATIO):
            continue
        values = [ratio(get_path(f, path), get_path(b, path)) for f, b in pairs]
        stat = summary(values)
        if stat:
            out[path] = stat
    for run in CAPACITY_RUNS:
        sides = [(get_path(f, run), get_path(b, run)) for f, b in pairs]
        results = [capacity_ratio(f, b) for f, b in sides]
        present = [(value, basis, f, b) for (value, basis), (f, b) in zip(results, sides) if basis != "missing"]
        if not present:
            continue
        stat = summary([value for value, basis, _, _ in present if basis in ("rps", "cpu")]) or {
            "median": None, "min": None, "max": None, "spread": None, "n": 0}
        stat["pairs"] = len(present)
        stat["cpu_rounds"] = sum(1 for _, basis, _, _ in present if basis == "cpu")
        stat["not_comparable_rounds"] = sum(1 for _, basis, _, _ in present if basis == "not comparable")
        for name, key in (("postgresql", "postgresql_rounds"), ("load-generator", "load_generator_rounds")):
            stat[key] = sum(1 for _, _, f, b in present if name in (run_limiter(f), run_limiter(b)))
        out[f"{run}.capacity"] = stat
    return out


def require_measurable(conformance: dict, slug: str) -> None:
    if not conformance.get("passed"):
        failed = [c for c in conformance.get("checks", []) if not c["ok"]]
        detail = "; ".join(f"{c['endpoint']}: {c['problem']}" for c in failed) or "no checks ran"
        raise BenchError(f"{slug} failed conformance: {detail}")
